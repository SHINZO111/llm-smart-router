# OpenClaw統合ガイド

LLM Smart RouterとOpenClawの双方向統合により、以下が可能になります：

1. **このアプリ → OpenClaw**: 検出したモデルをOpenClawに自動設定
2. **OpenClaw → このアプリ**: OpenClawからこのアプリを操作

## 1. このアプリ → OpenClaw（自動設定）

### 機能
- モデルスキャン後、検出されたローカルモデルをOpenClawの設定ファイルに自動反映
- デフォルトLLMエンドポイント/モデルIDの自動設定

### 使い方

#### GUI経由
1. 設定ダイアログを開く（⚙️ボタン）
2. 「OpenClaw」タブを選択
3. 「スキャン時に自動同期」をチェック
4. または「今すぐ同期」ボタンで手動同期

#### CLI経由
```bash
# Pythonから直接
python -c "
from src.scanner.scanner import MultiRuntimeScanner
from src.scanner.registry import ModelRegistry
import asyncio

async def sync():
    scanner = MultiRuntimeScanner()
    results = await scanner.scan_all()
    registry = ModelRegistry('data/model_registry.json')
    registry.update(results, sync_openclaw=True)  # sync_openclaw=True で同期

asyncio.run(sync())
"
```

#### Node.js経由
```bash
# openclaw-integration.jsから
node openclaw-integration.js

# OpenClaw設定を手動更新
const integration = new OpenClawLLMRouter();
integration.updateOpenClawLLM('http://localhost:1234/v1', 'qwen3-4b');
```

### OpenClaw設定ファイル場所
- `~/.openclaw/config.json` (優先)
- `~/.config/openclaw/config.json`
- `$(pwd)/.openclaw/config.json`

### 設定例
```json
{
  "llm": {
    "provider": "openai",
    "endpoint": "http://localhost:1234/v1",
    "model": "qwen3-4b",
    "available_models": [
      {
        "id": "qwen3-4b",
        "name": "Qwen 3 4B",
        "endpoint": "http://localhost:1234/v1",
        "runtime": "lmstudio"
      }
    ],
    "updated_at": "2026-02-06T12:34:56.789Z",
    "updated_by": "llm-smart-router"
  }
}
```

---

## 2. OpenClaw → このアプリ（逆方向制御）

### 機能
OpenClawからLLM Smart Routerを操作できます：

- クエリ実行（インテリジェントルーティング）
- モデルスキャンのトリガー
- 統計情報の取得
- 検出済みモデル一覧の取得
- 設定のリロード

### 前提条件
LLM Smart Router APIサーバーが起動している必要があります：

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

または、環境変数で別のエンドポイントを指定：
```bash
export LLM_ROUTER_API_URL=http://localhost:8000
```

### 使い方

#### 1. Node.js CLIから直接操作

```bash
# クエリ実行（自動ルーティング）
node openclaw-integration.js query "JavaScriptとTypeScriptの違いは？"

# モデルスキャンをトリガー
node openclaw-integration.js scan

# 統計情報取得
node openclaw-integration.js router-stats

# 検出済みモデル一覧
node openclaw-integration.js models

# 設定リロード
node openclaw-integration.js reload

# 統合コマンド（JSON形式）
node openclaw-integration.js control query '{"input":"質問", "forceModel":"local"}'
```

#### 2. OpenClawカスタムツールとして登録

**ツール定義ファイル** (`~/.openclaw/tools/llm-router.json`):
```json
{
  "name": "llm-router",
  "description": "LLM Smart Routerを操作してクエリをインテリジェントにルーティング",
  "version": "1.0.0",
  "commands": {
    "query": {
      "description": "クエリを実行（自動ルーティング）",
      "command": "node",
      "args": ["openclaw-integration.js", "query"],
      "input": "stdin"
    },
    "scan": {
      "description": "モデルスキャンを実行",
      "command": "node",
      "args": ["openclaw-integration.js", "scan"]
    },
    "stats": {
      "description": "ルーター統計を取得",
      "command": "node",
      "args": ["openclaw-integration.js", "router-stats"]
    },
    "models": {
      "description": "検出済みモデル一覧",
      "command": "node",
      "args": ["openclaw-integration.js", "models"]
    }
  }
}
```

#### 3. OpenClawワークフローから呼び出し

```yaml
# OpenClawワークフロー例
name: intelligent-query
description: LLM Smart Routerを使ってインテリジェントにクエリを処理

steps:
  - name: scan-models
    tool: llm-router
    command: scan
    description: 利用可能なモデルをスキャン

  - name: execute-query
    tool: llm-router
    command: query
    input: "${user_input}"
    description: クエリを自動ルーティング

  - name: get-stats
    tool: llm-router
    command: stats
    description: 実行統計を取得
```

#### 4. Node.jsコードから直接呼び出し

```javascript
import OpenClawLLMRouter from './openclaw-integration.js';

const integration = new OpenClawLLMRouter();

// クエリ実行
const result = await integration.queryRouter(
  "機械学習の基礎を教えて",
  null,  // forceModel: null = 自動判定
  {}     // 追加コンテキスト
);

if (result.success) {
  console.log(`モデル: ${result.model}`);
  console.log(`応答: ${result.response}`);
} else {
  console.error(`エラー: ${result.error}`);
}

// モデルスキャン
await integration.triggerModelScan();

// 統計取得
const stats = await integration.getRouterStats();
console.log(stats);

// 統合インターフェース（コマンド形式）
const queryResult = await integration.controlRouter('query', {
  input: '質問内容',
  forceModel: 'local:qwen3-4b'
});
```

### REST API エンドポイント

OpenClawからHTTPリクエストで直接呼び出すこともできます：

#### POST /router/query
クエリを実行（インテリジェントルーティング）

**リクエスト**:
```json
{
  "input": "質問内容",
  "force_model": "local:qwen3-4b",  // 省略可（自動判定）
  "context": {}                      // 省略可
}
```

**レスポンス**:
```json
{
  "success": true,
  "model": "local:qwen3-4b",
  "response": "応答テキスト",
  "metadata": {
    "tokens": 150,
    "cost": 0.0
  }
}
```

#### GET /router/stats
ルーター統計を取得

**レスポンス**:
```json
{
  "models": {
    "local_count": 5,
    "cloud_count": 4,
    "total_count": 9,
    "last_scan": "2026-02-06T12:34:56.789Z",
    "cache_valid": true
  },
  "fallback_priority": ["local", "cloud"],
  "conversations": {
    "total": 42,
    "active": 5
  }
}
```

#### POST /models/scan
モデルスキャンをトリガー（バックグラウンド実行）

**レスポンス**:
```json
{
  "status": "started",
  "message": "モデルスキャン開始"
}
```

#### GET /models/detected
検出済みモデル一覧を取得

**レスポンス**:
```json
{
  "local": [
    {
      "id": "qwen3-4b",
      "name": "Qwen 3 4B",
      "runtime": {
        "runtime_type": "lmstudio",
        "endpoint": "http://localhost:1234/v1"
      }
    }
  ],
  "cloud": [
    {
      "id": "claude-4.6-sonnet",
      "provider": "anthropic"
    }
  ],
  "total": 9,
  "last_scan": "2026-02-06T12:34:56.789Z",
  "cache_valid": true
}
```

#### POST /router/config/reload
設定をリロード

**レスポンス**:
```json
{
  "success": true,
  "message": "設定をリロードしました",
  "models_loaded": 9
}
```

---

## トラブルシューティング

### APIサーバーに接続できない
```bash
# APIサーバーが起動しているか確認
curl http://localhost:8000/health

# ポート確認
netstat -ano | findstr :8000

# 環境変数確認
echo $LLM_ROUTER_API_URL
```

### OpenClaw設定が見つからない
```bash
# デフォルト設定を作成
node openclaw-integration.js

# Pythonから作成
python -c "
from src.openclaw.config_manager import OpenClawConfigManager
manager = OpenClawConfigManager()
manager.create_default_config()
"
```

### モデルが検出されない
```bash
# 手動スキャン
python -m scanner scan

# レジストリ確認
cat data/model_registry.json

# ローカルランタイム起動確認
curl http://localhost:1234/v1/models  # LM Studio
curl http://localhost:11434/api/tags   # Ollama
```

---

## 統合ワークフロー例

### フルオートワークフロー
```bash
# 1. LM Studio起動 → モデルスキャン → OpenClaw設定
python -m launcher

# 2. OpenClawからクエリ実行
node openclaw-integration.js query "Python機械学習ライブラリの比較"

# 3. 統計確認
node openclaw-integration.js router-stats
```

### OpenClawワークフロー内での自動化
```yaml
name: auto-ai-pipeline
description: LLM Smart Routerを使った自動AIパイプライン

on:
  schedule: "0 * * * *"  # 1時間ごと

steps:
  - name: start-router
    run: |
      python -m launcher --skip-discord
    background: true

  - name: scan-models
    tool: llm-router
    command: scan
    wait: 30s

  - name: sync-to-openclaw
    run: |
      python -c "
      from src.scanner.registry import ModelRegistry
      registry = ModelRegistry('data/model_registry.json')
      registry.update(registry.get_all_models(), sync_openclaw=True)
      "

  - name: process-queries
    loop: queries
    tool: llm-router
    command: query
    input: "${query}"
    save_output: results/${query_id}.json
```

---

## セキュリティ考慮事項

- API認証: 現在は認証なし。本番環境ではAPIキー認証を追加推奨
- CORS: `ALLOWED_ORIGINS` 環境変数でオリジン制限
- レートリミット: 現在は未実装。高負荷環境では追加推奨
- ログ: 機密情報がログに含まれないよう注意

---

## 参考リンク

- [LLM Smart Router README](README.md)
- [Multi-Runtime Scanner](src/scanner/README.md)
- [API仕様](API_REFERENCE.md)
- OpenClaw公式ドキュメント（該当する場合）
