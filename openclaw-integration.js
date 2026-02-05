#!/usr/bin/env node
/**
 * OpenClaw統合モジュール
 * OpenClawのカスタムツールとして使用可能
 */

import LLMRouter from './router.js';
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';
import os from 'os';

// 定数
const APP_NAME = 'llm-smart-router';
const VALID_COMMANDS = ['query', 'scan', 'stats', 'models', 'reload'];

class OpenClawLLMRouter {
  constructor() {
    this.router = new LLMRouter();
  }

  /**
   * OpenClaw tool interface
   */
  async invoke({ input, forceModel = null, showStats = false }) {
    try {
      let result;
      
      if (forceModel) {
        // モデル指定あり
        result = await this.router.executeWithModel(forceModel, input, {
          reason: 'ユーザー指定'
        });
      } else {
        // 自動判定
        result = await this.router.route(input);
      }
      
      // 統計表示
      if (showStats) {
        this.router.showStats();
      }
      
      return {
        success: true,
        model: result.model,
        response: result.response,
        metadata: result.metadata
      };
      
    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  }

  /**
   * Discord Botから呼ばれる想定
   */
  async handleDiscordMessage(message, userId) {
    const input = message.content;
    
    // 特殊コマンド処理
    if (input.startsWith('!local ')) {
      return await this.invoke({ 
        input: input.replace('!local ', ''), 
        forceModel: 'local' 
      });
    }
    
    if (input.startsWith('!claude ')) {
      return await this.invoke({ 
        input: input.replace('!claude ', ''), 
        forceModel: 'cloud' 
      });
    }
    
    if (input === '!stats') {
      this.router.showStats();
      return { 
        success: true, 
        response: '統計を表示しました' 
      };
    }
    
    // 通常処理（自動判定）
    return await this.invoke({ input });
  }

  /**
   * セッション統計取得
   */
  getStats() {
    return this.router.stats;
  }

  /**
   * 設定リロード
   */
  reloadConfig() {
    this.router = new LLMRouter();
    return { success: true, message: '設定をリロードしました' };
  }

  /**
   * OpenClaw設定ファイルを検索
   */
  _findOpenClawConfig() {
    const candidates = [
      path.join(os.homedir(), '.openclaw', 'config.json'),
      path.join(os.homedir(), '.config', 'openclaw', 'config.json'),
      path.join(process.cwd(), '.openclaw', 'config.json'),
    ];

    for (const configPath of candidates) {
      if (fs.existsSync(configPath)) {
        return configPath;
      }
    }
    return null;
  }

  /**
   * OpenClaw設定ファイルを読み込み
   */
  _loadOpenClawConfig(configPath) {
    try {
      const data = fs.readFileSync(configPath, 'utf8');
      return JSON.parse(data);
    } catch (error) {
      console.error(`OpenClaw設定読み込み失敗: ${error.message}`);
      return null;
    }
  }

  /**
   * OpenClaw設定ファイルを保存（アトミック書き込み）
   */
  _saveOpenClawConfig(configPath, config) {
    try {
      const dir = path.dirname(configPath);
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }

      const tmpPath = `${configPath}.tmp`;
      fs.writeFileSync(tmpPath, JSON.stringify(config, null, 2), 'utf8');
      fs.renameSync(tmpPath, configPath);
      return true;
    } catch (error) {
      console.error(`OpenClaw設定保存失敗: ${error.message}`);
      return false;
    }
  }

  /**
   * OpenClawのLLM設定を更新
   * @param {string} endpoint - LLMエンドポイント（例: http://localhost:1234/v1）
   * @param {string} modelId - モデルID（例: qwen3-4b）
   */
  updateOpenClawLLM(endpoint, modelId) {
    const configPath = this._findOpenClawConfig();
    if (!configPath) {
      console.warn('OpenClaw設定ファイルが見つかりません');
      return { success: false, message: 'OpenClaw設定ファイルが見つかりません' };
    }

    let config = this._loadOpenClawConfig(configPath);
    if (!config) {
      config = {};
    }

    // LLM設定を更新
    if (!config.llm) {
      config.llm = {};
    }

    config.llm.endpoint = endpoint;
    config.llm.model = modelId;
    config.llm.provider = 'openai';  // OpenAI互換API
    config.llm.updated_at = new Date().toISOString();
    config.llm.updated_by = APP_NAME;

    if (this._saveOpenClawConfig(configPath, config)) {
      console.log(`✅ OpenClaw LLM設定更新: ${modelId} @ ${endpoint}`);
      return { success: true, message: `OpenClaw設定を更新しました: ${modelId}` };
    } else {
      return { success: false, message: 'OpenClaw設定の保存に失敗しました' };
    }
  }

  /**
   * 利用可能なモデル一覧をOpenClaw設定に追加
   * @param {Array} models - モデル情報の配列
   */
  updateOpenClawModels(models) {
    const configPath = this._findOpenClawConfig();
    if (!configPath) {
      return { success: false, message: 'OpenClaw設定ファイルが見つかりません' };
    }

    let config = this._loadOpenClawConfig(configPath);
    if (!config) {
      config = {};
    }

    if (!config.llm) {
      config.llm = {};
    }

    config.llm.available_models = models.map(m => ({
      id: m.id,
      name: m.name || m.id,
      endpoint: m.endpoint,
      runtime: m.runtime?.runtime_type
    }));
    config.llm.models_updated_at = new Date().toISOString();

    if (this._saveOpenClawConfig(configPath, config)) {
      console.log(`✅ OpenClaw利用可能モデル更新: ${models.length}モデル`);
      return { success: true, message: `${models.length}個のモデルを登録しました` };
    } else {
      return { success: false, message: '設定の保存に失敗しました' };
    }
  }

  /**
   * デフォルトOpenClaw設定ファイルを作成
   */
  createDefaultOpenClawConfig() {
    const configPath = path.join(os.homedir(), '.openclaw', 'config.json');
    const config = {
      llm: {
        provider: 'openai',
        endpoint: 'http://localhost:1234/v1',
        model: 'default',
        available_models: []
      },
      created_at: new Date().toISOString(),
      created_by: APP_NAME
    };

    if (this._saveOpenClawConfig(configPath, config)) {
      console.log(`✅ OpenClawデフォルト設定作成: ${configPath}`);
      return { success: true, configPath };
    } else {
      return { success: false, message: '設定ファイルの作成に失敗しました' };
    }
  }

  // ==================== OpenClaw → LLM Smart Router 制御用メソッド ====================

  /**
   * LLM Smart Router APIエンドポイント
   */
  get apiBaseUrl() {
    return process.env.LLM_ROUTER_API_URL || 'http://localhost:8000';
  }

  /**
   * 共通APIコールヘルパー（リトライロジック付き）
   * @private
   */
  async _apiCall(method, path, data = null, timeout = 10000, maxRetries = 3) {
    const axios = (await import('axios')).default;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        const config = {
          timeout,
          headers: { 'Content-Type': 'application/json' }
        };

        const response = method === 'GET'
          ? await axios.get(`${this.apiBaseUrl}${path}`, config)
          : await axios.post(`${this.apiBaseUrl}${path}`, data, config);

        return response.data;

      } catch (error) {
        const isRetryable = error.response?.status >= 500 || error.code === 'ECONNREFUSED' || error.code === 'ETIMEDOUT';
        const isLastAttempt = attempt === maxRetries;

        if (isRetryable && !isLastAttempt) {
          // 指数バックオフでリトライ
          const delay = Math.min(1000 * Math.pow(2, attempt - 1), 5000);
          console.warn(`API call failed [${method} ${path}], retrying in ${delay}ms (attempt ${attempt}/${maxRetries})`);
          await new Promise(resolve => setTimeout(resolve, delay));
          continue;
        }

        // リトライ不可またはリトライ上限
        console.error(`API call failed [${method} ${path}]: ${error.message}`);
        return {
          success: false,
          error: error.response?.data?.detail || error.message
        };
      }
    }
  }

  /**
   * クエリをLLM Smart Routerに送信
   * @param {string} input - クエリテキスト
   * @param {string} forceModel - モデル指定（省略可）
   * @param {object} context - 追加コンテキスト（省略可）
   * @returns {Promise<object>} - ルーター実行結果
   */
  async queryRouter(input, forceModel = null, context = {}) {
    return await this._apiCall('POST', '/router/query', {
      input,
      force_model: forceModel,
      context
    }, 30000, 2);  // 30秒タイムアウト、2回リトライ
  }

  /**
   * ルーター統計を取得
   * @returns {Promise<object>} - 統計情報
   */
  async getRouterStats() {
    return await this._apiCall('GET', '/router/stats', null, 10000, 3);
  }

  /**
   * モデルスキャンをトリガー
   * @returns {Promise<object>} - スキャン結果
   */
  async triggerModelScan() {
    return await this._apiCall('POST', '/models/scan', {}, 10000, 1);  // スキャンはリトライなし
  }

  /**
   * 検出済みモデル一覧を取得
   * @returns {Promise<object>} - モデル一覧
   */
  async getDetectedModels() {
    return await this._apiCall('GET', '/models/detected', null, 10000, 3);
  }

  /**
   * ルーター設定をリロード
   * @returns {Promise<object>} - リロード結果
   */
  async reloadRouterConfig() {
    return await this._apiCall('POST', '/router/config/reload', {}, 10000, 2);
  }

  /**
   * OpenClawカスタムツール用の統合インターフェース
   * OpenClawから直接呼び出される想定
   */
  async controlRouter(command, params = {}) {
    // コマンドホワイトリスト検証
    if (!VALID_COMMANDS.includes(command)) {
      return {
        success: false,
        error: `Invalid command: ${command}. Valid commands: ${VALID_COMMANDS.join(', ')}`
      };
    }

    switch (command) {
      case 'query':
        return await this.queryRouter(params.input, params.forceModel, params.context);

      case 'scan':
        return await this.triggerModelScan();

      case 'stats':
        return await this.getRouterStats();

      case 'models':
        return await this.getDetectedModels();

      case 'reload':
        return await this.reloadRouterConfig();

      default:
        // ホワイトリストチェック後なので到達不可
        return {
          success: false,
          error: `Unknown command: ${command}`
        };
    }
  }
}

// Export
export default OpenClawLLMRouter;

// CLI実行時
const __filename_check = fileURLToPath(import.meta.url);
if (process.argv[1] && path.resolve(__filename_check) === path.resolve(process.argv[1])) {
  const integration = new OpenClawLLMRouter();

  const command = process.argv[2];
  const input = process.argv.slice(3).join(' ');

  switch (command) {
    case 'local':
      integration.invoke({ input, forceModel: 'local' }).then(r => {
        console.log(r.response);
      }).catch(err => {
        console.error('エラー:', err.message);
        process.exit(1);
      });
      break;

    case 'claude':
      integration.invoke({ input, forceModel: 'cloud' }).then(r => {
        console.log(r.response);
      }).catch(err => {
        console.error('エラー:', err.message);
        process.exit(1);
      });
      break;

    case 'stats':
      console.log(integration.getStats());
      break;

    // OpenClaw → LLM Smart Router 制御コマンド
    case 'query':
      integration.queryRouter(input).then(r => {
        console.log(JSON.stringify(r, null, 2));
      }).catch(err => {
        console.error('エラー:', err.message);
        process.exit(1);
      });
      break;

    case 'scan':
      integration.triggerModelScan().then(r => {
        console.log(JSON.stringify(r, null, 2));
      }).catch(err => {
        console.error('エラー:', err.message);
        process.exit(1);
      });
      break;

    case 'models':
      integration.getDetectedModels().then(r => {
        console.log(JSON.stringify(r, null, 2));
      }).catch(err => {
        console.error('エラー:', err.message);
        process.exit(1);
      });
      break;

    case 'router-stats':
      integration.getRouterStats().then(r => {
        console.log(JSON.stringify(r, null, 2));
      }).catch(err => {
        console.error('エラー:', err.message);
        process.exit(1);
      });
      break;

    case 'reload':
      integration.reloadRouterConfig().then(r => {
        console.log(JSON.stringify(r, null, 2));
      }).catch(err => {
        console.error('エラー:', err.message);
        process.exit(1);
      });
      break;

    case 'control':
      // 統合コマンド: node openclaw-integration.js control <command> [params...]
      const subCommand = process.argv[3];
      const params = process.argv[4] ? JSON.parse(process.argv[4]) : {};
      integration.controlRouter(subCommand, params).then(r => {
        console.log(JSON.stringify(r, null, 2));
      }).catch(err => {
        console.error('エラー:', err.message);
        process.exit(1);
      });
      break;

    default:
      integration.invoke({ input: process.argv.slice(2).join(' ') }).then(r => {
        console.log(r.response);
      }).catch(err => {
        console.error('エラー:', err.message);
        process.exit(1);
      });
  }
}
