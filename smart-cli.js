#!/usr/bin/env node
/**
 * Smart CLI - 自然言語でモデル切り替え
 * 使い方:
 *   node smart-cli.js "ローカルLLM使用 質問内容"
 *   node smart-cli.js "Claude使用 質問内容"
 *   node smart-cli.js "質問内容" ← デフォルトはローカル
 */

import LLMRouter from './router.js';

console.log('🧠 Smart CLI 起動...\n');

const router = new LLMRouter();
const input = process.argv.slice(2).join(' ');

if (!input) {
  console.log('使い方:');
  console.log('  node smart-cli.js "質問内容"');
  console.log('  node smart-cli.js "ローカルLLM使用 質問内容"');
  console.log('  node smart-cli.js "Claude使用 質問内容"');
  console.log('\nキーワード:');
  console.log('  - ローカルLLM使用 / ローカル使用 / local');
  console.log('  - Claude使用 / クラウド使用 / cloud');
  process.exit(0);
}

// キーワード検出
const keywords = {
  local: [
    /^ローカルLLM使用\s+/i,
    /^ローカル使用\s+/i,
    /^local\s+/i,
    /^ローカルで\s+/i
  ],
  cloud: [
    /^Claude使用\s+/i,
    /^クラウド使用\s+/i,
    /^cloud\s+/i,
    /^Claudeで\s+/i
  ]
};

let forceModel = null;
let actualInput = input;

// ローカル指定チェック
for (const pattern of keywords.local) {
  if (pattern.test(input)) {
    forceModel = 'local';
    actualInput = input.replace(pattern, '');
    console.log('🏠 ローカルLLMを使用します\n');
    break;
  }
}

// Claude指定チェック
if (!forceModel) {
  for (const pattern of keywords.cloud) {
    if (pattern.test(input)) {
      forceModel = 'cloud';
      actualInput = input.replace(pattern, '');
      console.log('☁️  Claude を使用します\n');
      break;
    }
  }
}

// デフォルトはローカル
if (!forceModel) {
  forceModel = 'local';
  console.log('🏠 デフォルト: ローカルLLMを使用します\n');
}

// 実行
try {
  const result = await router.executeWithModel(forceModel, actualInput, {
    reason: 'ユーザー指定'
  });
  
  console.log('\n📄 応答:\n');
  console.log(result.response);
  console.log('\n');
  
  router.showStats();
  
} catch (error) {
  console.error('❌ エラー:', error.message);
  
  // フォールバック
  if (forceModel === 'cloud' && error.message.includes('rate_limit')) {
    console.log('\n⚠️  Claude がレート制限中です。ローカルLLMで試します...\n');
    
    try {
      const result = await router.executeWithModel('local', actualInput, {
        reason: 'Claudeフォールバック'
      });
      
      console.log('\n📄 応答:\n');
      console.log(result.response);
      console.log('\n');
      
    } catch (fallbackError) {
      console.error('❌ フォールバックも失敗:', fallbackError.message);
      process.exit(1);
    }
  } else {
    process.exit(1);
  }
}
