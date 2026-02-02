# LLM Smart Router 🧠⚡

ローカルLLM（rnj-1）とClaude Codeを自動で切り替えるインテリジェントルーター

## 特徴

- ✅ **自動判定**: タスクの複雑度を自動で判定し、最適なLLMを選択
- ⚡ **コスト削減**: 単純タスクはローカル、複雑タスクはClaudeで最大95%削減
- 🎯 **確実ルール**: CM業務・推し活などは確実にClaude使用
- 📊 **統計管理**: コスト・節約額・使用率をリアルタイム表示
- 🔄 **自動フォールバック**: 障害時は自動で代替モデルに切り替え

## セットアップ

### 1. LM Studio設定

1. LM StudioでrnJ-1をダウンロード
2. モデルをロード
3. Local Server起動（http://localhost:1234）

### 2. 環境変数設定

```powershell
# Claude APIキー
$env:ANTHROPIC_API_KEY="sk-ant-..."
```

永続化する場合：
```powershell
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")
```

### 3. GUIアプリの起動（推奨）

```powershell
# Windows - バッチファイルで簡単起動
.\run_gui.bat
```

または手動で：

```powershell
# 仮想環境作成
python -m venv venv
venv\Scripts\activate

# 依存関係インストール
pip install -r requirements-gui.txt

# GUI起動
python src\gui\main_window.py
```

### 4. 動作確認

```bash
# テスト実行
cd F:\llm-smart-router
node test.js
```

## 使い方

### GUIアプリ（推奨）

#### クイックスタート

1. **起動**: `run_gui.bat` をダブルクリック
2. **APIキー設定**: 初回起動時にAnthropic APIキーを設定
3. **入力**: 質問やタスクを入力欄に記入
4. **実行**: `Ctrl+Enter` または 🚀実行ボタン
5. **結果確認**: 出力欄に応答が表示されます

#### 主な機能

| 機能 | 説明 |
|------|------|
| 🤖 **モデル切替** | 自動/ローカル/クラウドをワンクリックで切替 |
| 📋 **プリセット** | CM業務、推し活、コーディングなど用途別テンプレート |
| 📊 **ダッシュボード** | 使用量、コスト、節約額をリアルタイム表示 |
| 🔐 **APIキー管理** | Windows/macOS標準キーストアに安全に保存 |
| ⚙️ **設定** | 確信度閾値、タイムアウト、コスト警告など |

#### ショートカットキー

| キー | 機能 |
|------|------|
| `Ctrl+Enter` | 実行 |
| `Esc` | 停止 |
| `Ctrl+O` | ファイルを開く |
| `Ctrl+S` | 結果を保存 |

詳細は [README_GUI.md](README_GUI.md) を参照

### コマンドライン

```bash
# 基本
node router.js "質問内容"

# 例
node router.js "Pythonでソート関数を書いて"
node router.js "このシステムの根本原因を分析して"
node router.js "KONOさんの配信スケジュール教えて"
```

### プログラムから

```javascript
import LLMRouter from './router.js';

const router = new LLMRouter();

const result = await router.route("質問内容");
console.log(result.response);
console.log(`使用モデル: ${result.model}`);
console.log(`コスト: ¥${result.metadata.cost.toFixed(2)}`);
```

## 設定カスタマイズ

`config.yaml` を編集：

### モデル切り替えルール追加

```yaml
hard_rules:
  - name: "custom_rule"
    triggers: ["キーワード1", "キーワード2"]
    model: "cloud"  # or "local"
    reason: "理由"
```

### コスト閾値変更

```yaml
cost:
  notify_threshold: 100  # ¥100超えで通知
  confirm_expensive: true
```

## トラブルシューティング

### LM Studio接続エラー
```
❌ Error: connect ECONNREFUSED 127.0.0.1:1234
```
→ LM StudioのLocal Serverが起動しているか確認

### Claude APIエラー
```
❌ Error: authentication_error
```
→ `ANTHROPIC_API_KEY` 環境変数が正しく設定されているか確認

### モデルが見つからない
```
❌ Error: model not found
```
→ LM Studioでrnj-1がロードされているか確認

## OpenClaw統合

OpenClawから使用する場合は `openclaw-integration.js` を参照。

## ログ

ログは自動で保存されます：
```
F:\llm-smart-router\logs\
  └── 2026-02-02.log
```

## 開発者向け

### 構造

```
F:\llm-smart-router\
├── router.js          # メインルーター
├── config.yaml        # 設定ファイル
├── test.js            # テストスクリプト
├── package.json       # 依存関係
└── README.md          # このファイル
```

### カスタムロジック追加

`router.js` の `intelligentTriage()` メソッドを編集。

---

**Created by クラ for 新さん** 🦞
