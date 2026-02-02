#!/usr/bin/env node
/**
 * OpenClaw統合モジュール
 * OpenClawのカスタムツールとして使用可能
 */

import LLMRouter from './router.js';
import { fileURLToPath } from 'url';
import path from 'path';

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
      });
      break;
    
    case 'claude':
      integration.invoke({ input, forceModel: 'cloud' }).then(r => {
        console.log(r.response);
      });
      break;
    
    case 'stats':
      console.log(integration.getStats());
      break;
    
    default:
      integration.invoke({ input: process.argv.slice(2).join(' ') }).then(r => {
        console.log(r.response);
      });
  }
}
