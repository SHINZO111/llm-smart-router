# LLM Smart Router - Conversation History API

会話履歴管理機能のFastAPIベースのREST APIとCLIインターフェース

## CP3: API/UI層

このモジュールは、CP1（データベース層）とCP2（ロジック層）の上に構築されたREST APIとCLIインターフェースを提供します。

## インストール

```bash
pip install -r requirements.txt
```

## APIサーバーの起動

```bash
# 開発モード（ホットリロード有効）
python -m api.main

# または直接
uvicorn api.main:app --reload

# 本番モード
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

APIドキュメントは http://localhost:8000/docs で確認できます。

## APIエンドポイント

### 会話管理

| メソッド | エンドポイント | 説明 |
|---------|--------------|------|
| GET | `/api/v1/conversations` | 会話一覧取得（フィルタ・ソート対応） |
| GET | `/api/v1/conversations/{id}` | 会話詳細取得 |
| POST | `/api/v1/conversations` | 新規会話作成 |
| PUT | `/api/v1/conversations/{id}` | 会話更新（タイトル・ステータス変更） |
| DELETE | `/api/v1/conversations/{id}` | 会話削除 |

### メッセージ管理

| メソッド | エンドポイント | 説明 |
|---------|--------------|------|
| GET | `/api/v1/conversations/{id}/messages` | メッセージ一覧取得 |
| POST | `/api/v1/conversations/{id}/messages` | メッセージ追加 |
| GET | `/api/v1/conversations/{id}/history` | LLM用履歴フォーマットで取得 |

### トピック管理

| メソッド | エンドポイント | 説明 |
|---------|--------------|------|
| GET | `/api/v1/topics` | トピック一覧取得 |
| POST | `/api/v1/topics` | トピック作成 |
| GET | `/api/v1/topics/{id}` | トピック詳細取得 |
| PUT | `/api/v1/topics/{id}` | トピック更新 |
| DELETE | `/api/v1/topics/{id}` | トピック削除 |

### 検索・エクスポート・統計

| メソッド | エンドポイント | 説明 |
|---------|--------------|------|
| GET | `/api/v1/search?q={query}` | 会話検索 |
| POST | `/api/v1/export` | 会話エクスポート（JSON） |
| POST | `/api/v1/import` | 会話インポート（JSON） |
| GET | `/api/v1/stats` | 統計情報取得 |

## CLI使用方法

### 基本コマンド

```bash
# 会話一覧
python -m conversation list

# フィルタ付き一覧
python -m conversation list --status active --limit 10

# 会話詳細表示
python -m conversation show <conversation_id>

# 会話作成
python -m conversation create --title "New Conversation"

# 検索
python -m conversation search "keyword"

# 統計情報
python -m conversation stats
```

### エクスポート/インポート

```bash
# 単一会話エクスポート
python -m conversation export <conversation_id> --output export.json

# 全会話エクスポート
python -m conversation export --all --output backup.json

# インポート
python -m conversation import backup.json
```

### トピック管理

```bash
# トピック一覧
python -m conversation topics

# トピック作成
python -m conversation topic "Project A" --description "Work related"
```

### インタラクティブモード

```bash
python -m conversation interactive
```

## テスト実行

```bash
# すべてのテスト
pytest src/tests/ -v

# APIテストのみ
pytest src/tests/test_api.py -v

# CLIテストのみ
pytest src/tests/test_cli.py -v

# 統合テスト
pytest src/tests/test_integration.py -v
```

## ファイル構成

```
src/
├── api/
│   ├── __init__.py
│   ├── main.py          # FastAPIアプリケーション
│   └── routes.py        # APIルート定義
├── cli/
│   ├── __init__.py
│   └── commands.py      # CLIコマンド
├── conversation/
│   ├── __main__.py      # python -m conversation エントリポイント
│   ├── conversation_manager.py  # CP2（既存）
│   ├── db_manager.py            # CP1（既存）
│   └── json_handler.py          # CP2（既存）
├── models/
│   ├── conversation.py  # CP1（既存）
│   └── message.py       # CP1（既存）
└── tests/
    ├── __init__.py
    ├── test_api.py      # APIテスト
    ├── test_cli.py      # CLIテスト
    └── test_integration.py  # 統合テスト
```

## 環境変数

```bash
# データ保存パス（オプション）
export LLM_ROUTER_STORAGE_PATH="~/.llm-router/conversations"

# API設定
export LLM_ROUTER_API_HOST="0.0.0.0"
export LLM_ROUTER_API_PORT="8000"
```
