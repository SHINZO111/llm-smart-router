#!/usr/bin/env node
/**
 * LLM Smart Router - Intelligent routing between Local LLM and Claude
 * Author: クラ for 新さん
 */

import fs from 'fs';
import yaml from 'js-yaml';
import axios from 'axios';
import Anthropic from '@anthropic-ai/sdk';
import { fileURLToPath } from 'url';
import path from 'path';

class LLMRouter {
  constructor(configPath = './config.yaml') {
    this.config = yaml.load(fs.readFileSync(configPath, 'utf8'));
    this.anthropic = new Anthropic({
      apiKey: process.env.ANTHROPIC_API_KEY
    });
    this.stats = {
      total_requests: 0,
      local_used: 0,
      cloud_used: 0,
      total_cost: 0,
      total_saved: 0
    };
  }

  /**
   * メインルーティング関数
   */
  async route(input, options = {}) {
    this.stats.total_requests++;
    
    console.log('\n🔄 Smart Router 起動...');
    console.log(`📝 入力: ${input.substring(0, 100)}${input.length > 100 ? '...' : ''}`);
    
    try {
      // Phase 1: Hard Rules チェック
      const hardRule = this.checkHardRules(input);
      if (hardRule) {
        console.log(`\n⚡ 確定ルール適用: ${hardRule.name}`);
        console.log(`📌 理由: ${hardRule.reason}`);
        return await this.executeWithModel(hardRule.model, input, hardRule);
      }
      
      // Phase 2: Intelligent Routing
      if (this.config.routing.intelligent_routing.enabled) {
        const decision = await this.intelligentTriage(input);
        console.log(`\n🧠 AI判定結果:`);
        console.log(`   モデル: ${decision.model}`);
        console.log(`   確信度: ${(decision.confidence * 100).toFixed(1)}%`);
        console.log(`   理由: ${decision.reason}`);
        
        // 確信度が低い場合はClaudeへ
        const threshold = this.config.routing.intelligent_routing.confidence_threshold;
        if (decision.model === 'local' && decision.confidence < threshold) {
          console.log(`\n⚠️  確信度が低いため、Claudeに切り替えます`);
          return await this.executeWithModel('cloud', input, decision);
        }
        
        return await this.executeWithModel(decision.model, input, decision);
      }
      
      // Phase 3: Default (fallback)
      console.log(`\n📍 デフォルトモデル使用: ${this.config.default}`);
      return await this.executeWithModel(this.config.default, input, { reason: 'デフォルト' });
      
    } catch (error) {
      console.error(`\n❌ エラー: ${error.message}`);
      return await this.handleError(error, input);
    }
  }

  /**
   * Hard Rules チェック
   */
  checkHardRules(input) {
    if (!this.config.routing.hard_rules) return null;
    
    for (const rule of this.config.routing.hard_rules) {
      for (const trigger of rule.triggers) {
        if (input.includes(trigger)) {
          return rule;
        }
      }
    }
    return null;
  }

  /**
   * インテリジェント判定（ローカルLLMで判定）
   */
  async intelligentTriage(input) {
    const triageConfig = this.config.routing.intelligent_routing;
    const prompt = triageConfig.triage_prompt.replace('{input}', input);
    
    console.log(`\n🔍 ローカルLLMで判定中...`);
    
    try {
      const response = await axios.post(
        `${this.config.models.local.endpoint}/chat/completions`,
        {
          model: this.config.models.local.model,
          messages: [{ role: 'user', content: prompt }],
          temperature: 0.3,
          max_tokens: 200
        },
        { timeout: 10000 }
      );
      
      const content = response.data.choices[0].message.content;
      
      // JSON抽出
      const jsonMatch = content.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        return JSON.parse(jsonMatch[0]);
      }
      
      // JSONが取れなかった場合はパース試行
      if (content.includes('cloud') || content.includes('complex')) {
        return { model: 'cloud', confidence: 0.8, reason: '複雑タスクと判定' };
      } else {
        return { model: 'local', confidence: 0.8, reason: '単純タスクと判定' };
      }
      
    } catch (error) {
      console.warn(`⚠️  判定失敗、デフォルト判定使用`);
      // 判定失敗時は安全側（local）に倒す
      return { model: 'local', confidence: 0.5, reason: '判定失敗（デフォルト）' };
    }
  }

  /**
   * モデル実行
   */
  async executeWithModel(modelType, input, context = {}) {
    const startTime = Date.now();
    
    console.log(`\n${'='.repeat(60)}`);
    console.log(`🚀 実行: ${modelType.toUpperCase()} モデル`);
    console.log(`${'='.repeat(60)}`);
    
    try {
      let result;
      
      if (modelType === 'local') {
        result = await this.executeLocal(input);
        this.stats.local_used++;
      } else {
        result = await this.executeClaude(input);
        this.stats.cloud_used++;
      }
      
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
      
      // コスト計算
      const cost = this.calculateCost(result, modelType);
      this.stats.total_cost += cost.total;
      
      // 統計表示
      console.log(`\n${'─'.repeat(60)}`);
      console.log(`✅ 完了`);
      console.log(`⏱️  処理時間: ${elapsed}秒`);
      console.log(`📊 トークン: ${result.tokens.input} in / ${result.tokens.output} out`);
      console.log(`💰 コスト: ¥${cost.total.toFixed(2)}`);
      
      if (modelType === 'local') {
        const savedCost = this.calculateCost(result, 'cloud').total;
        this.stats.total_saved += savedCost;
        console.log(`💵 節約: ¥${savedCost.toFixed(2)} (ローカル使用)`);
      }
      
      console.log(`${'─'.repeat(60)}\n`);
      
      return {
        model: modelType,
        response: result.content,
        metadata: {
          elapsed,
          tokens: result.tokens,
          cost: cost.total,
          context
        }
      };
      
    } catch (error) {
      throw new Error(`${modelType} execution failed: ${error.message}`);
    }
  }

  /**
   * ローカルLLM実行
   */
  async executeLocal(input) {
    const config = this.config.models.local;
    
    const response = await axios.post(
      `${config.endpoint}/chat/completions`,
      {
        model: config.model,
        messages: [{ role: 'user', content: input }],
        temperature: config.temperature,
        max_tokens: config.max_tokens
      },
      { timeout: config.timeout }
    );
    
    const choice = response.data.choices[0];
    
    return {
      content: choice.message.content,
      tokens: {
        input: response.data.usage?.prompt_tokens || 0,
        output: response.data.usage?.completion_tokens || 0
      }
    };
  }

  /**
   * Claude実行
   */
  async executeClaude(input) {
    const config = this.config.models.cloud;
    
    const message = await this.anthropic.messages.create({
      model: config.model,
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
  }

  /**
   * コスト計算
   */
  calculateCost(result, modelType) {
    if (modelType === 'local') {
      return { input: 0, output: 0, total: 0 };
    }
    
    const pricing = this.config.cost.pricing;
    const inputCost = (result.tokens.input / 1000) * pricing.claude_sonnet_input;
    const outputCost = (result.tokens.output / 1000) * pricing.claude_sonnet_output;
    
    // ドル→円換算（仮に150円/ドル）
    const rate = 150;
    
    return {
      input: inputCost * rate,
      output: outputCost * rate,
      total: (inputCost + outputCost) * rate
    };
  }

  /**
   * エラーハンドリング
   */
  async handleError(error, input) {
    console.error(`\n🚨 エラー発生: ${error.message}`);
    
    const fallback = this.config.fallback;
    
    if (error.message.includes('local')) {
      if (fallback.local_failure.action === 'switch_to_cloud') {
        console.log(`\n🔄 Claudeにフォールバック...`);
        return await this.executeWithModel('cloud', input, { 
          reason: 'ローカルLLM障害によるフォールバック' 
        });
      }
    }
    
    throw error;
  }

  /**
   * 統計表示
   */
  showStats() {
    console.log(`\n${'='.repeat(60)}`);
    console.log(`📊 統計情報`);
    console.log(`${'='.repeat(60)}`);
    console.log(`総リクエスト: ${this.stats.total_requests}`);
    console.log(`ローカル使用: ${this.stats.local_used} (${(this.stats.local_used/this.stats.total_requests*100).toFixed(1)}%)`);
    console.log(`Claude使用: ${this.stats.cloud_used} (${(this.stats.cloud_used/this.stats.total_requests*100).toFixed(1)}%)`);
    console.log(`総コスト: ¥${this.stats.total_cost.toFixed(2)}`);
    console.log(`総節約: ¥${this.stats.total_saved.toFixed(2)}`);
    console.log(`${'='.repeat(60)}\n`);
  }
}

// Export
export default LLMRouter;

// CLI実行時
const __filename = fileURLToPath(import.meta.url);
if (process.argv[1] && path.resolve(__filename) === path.resolve(process.argv[1])) {
  const router = new LLMRouter();
  const input = process.argv.slice(2).join(' ');
  
  if (!input) {
    console.log('Usage: node router.js <your question>');
    process.exit(1);
  }
  
  router.route(input).then(result => {
    console.log('\n📄 応答:\n');
    console.log(result.response);
    console.log('\n');
    router.showStats();
  }).catch(error => {
    console.error('Error:', error);
    process.exit(1);
  });
}
