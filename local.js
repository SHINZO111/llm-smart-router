#!/usr/bin/env node
/**
 * ローカルLLM専用 - シンプル版
 * 使い方: node local.js "質問内容"
 */

import axios from 'axios';

const input = process.argv.slice(2).join(' ');

if (!input) {
  console.log('使い方: node local.js "質問内容"');
  process.exit(0);
}

console.log('🏠 ローカルLLM実行中...\n');

const startTime = Date.now();

try {
  const response = await axios.post(
    'http://localhost:1234/v1/chat/completions',
    {
      model: 'essentialai/rnj-1',
      messages: [{ role: 'user', content: input }],
      temperature: 0.7,
      max_tokens: 4096
    },
    { timeout: 30000 }
  );
  
  const result = response.data.choices[0].message.content;
  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  
  console.log('📄 応答:\n');
  console.log(result);
  console.log('\n' + '─'.repeat(60));
  console.log(`⏱️  ${elapsed}秒 | 💰 ¥0 | 🏠 ローカルLLM`);
  console.log('─'.repeat(60));
  
} catch (error) {
  console.error('❌ エラー:', error.message);
  console.log('\n💡 確認事項:');
  console.log('  - LM Studio起動してますか？');
  console.log('  - Local Server起動してますか？');
  console.log('  - rnj-1ロード済みですか？');
  process.exit(1);
}
