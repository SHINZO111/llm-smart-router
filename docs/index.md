---
layout: default
title: LLM Smart Router
---

# LLM Smart Router

ローカルLLM（rnj-1 via LM Studio等）とクラウドモデル（Claude, GPT-4o, Gemini, Kimi）を自動で切り替えるインテリジェントルーター。

## 特徴

- **自動判定**: タスクの複雑度を自動で判定し、最適なLLMを選択
- **コスト削減**: 単純タスクはローカル、複雑タスクはClaudeで最大95%削減
- **マルチランタイム対応**: LM Studio, Ollama, llama.cpp, KoboldCpp, Jan, GPT4All, vLLM
- **自動フォールバック**: 障害時は自動で代替モデルに切り替え
- **会話履歴管理**: 自動保存・検索・トピック別整理・エクスポート対応
- **PySide6 GUI**: ダークテーマ、統計ダッシュボード、設定ダイアログ
- **OpenAI互換API**: `/v1/chat/completions` エンドポイント

## ドキュメント

| ガイド | 内容 |
|--------|------|
| [クイックスタート](quick-start) | 5分でセットアップ |
| [インストールガイド](INSTALL) | 詳細なインストール手順 |
| [ユーザーマニュアル](USER_MANUAL) | GUI機能の完全ガイド |
| [GUI詳細](README_GUI) | GUI機能・セキュリティ・統計 |
| [会話履歴ガイド](conversation_history_guide) | 会話管理機能の使い方 |

## アーキテクチャ

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│  PySide6 GUI │────▶│  Node.js     │────▶│ Local Runtime │
│  FastAPI API │     │  Router      │     │ (LM Studio等) │
│  CLI         │     │  (config.yaml)│    │               │
└─────────────┘     └──────┬───────┘     └───────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ Cloud APIs   │
                    │ Claude/GPT-4o│
                    │ Gemini/Kimi  │
                    └──────────────┘
```

## リンク

- [GitHub Repository](https://github.com/SHINZO111/llm-smart-router)
