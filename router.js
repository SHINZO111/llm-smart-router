#!/usr/bin/env node
/**
 * LLM Smart Router - Intelligent routing between Local LLM and Claude
 * Author: クラ for 新さん
 * Version: 4.0.0 - Added Vision support
 */

import fs from 'fs';
import yaml from 'js-yaml';
import axios from 'axios';
import Anthropic from '@anthropic-ai/sdk';
import { fileURLToPath } from 'url';
import path from 'path';
import { spawn } from 'child_process';

/**
 * Conversation History Manager - Python DB Handler Integration
 * Manages automatic saving of conversations to SQLite database
 */
class ConversationHistoryManager {
  constructor(dbPath = './data/conversations.db') {
    this.dbPath = dbPath;
    this.currentConversationId = null;
    this.dbScriptPath = path.join(process.cwd(), 'src/conversation/db_manager.py');
  }

  /**
   * Pythonサブプロセスをstdin経由でJSON実行（インジェクション防止）
   */
  _runPython(script) {
    return new Promise((resolve, reject) => {
      const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
      const proc = spawn(pythonCmd, ['-c', script], { cwd: process.cwd() });
      let output = '';
      let error = '';

      proc.stdout.on('data', (data) => { output += data.toString(); });
      proc.stderr.on('data', (data) => { error += data.toString(); });

      proc.on('error', (err) => {
        reject(new Error(`Python process spawn failed: ${err.message}`));
      });

      proc.on('close', (code) => {
        if (code !== 0) {
          reject(new Error(error || `Python exited with code ${code}`));
        } else {
          resolve(output.trim());
        }
      });
    });
  }

  /**
   * Initialize a new conversation or get existing one
   */
  async initConversation(title = 'New Conversation', topicId = null) {
    const safeTitle = JSON.stringify(title);
    const safeTopic = topicId != null ? String(Number(topicId)) : 'None';
    const safeDbPath = JSON.stringify(this.dbPath);

    const script = `
import sys, json
sys.path.insert(0, 'src/conversation')
from db_manager import get_db

db = get_db(${safeDbPath})
conv_id = db.create_conversation(${safeTitle}, ${safeTopic})
print(conv_id)
    `.trim();

    try {
      const output = await this._runPython(script);
      this.currentConversationId = parseInt(output);
      console.log(`📝 Conversation initialized: #${this.currentConversationId}`);
      return this.currentConversationId;
    } catch (error) {
      console.warn('⚠️  DB initialization failed:', error.message);
      return null;
    }
  }

  /**
   * Save a message to the current conversation
   */
  async saveMessage(role, content, model = null) {
    if (!this.currentConversationId) {
      await this.initConversation();
    }

    // パラメータをJSON経由でPythonに安全に渡す
    const params = JSON.stringify({
      db_path: this.dbPath,
      conversation_id: this.currentConversationId,
      role: role,
      content: content,
      model: model,
    });

    const script = `
import sys, json
sys.path.insert(0, 'src/conversation')
from db_manager import get_db

params = json.loads(${JSON.stringify(params)})
db = get_db(params['db_path'])
msg_id = db.add_message(
    conversation_id=params['conversation_id'],
    role=params['role'],
    content=params['content'],
    model=params.get('model')
)
print(msg_id)
    `.trim();

    try {
      const output = await this._runPython(script);
      console.log(`💾 Message saved: ${role} (${output})`);
      return parseInt(output);
    } catch (error) {
      console.warn('⚠️  Failed to save message:', error.message);
      return null;
    }
  }

  /**
   * Auto-save hook - Call after message exchange
   */
  async autoSave(userInput, assistantResponse, modelUsed) {
    try {
      // Save user message
      await this.saveMessage('user', userInput, null);

      // Save assistant message
      await this.saveMessage('assistant', assistantResponse, modelUsed);

      console.log('💾 Conversation auto-saved');
      return true;
    } catch (error) {
      console.warn('⚠️  Auto-save failed:', error.message);
      return false;
    }
  }

  /**
   * Update conversation title
   */
  async updateTitle(title) {
    if (!this.currentConversationId) return;

    const params = JSON.stringify({
      db_path: this.dbPath,
      conversation_id: this.currentConversationId,
      title: title,
    });

    const script = `
import sys, json
sys.path.insert(0, 'src/conversation')
from db_manager import get_db

params = json.loads(${JSON.stringify(params)})
db = get_db(params['db_path'])
db.update_conversation(params['conversation_id'], title=params['title'])
print('OK')
    `.trim();

    try {
      await this._runPython(script);
      return true;
    } catch (error) {
      console.warn('⚠️  Failed to update title:', error.message);
      return false;
    }
  }

  /**
   * Get conversation history
   */
  async getHistory(limit = 50) {
    if (!this.currentConversationId) return [];

    const safeDbPath = JSON.stringify(this.dbPath);
    const safeConvId = Number(this.currentConversationId);
    const safeLimit = Number(limit);

    const script = `
import sys, json
sys.path.insert(0, 'src/conversation')
from db_manager import get_db

db = get_db(${safeDbPath})
messages = db.get_messages(${safeConvId}, limit=${safeLimit})
print(json.dumps(messages))
    `.trim();

    try {
      const output = await this._runPython(script);
      return JSON.parse(output);
    } catch (error) {
      console.warn('⚠️  Failed to get history:', error.message);
      return [];
    }
  }

  /**
   * Export current conversation to JSON
   */
  async exportToJson(filepath) {
    if (!this.currentConversationId) return null;

    const params = JSON.stringify({
      filepath: filepath,
      conversation_ids: [this.currentConversationId],
    });

    const script = `
import sys, json
sys.path.insert(0, 'src/conversation')
from json_handler import ConversationJSONHandler

params = json.loads(${JSON.stringify(params)})
handler = ConversationJSONHandler()
result = handler.export_to_file(params['filepath'], conversation_ids=params['conversation_ids'])
print(result)
    `.trim();

    try {
      return await this._runPython(script);
    } catch (error) {
      console.warn('⚠️  Failed to export:', error.message);
      return null;
    }
  }
}

class LLMRouter {
  constructor(configPath = './config.yaml') {
    try {
      this.config = yaml.load(fs.readFileSync(configPath, 'utf8'));
    } catch (error) {
      throw new Error(`設定ファイル読み込み失敗 (${configPath}): ${error.message}`);
    }
    this.anthropic = new Anthropic({
      apiKey: process.env.ANTHROPIC_API_KEY
    });
    this.stats = {
      total_requests: 0,
      local_used: 0,
      cloud_used: 0,
      total_cost: 0,
      total_saved: 0,
      vision_requests: 0
    };
    
    // Initialize conversation history manager
    this.history = new ConversationHistoryManager(
      this.config.database?.path || './data/conversations.db'
    );
    
    // Vision対応モデル設定
    this.visionModels = {
      claude: {
        primary: 'claude-3-5-sonnet-20241022',
        fallback: 'claude-3-opus-20240229',
        max_tokens: 4096
      },
      openai: {
        primary: 'gpt-4o',
        fallback: 'gpt-4o-mini',
        max_tokens: 4096
      }
    };
  }

  /**
   * メインルーティング関数
   */
  async route(input, options = {}) {
    this.stats.total_requests++;
    
    console.log('\n🔄 Smart Router 起動...');
    console.log(`📝 入力: ${input.substring(0, 100)}${input.length > 100 ? '...' : ''}`);
    
    // 画像がある場合はVisionタスク
    if (options.imagePath || options.imageBase64) {
      this.stats.vision_requests++;
      console.log(`🖼️ 画像検出: Visionモード`);
      const result = await this.routeVision(input, options);
      
      // Auto-save Vision conversation
      await this.history.autoSave(input, result.response, result.model);
      
      return result;
    }
    
    try {
      // Phase 1: Hard Rules チェック
      const hardRule = this.checkHardRules(input);
      if (hardRule) {
        console.log(`\n⚡ 確定ルール適用: ${hardRule.name}`);
        console.log(`📌 理由: ${hardRule.reason}`);
        const result = await this.executeWithModel(hardRule.model, input, hardRule);
        
        // Auto-save after successful response
        await this.history.autoSave(input, result.response, result.model);
        
        return result;
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
        let result;
        if (decision.model === 'local' && decision.confidence < threshold) {
          console.log(`\n⚠️  確信度が低いため、Claudeに切り替えます`);
          result = await this.executeWithModel('cloud', input, decision);
        } else {
          result = await this.executeWithModel(decision.model, input, decision);
        }
        
        // Auto-save after successful response
        await this.history.autoSave(input, result.response, result.model);
        
        return result;
      }
      
      // Phase 3: Default (fallback)
      console.log(`\n📍 デフォルトモデル使用: ${this.config.default}`);
      const result = await this.executeWithModel(this.config.default, input, { reason: 'デフォルト' });
      
      // Auto-save after successful response
      await this.history.autoSave(input, result.response, result.model);
      
      return result;
      
    } catch (error) {
      console.error(`\n❌ エラー: ${error.message}`);
      return await this.handleError(error, input);
    }
  }

  /**
   * Visionタスクのルーティング
   * 画像ありの場合はVision対応モデルを自動選択
   */
  async routeVision(input, options) {
    console.log('\n🎯 Vision Routing...');
    
    // Vision対応モデルを選択（Claude優先、GPT-4oフォールバック）
    const visionModel = this.selectVisionModel();
    console.log(`📷 Vision Model: ${visionModel.provider} - ${visionModel.model}`);
    
    try {
      if (visionModel.provider === 'claude') {
        return await this.executeClaudeVision(input, options, visionModel.model);
      } else {
        return await this.executeOpenAIVision(input, options, visionModel.model);
      }
    } catch (error) {
      console.error(`\n❌ Visionエラー: ${error.message}`);
      // フォールバック
      const fallbackModel = visionModel.provider === 'claude' 
        ? { provider: 'openai', model: this.visionModels.openai.primary }
        : { provider: 'claude', model: this.visionModels.claude.primary };
      
      console.log(`🔄 フォールバック: ${fallbackModel.provider}`);
      
      if (fallbackModel.provider === 'claude') {
        return await this.executeClaudeVision(input, options, fallbackModel.model);
      } else {
        return await this.executeOpenAIVision(input, options, fallbackModel.model);
      }
    }
  }

  /**
   * Vision対応モデルを選択
   * 優先順位: Claude > GPT-4o
   */
  selectVisionModel() {
    const claudeKey = process.env.ANTHROPIC_API_KEY;
    const openaiKey = process.env.OPENAI_API_KEY;
    
    // Claudeが優先
    if (claudeKey) {
      return {
        provider: 'claude',
        model: this.visionModels.claude.primary
      };
    }
    
    // フォールバック: GPT-4o
    if (openaiKey) {
      return {
        provider: 'openai',
        model: this.visionModels.openai.primary
      };
    }
    
    // どちらもない場合はClaudeをデフォルトとして返す（エラーになるが明示的に）
    return {
      provider: 'claude',
      model: this.visionModels.claude.primary
    };
  }

  /**
   * Claude Vision API実行
   */
  async executeClaudeVision(input, options, model) {
    const startTime = Date.now();
    
    console.log(`\n${'='.repeat(60)}`);
    console.log(`🚀 Claude Vision実行: ${model}`);
    console.log(`${'='.repeat(60)}`);
    
    // 画像を読み込み
    let imageBase64;
    let mediaType = 'image/jpeg';
    
    if (options.imageBase64) {
      imageBase64 = options.imageBase64;
    } else if (options.imagePath && fs.existsSync(options.imagePath)) {
      const imageData = fs.readFileSync(options.imagePath);
      imageBase64 = imageData.toString('base64');
      // ファイル拡張子からMIMEタイプを推定
      const ext = path.extname(options.imagePath).toLowerCase();
      mediaType = this.getMimeType(ext);
    } else {
      throw new Error('No image data provided');
    }
    
    const message = await this.anthropic.messages.create({
      model: model,
      max_tokens: this.visionModels.claude.max_tokens,
      temperature: 0.7,
      messages: [{
        role: 'user',
        content: [
          {
            type: 'image',
            source: {
              type: 'base64',
              media_type: mediaType,
              data: imageBase64
            }
          },
          {
            type: 'text',
            text: input || 'この画像について説明してください。'
          }
        ]
      }]
    });
    
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    
    // コスト計算（Visionは通常の1.5倍程度）
    const cost = this.calculateVisionCost(message.usage, 'claude');
    this.stats.total_cost += cost.total;
    this.stats.cloud_used++;
    
    console.log(`\n${'─'.repeat(60)}`);
    console.log(`✅ Vision完了 (Claude)`);
    console.log(`⏱️  処理時間: ${elapsed}秒`);
    console.log(`📊 トークン: ${message.usage.input_tokens} in / ${message.usage.output_tokens} out`);
    console.log(`💰 コスト: ¥${cost.total.toFixed(2)}`);
    console.log(`${'─'.repeat(60)}\n`);
    
    return {
      model: `claude-vision-${model}`,
      response: message.content[0].text,
      metadata: {
        elapsed,
        tokens: {
          input: message.usage.input_tokens,
          output: message.usage.output_tokens
        },
        cost: cost.total,
        provider: 'claude',
        vision: true
      }
    };
  }

  /**
   * OpenAI Vision API実行 (GPT-4o)
   */
  async executeOpenAIVision(input, options, model) {
    const startTime = Date.now();
    const apiKey = process.env.OPENAI_API_KEY;
    
    if (!apiKey) {
      throw new Error('OpenAI API key not found');
    }
    
    console.log(`\n${'='.repeat(60)}`);
    console.log(`🚀 GPT-4o Vision実行: ${model}`);
    console.log(`${'='.repeat(60)}`);
    
    // 画像を読み込み
    let imageBase64;
    let mediaType = 'image/jpeg';
    
    if (options.imageBase64) {
      imageBase64 = options.imageBase64;
    } else if (options.imagePath && fs.existsSync(options.imagePath)) {
      const imageData = fs.readFileSync(options.imagePath);
      imageBase64 = imageData.toString('base64');
      const ext = path.extname(options.imagePath).toLowerCase();
      mediaType = this.getMimeType(ext);
    } else {
      throw new Error('No image data provided');
    }
    
    const response = await axios.post(
      'https://api.openai.com/v1/chat/completions',
      {
        model: model,
        max_tokens: this.visionModels.openai.max_tokens,
        temperature: 0.7,
        messages: [{
          role: 'user',
          content: [
            {
              type: 'text',
              text: input || 'この画像について説明してください。'
            },
            {
              type: 'image_url',
              image_url: {
                url: `data:${mediaType};base64,${imageBase64}`,
                detail: 'auto'
              }
            }
          ]
        }]
      },
      {
        headers: {
          'Authorization': `Bearer ${apiKey}`,
          'Content-Type': 'application/json'
        },
        timeout: 120000
      }
    );
    
    const result = response.data;
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    
    const tokens = {
      input: result.usage?.prompt_tokens || 0,
      output: result.usage?.completion_tokens || 0
    };
    
    const cost = this.calculateVisionCost(tokens, 'openai');
    this.stats.total_cost += cost.total;
    this.stats.cloud_used++;
    
    console.log(`\n${'─'.repeat(60)}`);
    console.log(`✅ Vision完了 (GPT-4o)`);
    console.log(`⏱️  処理時間: ${elapsed}秒`);
    console.log(`📊 トークン: ${tokens.input} in / ${tokens.output} out`);
    console.log(`💰 コスト: ¥${cost.total.toFixed(2)}`);
    console.log(`${'─'.repeat(60)}\n`);
    
    return {
      model: `gpt-vision-${model}`,
      response: result.choices?.[0]?.message?.content || '',
      metadata: {
        elapsed,
        tokens,
        cost: cost.total,
        provider: 'openai',
        vision: true
      }
    };
  }

  /**
   * MIMEタイプ取得
   */
  getMimeType(ext) {
    const mapping = {
      '.jpg': 'image/jpeg',
      '.jpeg': 'image/jpeg',
      '.png': 'image/png',
      '.gif': 'image/gif',
      '.webp': 'image/webp',
      '.bmp': 'image/bmp'
    };
    return mapping[ext] || 'image/jpeg';
  }

  /**
   * Visionコスト計算
   */
  calculateVisionCost(usage, provider) {
    const rate = 150; // ドル→円
    
    if (provider === 'claude') {
      // Claude 3.5 Sonnet Vision
      const inputCost = (usage.input_tokens / 1000) * 3.0; // $3/M tokens
      const outputCost = (usage.output_tokens / 1000) * 15.0; // $15/M tokens
      return {
        input: inputCost * rate,
        output: outputCost * rate,
        total: (inputCost + outputCost) * rate
      };
    } else {
      // GPT-4o Vision
      const inputCost = (usage.input_tokens / 1000) * 5.0; // $5/M tokens
      const outputCost = (usage.output_tokens / 1000) * 15.0; // $15/M tokens
      return {
        input: inputCost * rate,
        output: outputCost * rate,
        total: (inputCost + outputCost) * rate
      };
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
      
      const choices = response.data.choices;
      if (!choices || !choices[0]) {
        throw new Error('Local LLM returned empty response');
      }
      const content = choices[0].message.content;

      // JSON抽出
      const jsonMatch = content.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        try {
          return JSON.parse(jsonMatch[0]);
        } catch (parseError) {
          console.warn('⚠️  JSON解析失敗、テキスト解析に切り替え');
        }
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
    
    const choices = response.data.choices;
    if (!choices || !choices[0]) {
      throw new Error('Local LLM returned empty choices');
    }
    const choice = choices[0];

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

    if (!message.content || !message.content[0]) {
      throw new Error('Claude returned empty content');
    }

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
    console.log(`Visionリクエスト: ${this.stats.vision_requests}`);
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
  
  // コマンドライン引数の解析
  const args = process.argv.slice(2);
  let input = '';
  let imagePath = null;
  let imageBase64 = null;
  let modelType = null;
  
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--image' && i + 1 < args.length) {
      imagePath = args[i + 1];
      i++;
    } else if (args[i] === '--model' && i + 1 < args.length) {
      modelType = args[i + 1];
      i++;
    } else if (args[i] === '--base64' && i + 1 < args.length) {
      imageBase64 = args[i + 1];
      i++;
    } else if (!input) {
      input = args[i];
    }
  }
  
  if (!input && !imagePath && !imageBase64) {
    console.log('Usage: node router.js <your question> [--image <path>] [--model <model>]');
    console.log('');
    console.log('Options:');
    console.log('  --image <path>   Image file path');
    console.log('  --base64 <data>  Base64 encoded image');
    console.log('  --model <model>  Model type (auto/local/claude)');
    process.exit(1);
  }
  
  const options = {};
  if (imagePath) options.imagePath = imagePath;
  if (imageBase64) options.imageBase64 = imageBase64;
  if (modelType) options.modelType = modelType;
  
  router.route(input, options).then(result => {
    console.log('\n📄 応答:\n');
    console.log(result.response);
    console.log('\n');
    router.showStats();
  }).catch(error => {
    console.error('Error:', error);
    process.exit(1);
  });
}
