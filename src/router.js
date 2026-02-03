/**
 * LLM Smart Router - Enhanced Router with Fallback Chain
 * 
 * エラーハンドリング強化版:
 * - フォールバック連鎖 (Primary → Secondary → Tertiary)
 * - 指数バックオフリトライ
 * - 詳細なエラーログ
 */

import fs from 'fs';
import yaml from 'js-yaml';
import axios from 'axios';
import Anthropic from '@anthropic-ai/sdk';
import { fileURLToPath } from 'url';
import path from 'path';

// ============================================
// エラークラス定義
// ============================================

class LLMRouterError extends Error {
  constructor(message, options = {}) {
    super(message);
    this.name = 'LLMRouterError';
    this.errorCode = options.errorCode || 'ROUTER_ERROR';
    this.retryable = options.retryable || false;
    this.details = options.details || {};
  }

  toDict() {
    return {
      error_code: this.errorCode,
      message: this.message,
      retryable: this.retryable,
      details: this.details,
      type: this.name
    };
  }
}

class APIError extends LLMRouterError {
  constructor(message, statusCode, apiProvider, responseBody) {
    super(message, {
      errorCode: 'API_ERROR',
      retryable: statusCode >= 500, // 5xxはリトライ可能
      details: { statusCode, apiProvider, responseBody }
    });
    this.name = 'APIError';
    this.statusCode = statusCode;
    this.apiProvider = apiProvider;
  }
}

class ConnectionError extends LLMRouterError {
  constructor(message, endpoint, timeout) {
    super(message, {
      errorCode: 'CONNECTION_ERROR',
      retryable: true,
      details: { endpoint, timeout }
    });
    this.name = 'ConnectionError';
    this.endpoint = endpoint;
    this.timeout = timeout;
  }
}

class RateLimitError extends LLMRouterError {
  constructor(message, retryAfter, limit, remaining, apiProvider) {
    super(message, {
      errorCode: 'RATE_LIMIT_ERROR',
      retryable: true,
      details: { retryAfter, limit, remaining, apiProvider }
    });
    this.name = 'RateLimitError';
    this.retryAfter = retryAfter;
  }
}

class ModelUnavailableError extends LLMRouterError {
  constructor(message, modelName, provider) {
    super(message, {
      errorCode: 'MODEL_UNAVAILABLE',
      retryable: true,
      details: { modelName, provider }
    });
    this.name = 'ModelUnavailableError';
    this.modelName = modelName;
    this.provider = provider;
  }
}

class AuthenticationError extends LLMRouterError {
  constructor(message, apiProvider) {
    super(message, {
      errorCode: 'AUTHENTICATION_ERROR',
      retryable: false, // 認証エラーはリトライ不可
      details: { apiProvider }
    });
    this.name = 'AuthenticationError';
  }
}

class AllModelsFailedError extends LLMRouterError {
  constructor(errors) {
    super('すべてのモデルで処理に失敗しました', {
      errorCode: 'ALL_MODELS_FAILED',
      retryable: false,
      details: { 
        failedModels: errors.map(e => e.model || 'unknown'),
        errorCount: errors.length
      }
    });
    this.name = 'AllModelsFailedError';
    this.errors = errors;
  }
}

// ============================================
// リトライハンドラー
// ============================================

class RetryHandler {
  constructor(config = {}) {
    this.maxRetries = config.maxRetries || 3;
    this.baseDelay = config.baseDelay || 1000; // ms
    this.maxDelay = config.maxDelay || 60000; // ms
    this.exponentialBase = config.exponentialBase || 2;
    this.jitter = config.jitter !== false; // デフォルトtrue
  }

  /**
   * 指数バックオフ遅延を計算
   */
  calculateDelay(attempt) {
    // 指数バックオフ
    let delay = this.baseDelay * Math.pow(this.exponentialBase, attempt);
    
    // 最大遅延で制限
    delay = Math.min(delay, this.maxDelay);
    
    // ジッター追加（±25%）
    if (this.jitter) {
      const jitterFactor = 0.75 + Math.random() * 0.5;
      delay *= jitterFactor;
    }
    
    return Math.round(delay);
  }

  /**
   * エラーに応じてリトライ可否を判定
   */
  shouldRetry(error, attempt) {
    // 認証エラーは即停止
    if (error instanceof AuthenticationError) {
      console.log(`🔒 認証エラーのためリトライしません`);
      return { shouldRetry: false };
    }

    // LLMRouterErrorのretryableフラグを尊重
    if (error instanceof LLMRouterError && !error.retryable) {
      console.log(`⛔ 非リトライ可能エラー: ${error.message}`);
      return { shouldRetry: false };
    }

    // 最大リトライ回数チェック
    if (attempt >= this.maxRetries) {
      console.log(`🚫 最大リトライ回数(${this.maxRetries})に到達`);
      return { shouldRetry: false };
    }

    // レート制限エラーはRetry-Afterを尊重
    if (error instanceof RateLimitError && error.retryAfter) {
      return { 
        shouldRetry: true, 
        delay: error.retryAfter * 1000 
      };
    }

    // APIエラーのステータスコード判定
    if (error instanceof APIError) {
      if (error.statusCode === 429) {
        return { shouldRetry: true, delay: this.calculateDelay(attempt) };
      }
      if (error.statusCode >= 500) {
        return { shouldRetry: true, delay: this.calculateDelay(attempt) };
      }
      if (error.statusCode >= 400) {
        return { shouldRetry: false }; // クライアントエラー
      }
    }

    // デフォルトはリトライ可能
    return { shouldRetry: true, delay: this.calculateDelay(attempt) };
  }

  /**
   * 関数をリトライ付きで実行
   */
  async execute(operationName, func) {
    let lastError;
    
    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      try {
        if (attempt > 0) {
          console.log(`🔄 ${operationName}: リトライ ${attempt}/${this.maxRetries}`);
        }
        
        const result = await func();
        
        if (attempt > 0) {
          console.log(`✅ ${operationName}: リトライ成功`);
        }
        
        return result;
        
      } catch (error) {
        lastError = error;
        
        const decision = this.shouldRetry(error, attempt);
        
        if (!decision.shouldRetry) {
          throw error;
        }
        
        console.log(`⚠️  ${operationName}: エラー発生 - ${error.message}`);
        console.log(`⏱️  ${decision.delay}ms 待機後リトライ...`);
        
        await this.sleep(decision.delay);
      }
    }
    
    throw lastError;
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// ============================================
// メインルータークラス
// ============================================

class LLMRouter {
  constructor(configPath = './config.yaml') {
    this.config = yaml.load(fs.readFileSync(configPath, 'utf8'));
    this.anthropic = new Anthropic({
      apiKey: process.env.ANTHROPIC_API_KEY
    });
    
    // フォールバック連鎖の設定
    this.fallbackChain = this.config.fallback_chain || {
      primary: { model: 'local', name: 'Local LLM' },
      secondary: { model: 'cloud', name: 'Claude' },
      tertiary: { model: 'cloud_backup', name: 'Claude Backup' }
    };
    
    // リトライハンドラー
    this.retryHandler = new RetryHandler({
      maxRetries: 3,
      baseDelay: 1000,
      maxDelay: 30000
    });
    
    // 統計
    this.stats = {
      total_requests: 0,
      local_used: 0,
      cloud_used: 0,
      total_cost: 0,
      total_saved: 0,
      fallback_count: 0,
      retry_count: 0,
      errors: []
    };
  }

  /**
   * メインルーティング関数（フォールバック連鎖付き）
   */
  async route(input, options = {}) {
    this.stats.total_requests++;
    
    console.log('\n' + '='.repeat(60));
    console.log('🚀 LLM Smart Router 起動');
    console.log('='.repeat(60));
    console.log(`📝 入力: ${input.substring(0, 100)}${input.length > 100 ? '...' : ''}`);
    console.log(`🔗 フォールバック連鎖: Primary → Secondary → Tertiary`);
    console.log('='.repeat(60));

    const errors = [];
    const chain = [
      { key: 'primary', ...this.fallbackChain.primary },
      { key: 'secondary', ...this.fallbackChain.secondary },
      { key: 'tertiary', ...this.fallbackChain.tertiary }
    ];

    // フォールバック連鎖を実行
    for (let i = 0; i < chain.length; i++) {
      const modelConfig = chain[i];
      const level = ['🥇 Primary', '🥈 Secondary', '🥉 Tertiary'][i];
      
      try {
        console.log(`\n${level}: ${modelConfig.name} で実行試行...`);
        
        const result = await this.executeWithRetry(modelConfig, input, options);
        
        if (i > 0) {
          this.stats.fallback_count++;
          console.log(`✅ フォールバック成功 (${modelConfig.name})`);
        }
        
        return {
          ...result,
          metadata: {
            ...result.metadata,
            fallback_used: i > 0,
            fallback_level: i
          }
        };
        
      } catch (error) {
        console.error(`❌ ${modelConfig.name} 失敗: ${error.message}`);
        
        errors.push({
          model: modelConfig.name,
          level: i,
          error: error.message,
          error_type: error.name || 'Unknown',
          error_code: error.errorCode || 'UNKNOWN'
        });
        
        // 次のモデルへフォールバック
        if (i < chain.length - 1) {
          console.log(`🔄 ${chain[i+1].name} へフォールバック...`);
        }
      }
    }

    // すべてのモデルが失敗
    console.error('\n' + '!'.repeat(60));
    console.error('🚨 すべてのモデルで処理に失敗しました');
    console.error('!'.repeat(60));
    
    // エラー詳細を表示
    errors.forEach((e, idx) => {
      console.error(`  ${idx + 1}. ${e.model}: [${e.error_code}] ${e.error}`);
    });
    
    const allFailedError = new AllModelsFailedError(errors);
    this.stats.errors.push(allFailedError.toDict());
    
    return {
      success: false,
      error: 'すべてのモデルで処理に失敗しました',
      response: '申し訳ございません。現在、すべてのAIモデルが利用できない状態です。しばらく経ってからお試しください。',
      metadata: {
        all_errors: errors,
        timestamp: new Date().toISOString()
      }
    };
  }

  /**
   * リトライ付きモデル実行
   */
  async executeWithRetry(modelConfig, input, options) {
    const operationName = `${modelConfig.name}_request`;
    
    return await this.retryHandler.execute(operationName, async () => {
      return await this.executeModel(modelConfig, input, options);
    });
  }

  /**
   * モデル実行（エラーハンドリング付き）
   */
  async executeModel(modelConfig, input, options) {
    const startTime = Date.now();
    
    try {
      let result;
      
      switch (modelConfig.model) {
        case 'local':
          result = await this.executeLocal(input, options);
          this.stats.local_used++;
          break;
        case 'cloud':
        case 'cloud_backup':
          result = await this.executeClaude(input, options, modelConfig.model);
          this.stats.cloud_used++;
          break;
        default:
          throw new ModelUnavailableError(
            `不明なモデルタイプ: ${modelConfig.model}`,
            modelConfig.model,
            'unknown'
          );
      }
      
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);
      
      // コスト計算
      const cost = this.calculateCost(result, modelConfig.model);
      this.stats.total_cost += cost.total;
      
      // 成功ログ
      console.log(`\n  ✅ 成功 (${elapsed}秒)`);
      console.log(`  📊 トークン: ${result.tokens.input} in / ${result.tokens.output} out`);
      console.log(`  💰 コスト: ¥${cost.total.toFixed(2)}`);
      
      return {
        success: true,
        model: modelConfig.model,
        model_name: modelConfig.name,
        response: result.content,
        metadata: {
          elapsed_seconds: elapsed,
          tokens: result.tokens,
          cost: cost.total,
          timestamp: new Date().toISOString()
        }
      };
      
    } catch (error) {
      // エラーを分類してthrow
      throw this.classifyError(error, modelConfig.model);
    }
  }

  /**
   * エラーを分類
   */
  classifyError(error, modelType) {
    // 既にLLMRouterErrorの場合はそのまま
    if (error instanceof LLMRouterError) {
      return error;
    }
    
    const message = error.message || '';
    
    // 接続エラー
    if (message.includes('ECONNREFUSED') || 
        message.includes('ETIMEDOUT') || 
        message.includes('ENOTFOUND') ||
        message.includes('timeout')) {
      return new ConnectionError(
        `接続エラー: ${message}`,
        modelType === 'local' ? this.config.models.local.endpoint : 'anthropic',
        30000
      );
    }
    
    // レート制限
    if (message.includes('rate limit') || message.includes('429')) {
      return new RateLimitError(
        `レート制限に到達しました: ${message}`,
        60,
        null,
        0,
        modelType
      );
    }
    
    // 認証エラー
    if (message.includes('authentication') || 
        message.includes('unauthorized') || 
        message.includes('401') ||
        message.includes('403')) {
      return new AuthenticationError(
        `認証エラー: ${message}`,
        modelType
      );
    }
    
    // APIエラー（ステータスコード抽出を試行）
    const statusMatch = message.match(/(\d{3})/);
    if (statusMatch) {
      const statusCode = parseInt(statusMatch[1]);
      return new APIError(message, statusCode, modelType, null);
    }
    
    // モデル利用不可
    if (message.includes('model') && (message.includes('not found') || message.includes('unavailable'))) {
      return new ModelUnavailableError(message, modelType, modelType);
    }
    
    // その他は汎用APIエラー
    return new APIError(message, null, modelType, null);
  }

  /**
   * ローカルLLM実行
   */
  async executeLocal(input, options) {
    const config = this.config.models.local;
    
    try {
      const response = await axios.post(
        `${config.endpoint}/chat/completions`,
        {
          model: config.model,
          messages: [{ role: 'user', content: input }],
          temperature: config.temperature,
          max_tokens: config.max_tokens
        },
        { 
          timeout: config.timeout || 30000,
          headers: {
            'Content-Type': 'application/json'
          }
        }
      );
      
      const choice = response.data.choices[0];
      
      return {
        content: choice.message.content,
        tokens: {
          input: response.data.usage?.prompt_tokens || 0,
          output: response.data.usage?.completion_tokens || 0
        }
      };
      
    } catch (error) {
      if (error.response) {
        throw new Error(`Local LLM API error: ${error.response.status} - ${JSON.stringify(error.response.data)}`);
      }
      throw error;
    }
  }

  /**
   * Claude実行
   */
  async executeClaude(input, options, modelVariant = 'cloud') {
    const config = this.config.models.cloud;
    
    // バックアップモデルの場合は異なるモデル名を使用
    const modelName = modelVariant === 'cloud_backup' 
      ? 'claude-3-haiku-20240307'  // バックアップは軽量モデル
      : config.model;
    
    try {
      const message = await this.anthropic.messages.create({
        model: modelName,
        max_tokens: config.max_tokens,
        temperature: config.temperature,
        messages: [{ role: 'user', content: input }]
      });
      
      return {
        content: message.content[0].text,
        tokens: {
          input: message.usage.input_tokens,
          output: message.usage.output_tokens
        }
      };
      
    } catch (error) {
      if (error.status) {
        throw new Error(`Claude API error: ${error.status} - ${error.message}`);
      }
      throw error;
    }
  }

  /**
   * コスト計算
   */
  calculateCost(result, modelType) {
    if (modelType === 'local') {
      return { input: 0, output: 0, total: 0 };
    }
    
    const pricing = this.config.cost?.pricing || {
      claude_sonnet_input: 3.0,
      claude_sonnet_output: 15.0
    };
    
    const inputCost = (result.tokens.input / 1000) * pricing.claude_sonnet_input;
    const outputCost = (result.tokens.output / 1000) * pricing.claude_sonnet_output;
    
    // ドル→円換算（150円/ドル）
    const rate = 150;
    
    return {
      input: inputCost * rate,
      output: outputCost * rate,
      total: (inputCost + outputCost) * rate
    };
  }

  /**
   * 統計表示
   */
  showStats() {
    console.log('\n' + '='.repeat(60));
    console.log('📊 統計情報');
    console.log('='.repeat(60));
    console.log(`総リクエスト: ${this.stats.total_requests}`);
    console.log(`ローカル使用: ${this.stats.local_used} (${this.getPercentage(this.stats.local_used)}%)`);
    console.log(`Claude使用: ${this.stats.cloud_used} (${this.getPercentage(this.stats.cloud_used)}%)`);
    console.log(`フォールバック発生: ${this.stats.fallback_count}回`);
    console.log(`総コスト: ¥${this.stats.total_cost.toFixed(2)}`);
    console.log(`総節約: ¥${this.stats.total_saved.toFixed(2)}`);
    
    if (this.stats.errors.length > 0) {
      console.log(`\n⚠️  エラー履歴: ${this.stats.errors.length}件`);
    }
    
    console.log('='.repeat(60));
  }

  getPercentage(count) {
    if (this.stats.total_requests === 0) return 0;
    return ((count / this.stats.total_requests) * 100).toFixed(1);
  }
}

// ============================================
// エクスポート
// ============================================

export default LLMRouter;
export {
  LLMRouterError,
  APIError,
  ConnectionError,
  RateLimitError,
  ModelUnavailableError,
  AuthenticationError,
  AllModelsFailedError,
  RetryHandler
};

// ============================================
// CLI実行
// ============================================

const __filename = fileURLToPath(import.meta.url);
if (process.argv[1] && path.resolve(__filename) === path.resolve(process.argv[1])) {
  const router = new LLMRouter();
  const input = process.argv.slice(2).join(' ');
  
  if (!input) {
    console.log('Usage: node router.js <your question>');
    console.log('');
    console.log('Features:');
    console.log('  - 3-tier fallback chain (Primary → Secondary → Tertiary)');
    console.log('  - Exponential backoff retry (max 3 attempts)');
    console.log('  - Detailed error classification and logging');
    process.exit(1);
  }
  
  router.route(input).then(result => {
    console.log('\n' + '='.repeat(60));
    console.log('📄 最終応答:\n');
    console.log(result.response);
    console.log('='.repeat(60));
    
    if (result.metadata?.fallback_used) {
      console.log(`\n⚠️  フォールバック使用: ${['Primary', 'Secondary', 'Tertiary'][result.metadata.fallback_level]}`);
    }
    
    router.showStats();
    
    // エラーがあれば非ゼロ終了
    if (!result.success) {
      process.exit(1);
    }
    
  }).catch(error => {
    console.error('Unexpected error:', error);
    process.exit(1);
  });
}
