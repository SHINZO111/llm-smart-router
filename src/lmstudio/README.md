# LM Studio Model Detector

LLM Smart Router用のLM Studioモデル自動検出モジュール

## 機能

- **モデル自動検出**: LM StudioのOpenAI互換APIを使用して読み込まれているモデルを検出
- **設定自動更新**: `config.yaml` を検出したモデル情報で自動更新
- **複数モデル対応**: 読み込まれている複数モデルを個別に管理
- **CLIインターフェース**: コマンドラインから簡単に操作

## インストール

```bash
# requirements.txtに追加
requests>=2.28.0
pyyaml>=6.0
```

## 使用方法

### CLIコマンド

```bash
# モデル検出して表示
python -m lmstudio detect

# 検出してconfig.yamlを更新
python -m lmstudio update

# LM Studio状態確認
python -m lmstudio status

# モデル一覧表示（テーブル形式）
python -m lmstudio list

# カスタムエンドポイントを指定
python -m lmstudio detect --endpoint http://192.168.1.100:1234/v1
```

### Python API

```python
from lmstudio import LMStudioModelDetector

# 検出器の初期化
detector = LMStudioModelDetector(endpoint="http://localhost:1234/v1")

# LM Studioが起動しているかチェック
if detector.is_running():
    # 読み込み中のモデル一覧を取得
    models = detector.get_loaded_models()
    for model in models:
        print(f"{model.id}: {model.name}")
    
    # デフォルトモデルを取得
    default = detector.get_default_model()
    print(f"デフォルト: {default}")
    
    # config.yamlを更新
    result = detector.detect_and_update_config("./config.yaml")
    print(f"更新成功: {result['success']}")
```

### router.jsとの連携

```javascript
// router.js 起動時に自動検出
import { execSync } from 'child_process';

class LLMRouter {
  constructor(configPath = './config.yaml') {
    // LM Studioモデルを自動検出
    this.detectLMStudioModels(configPath);
    
    // 設定を読み込み
    this.config = yaml.load(fs.readFileSync(configPath, 'utf8'));
    // ...
  }
  
  detectLMStudioModels(configPath) {
    try {
      console.log('🔍 LM Studioモデルを検出中...');
      const result = execSync(`python -m lmstudio update --config ${configPath}`, {
        encoding: 'utf8',
        timeout: 10000
      });
      console.log(result);
    } catch (error) {
      console.log('⚠️  LM Studio検出に失敗、既存設定を使用します');
    }
  }
}
```

## 設定ファイル構造

`python -m lmstudio update` を実行すると、以下のように更新されます:

```yaml
models:
  local:
    endpoint: http://localhost:1234/v1
    model: detected-model-id  # ← 自動更新
    temperature: 0.7
    max_tokens: 2048
    timeout: 30000
  
  # 複数モデル対応
  lmstudio:
    endpoint: http://localhost:1234/v1
    model: first-model-id
    name: "First Model"
  
  lmstudio_1:
    endpoint: http://localhost:1234/v1
    model: second-model-id
    name: "Second Model"

lmstudio_meta:
  last_detected: first-model-id
  detected_models:
    - first-model-id
    - second-model-id
```

## テスト

```bash
# テスト実行
python -m pytest src/tests/test_lmstudio.py -v

# カバレッジ付き
python -m pytest src/tests/test_lmstudio.py --cov=lmstudio --cov-report=html
```

## LM Studio設定

1. LM Studioを起動
2. モデルを読み込む
3. サーバーを起動（OpenAI互換API有効）
4. デフォルトで `http://localhost:1234/v1` でアクセス可能

## トラブルシューティング

| 問題 | 解決策 |
|------|--------|
| Connection refused | LM Studioが起動しているか確認 |
| モデルが検出されない | LM Studioでモデルを読み込んでいるか確認 |
| タイムアウト | エンドポイントURLが正しいか確認 |

## ライセンス

MIT
