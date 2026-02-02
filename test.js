#!/usr/bin/env node
/**
 * テストスクリプト
 */

import LLMRouter from './router.js';

const router = new LLMRouter();

const testCases = [
  {
    name: "簡単な質問（ローカル期待）",
    input: "Pythonでリストの要素を逆順にする方法は？"
  },
  {
    name: "CM業務（Claude確定）",
    input: "このプロジェクトのコスト見積もりを分析して"
  },
  {
    name: "推し活（Claude確定）",
    input: "KONOさんの配信スケジュール教えて"
  },
  {
    name: "複雑な分析（Claude期待）",
    input: "このシステムアーキテクチャの根本的な問題点と最適化案を提示して"
  },
  {
    name: "単純な整理（ローカル期待）",
    input: "以下のログファイルを要約して: エラー10件、警告5件"
  }
];

async function runTests() {
  console.log('🧪 テスト開始\n');
  
  for (const testCase of testCases) {
    console.log(`\n${'='.repeat(70)}`);
    console.log(`テストケース: ${testCase.name}`);
    console.log(`${'='.repeat(70)}`);
    
    try {
      const result = await router.route(testCase.input);
      console.log(`\n✅ 成功: ${result.model}モデル使用`);
    } catch (error) {
      console.log(`\n❌ 失敗: ${error.message}`);
    }
    
    // レート制限回避
    await new Promise(resolve => setTimeout(resolve, 2000));
  }
  
  router.showStats();
}

runTests();
