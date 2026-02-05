# 🤖 LLM Smart Router Pro v2.0

<p align="center">
  <img src="https://img.shields.io/badge/version-2.0.0-blue?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.9+-green?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/PySide6-Qt-orange?style=for-the-badge" alt="PySide6">
  <img src="https://img.shields.io/badge/license-MIT-yellow?style=for-the-badge" alt="License">
</p>

<p align="center">
  <b>世界最高峰のLLMルーターGUIアプリケーション</b><br>
  ローカルLLM × Claude をシームレスに切り替え
</p>

---

## ✨ 特徴

### 🎯 インテリジェントルーティング
- **自動判定**: タスク内容に応じて最適なモデルを自動選択
- **ワンクリック切替**: 手動でのモデル切り替えも瞬時に
- **確信度ベース**: 曖昧な場合は安全側（クラウド）に倒す

### 🔐 セキュリティ
- **OS標準キーストア**: Windows Credential / macOS Keychain対応
- **暗号化保存**: フォールバック時はAES-256暗号化
- **メモリ保護**: APIキーはメモリ上でのみ復号化

### 📊 統計ダッシュボード
- **リアルタイム表示**: 使用量、コスト、節約額を可視化
- **円形プログレス**: ローカル/クラウド使用比率
- **履歴管理**: 実行履歴の保存・エクスポート

### 📋 用途別プリセット
- 🏗️ **CM業務**: 建設業のコスト管理・見積対応
- 💎 **推し活**: KONO・mina・りぃサポート
- 💻 **コーディング**: コード生成・レビュー・デバッグ
- ✍️ **文章作成**: ビジネス文書・SNS投稿
- 📊 **データ分析**: 分析・可視化・レポート
- 📚 **学習支援**: 新知識の習得・解説

---

## 🚀 クイックスタート

### 必要条件

- **Windows 10/11** または **macOS 12+**
- **Python 3.9+**
- **LM Studio**（ローカルLLM使用時）
- **Anthropic APIキー**（Claude使用時）

### インストール

```powershell
# 1. リポジトリをクローン
cd F:\llm-smart-router

# 2. バッチファイルで起動
.\run_gui.bat
```

初回起動時に自動的に仮想環境と依存関係がインストールされます。

### APIキー設定

1. 初回起動時に「APIキー未設定」ダイアログが表示されます
2. 「はい」を選択して設定画面を開きます
3. Anthropic APIキーを入力（`sk-ant-api03-...`）
4. 「接続テスト」ボタンで検証
5. 「保存」ボタンで暗号化保存

---

## 📖 使用方法

### 基本フロー

1. **入力**: 質問やタスクを入力欄に記入
2. **モデル選択**: 「自動判定」または特定モデルを選択
3. **プリセット選択**: 用途に応じたプリセットを選択（任意）
4. **実行**: `Ctrl+Enter` または 🚀実行ボタン
5. **結果確認**: 出力欄に応答が表示されます

### ショートカットキー

| キー | 機能 |
|------|------|
| `Ctrl+Enter` | 実行 |
| `Esc` | 停止 |
| `Ctrl+O` | ファイルを開く |
| `Ctrl+S` | 結果を保存 |

### コマンドライン

```powershell
# 自動判定
python src\gui\main_window.py

# 設定ダイアログ
python src\gui\settings_dialog.py

# APIキー管理（CLI）
python src\security\key_manager.py set anthropic sk-ant-api03-...
python src\security\key_manager.py get anthropic
python src\security\key_manager.py delete anthropic
```

---

## ⚙️ 設定

### 設定ファイル

設定は以下の場所に保存されます：

- **Windows**: `%USERPROFILE%\.llm-smart-router\`
- **macOS/Linux**: `~/.llm-smart-router/`

### ルーター設定 (`config.yaml`)

```yaml
# モデル設定
models:
  local:
    provider: "lmstudio"
    endpoint: "http://localhost:1234/v1"
    model: "essentialai/rnj-1"
    timeout: 30000
  
  cloud:
    provider: "anthropic"
    model: "claude-sonnet-4-5-20250929"

# ルーティング設定
routing:
  enabled: true
  strategy: "intelligent"
  intelligent_routing:
    confidence_threshold: 0.75

# コスト管理
cost:
  tracking: true
  notify_threshold: 50  # ¥50超えたら通知
```

---

## 🛡️ セキュリティ

### APIキー管理

| 項目 | 仕様 |
|------|------|
| **保存方式** | Windows Credential / macOS Keychain |
| **暗号化** | OS標準暗号化 + AES-256（フォールバック） |
| **メモリ管理** | セッション中のみキャッシュ、終了時クリア |
| **削除** | 安全な上書き削除（3回ランダムデータ上書き） |

### 推奨設定

```python
# 定期的なキーローテーション
# 3ヶ月ごとにAPIキーを更新することを推奨

# 最小権限の原則
# Anthropic Consoleで適切なレート制限を設定
```

---

## 📊 パフォーマンス

### ベンチマーク

| モデル | 応答時間 | コスト/1K tokens |
|--------|----------|------------------|
| Local (LM Studio) | 2-5秒 | ¥0（無料） |
| Claude Sonnet | 3-10秒 | ¥4.5 |

### 節約効果

- **ローカル使用率 70%** の場合: **月額約¥15,000節約**
- **ローカル使用率 90%** の場合: **月額約¥25,000節約**

---

## 🏗️ アーキテクチャ

```
llm-smart-router/
├── src/
│   ├── gui/
│   │   ├── main_window.py      # メインGUI
│   │   ├── settings_dialog.py  # 設定画面
│   │   └── dashboard.py        # 統計ダッシュボード
│   ├── security/
│   │   └── key_manager.py      # APIキー管理
│   └── presets/                # プリセット定義
├── router.js                   # Node.jsルーター
├── openclaw-integration.js     # OpenClaw連携
├── config.yaml                 # 設定ファイル
├── run_gui.bat                 # Windows起動スクリプト
├── requirements-gui.txt        # Python依存関係
└── README.md                   # 本ファイル
```

---

## 🔧 トラブルシューティング

### よくある問題

#### 「APIキーが見つかりません」

```powershell
# 設定ダイアログを開く
python src\gui\settings_dialog.py

# またはCLIで設定
python src\security\key_manager.py set anthropic YOUR_API_KEY
```

#### 「ローカルLLMに接続できません」

1. LM Studioが起動しているか確認
2. ポート1234でリッスンしているか確認
3. ファイアウォール設定を確認

#### 「ModuleNotFoundError」

```powershell
# 依存関係を再インストール
pip install -r requirements-gui.txt --force-reinstall
```

### ログ確認

```powershell
# ログファイルの場所
%USERPROFILE%\.llm-smart-router\logs\
```

---

## 📝 変更履歴

### v2.0.0 (2025-02-03)
- ✨ PySide6 GUIを追加
- 🔐 keyringライブラリによるOS標準キーストア連携
- 📊 統計ダッシュボード実装
- 📋 用途別プリセット機能追加
- 🎨 ダークテーマUI

### v1.0.0 (2025-01-XX)
- 🎉 初回リリース
- 🔄 Node.jsベースのルーター
- 🤖 Claude API連携

---

## 🤝 コントリビューション

貢献を歓迎します！

1. Forkを作成
2. 機能ブランチを作成 (`git checkout -b feature/amazing-feature`)
3. 変更をコミット (`git commit -m 'Add amazing feature'`)
4. ブランチにプッシュ (`git push origin feature/amazing-feature`)
5. Pull Requestを作成

---

## 📜 ライセンス

MIT License - 詳細は [LICENSE](LICENSE) ファイルを参照

---

## 🙏 謝辞

- **新さん** - 本プロジェクトの為に
- **Anthropic** - Claude API
- **Qt Project** - PySide6

---

<p align="center">
  <b>Made with ❤️ by クラ for 新さん</b><br>
  <sub>© 2025 LLM Smart Router Project</sub>
</p>
