# クイックスタートガイド 🚀

## 5分でセットアップ

### Step 1: LM Studio起動
1. LM Studioを開く
2. rnj-1をロード（まだの場合はダウンロード）
3. **Local Server** タブ → **Start Server**

### Step 2: APIキー設定
```powershell
# PowerShellで実行
$env:ANTHROPIC_API_KEY="sk-ant-..." を設定
```

### Step 3: テスト実行
```bash
cd F:\llm-smart-router
node router.js "こんにちは"
```

成功例：
```
🔄 Smart Router 起動...
📝 入力: こんにちは

🔍 ローカルLLMで判定中...

🧠 AI判定結果:
   モデル: local
   確信度: 92.5%
   理由: 簡単な挨拶

============================================================
🚀 実行: LOCAL モデル
============================================================

✅ 完了
⏱️  処理時間: 1.2秒
📊 トークン: 12 in / 15 out
💰 コスト: ¥0.00
💵 節約: ¥0.45 (ローカル使用)
```

### Step 4: 実用例を試す

#### 例1: 簡単なコード生成（ローカル）
```bash
node router.js "Pythonでリストを逆順にするコードを書いて"
```
→ ローカルLLMで処理（¥0）

#### 例2: 複雑な分析（Claude自動切替）
```bash
node router.js "このアーキテクチャの根本的な問題点を分析して"
```
→ 自動的にClaudeに切り替わる

#### 例3: CM業務（Claude確定）
```bash
node router.js "このコスト見積もりを分析して"
```
→ 確実にClaude使用（業務クリティカル）

#### 例4: 推し活（Claude確定）
```bash
node router.js "KONOさんの配信スケジュール教えて"
```
→ 確実にClaude使用（推し活は妥協なし）

## Discord統合（OpenClaw）

```bash
# OpenClawから呼ぶ場合
node openclaw-integration.js "質問内容"

# ローカル強制
node openclaw-integration.js local "質問内容"

# Claude強制
node openclaw-integration.js claude "質問内容"

# 統計表示
node openclaw-integration.js stats
```

## カスタマイズ

### 自分専用ルール追加

`config.yaml` を開いて：

```yaml
hard_rules:
  - name: "my_custom_rule"
    triggers: ["あなたのキーワード"]
    model: "cloud"  # cloudまたはlocal
    reason: "理由"
```

### コスト通知の閾値変更

```yaml
cost:
  notify_threshold: 50  # ¥50 → 好きな金額
```

## トラブル解決

### Q: "Connection refused" エラー
**A**: LM StudioのLocal Serverを起動してください

### Q: 応答が遅い
**A**: LM Studioでモデルがロードされているか確認（初回ロードは時間かかります）

### Q: Claudeに切り替わらない
**A**: `ANTHROPIC_API_KEY` 環境変数が設定されているか確認

### Q: 判定が期待と違う
**A**: `config.yaml` のルールを調整するか、強制指定を使用

## 次のステップ

✅ 基本動作確認  
→ 📚 [README.md](README.md) で詳細設定を見る  
→ 🔧 [config.yaml](config.yaml) をカスタマイズ  
→ 🤖 OpenClawに統合（次のフェーズ）

---

**質問・問題があればクラに聞いてください！** 🦞
