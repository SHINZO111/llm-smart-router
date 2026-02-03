# 会話履歴管理機能ガイド

## 概要

LLM Smart Routerの**会話履歴管理機能**では、AIとのやり取りを自動的に保存し、後から参照・検索・管理することができます。

```
┌─────────────────────────────────────────────────────────────┐
│  📚 会話履歴管理機能の主なメリット                              │
├─────────────────────────────────────────────────────────────┤
│  ✅ 過去の会話を自動保存・永続的に参照可能                      │
│  ✅ トピック別に整理・カテゴリ管理                              │
│  ✅ フルテキスト検索ですぐに必要な情報を発見                    │
│  ✅ JSON形式でのエクスポート/インポート対応                    │
│  ✅ 複数セッションの同時管理                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 目次

1. [クイックスタート](#クイックスタート)
2. [基本操作](#基本操作)
3. [トピック管理](#トピック管理)
4. [検索機能](#検索機能)
5. [エクスポート/インポート](#エクスポートインポート)
6. [よくある質問](#よくある質問)

---

## クイックスタート

### 自動保存の仕組み

会話履歴は**自動的に保存**されます。特別な操作は不要です。

```
新規会話を開始 → メッセージを送信 → 自動保存
```

### 保存される情報

| 項目 | 説明 |
|------|------|
| **会話タイトル** | 最初のメッセージから自動生成（編集可能） |
| **メッセージ履歴** | ユーザーの入力とAIの応答 |
| **使用モデル** | 各応答に使用されたAIモデル |
| **タイムスタンプ** | 作成日時・更新日時 |
| **トピック** | 分類用のカテゴリ |

---

## 基本操作

### 会話一覧の表示

左側のサイドバーに最近の会話一覧が表示されます：

```
┌─────────────────┬──────────────────────────┐
│ 📋 会話一覧      │  💬 メイン画面            │
│                 │                          │
│ 🔍 検索...      │  Pythonについて教えて     │
│                 │  ──────────────────────  │
│ + 新規会話      │  🤖 Pythonは1991年に...   │
│                 │                          │
│ 📄 会話1        │  [続きを入力...]          │
│ 📄 会話2        │                          │
│ 📄 会話3        │                          │
└─────────────────┴──────────────────────────┘
```

### 新規会話の作成

**方法1**: 「+ 新規会話」ボタンをクリック  
**方法2**: ショートカート `Ctrl+N`

### 既存会話の再開

1. サイドバーから会話をクリック
2. 前回の続きからチャットを再開

### 会話の削除

1. 会話を右クリック → 「削除」を選択
2. または会話を選択して `Delete` キー

⚠️ **注意**: 削除した会話は復元できません

---

## トピック管理

### トピックとは

会話を分類するための**カテゴリ**です。業種や目的別に整理できます。

デフォルトトピック：
- **General** - 一般的な会話
- **Development** - 開発・コーディング関連
- **Research** - 調査・研究関連

### トピックの作成

```python
# プログラムからの作成例
from src.conversation.conversation_manager import ConversationManager

manager = ConversationManager()
topic = manager.create_topic(
    name="建設業務",
    description="コスト管理・見積もり関連",
    color="#FF5733"
)
```

### 会話へのトピック割り当て

1. 会話を選択
2. 「トピック」メニューから割り当てるトピックを選択

または新規作成時に指定：

```python
conv = manager.create_conversation(
    first_message="見積もりについて",
    topic_id=topic.id
)
```

### トピック別フィルタ

サイドバーのトピックセレクターでフィルタ：

```
[すべて] [General] [Development] [建設業務] [Research]
```

---

## 検索機能

### 全文検索

検索ボックスにキーワードを入力：

```
🔍 Python リスト
```

検索対象：
- 会話タイトル
- メッセージ内容
- 使用モデル名

### 高度な検索

日付範囲で絞り込み：

```python
from datetime import datetime, timedelta

# 過去7日間の会話を検索
results = manager.list_conversations(
    search_query="Python",
    date_from=datetime.now() - timedelta(days=7)
)
```

### 検索結果の表示

```
検索結果: "Python" (3件)
─────────────────────────
📄 Pythonでソート関数    - 2日前
📄 Python初心者向け      - 5日前
📄 Django vs Flask       - 1週間前
```

---

## エクスポート/インポート

### 会話のエクスポート

**単一会話のエクスポート**：

```python
from src.conversation.json_handler import ConversationJSONHandler

handler = ConversationJSONHandler()

# 単一会話をエクスポート
handler.export_to_file(
    "my_conversation.json",
    conversation_ids=[conv_id]
)
```

**複数会話のエクスポート**：

```python
# すべての会話をエクスポート
handler.export_to_file("backup.json")

# トピック別にエクスポート
handler.export_to_file(
    "dev_conversations.json",
    topic_id=development_topic_id
)
```

### エクスポート形式

```json
{
  "version": "1.0",
  "export_date": "2026-02-04T10:30:00",
  "conversation": {
    "id": 1,
    "title": "Python入門",
    "created_at": "2026-02-01T09:00:00",
    "updated_at": "2026-02-01T09:30:00",
    "topic": "Development",
    "messages": [
      {
        "role": "user",
        "content": "Pythonについて教えて",
        "model": null,
        "timestamp": "2026-02-01T09:00:00"
      },
      {
        "role": "assistant",
        "content": "Pythonは1991年に...",
        "model": "claude-3-opus",
        "timestamp": "2026-02-01T09:00:05"
      }
    ]
  },
  "metadata": {
    "message_count": 2,
    "user_messages": 1,
    "assistant_messages": 1,
    "models_used": ["claude-3-opus"]
  }
}
```

### 会話のインポート

```python
# JSONファイルからインポート
imported_ids = handler.import_from_file("backup.json")

# 特定のトピックに割り当ててインポート
handler.import_from_file(
    "dev_conversations.json",
    target_topic_id=development_topic_id
)
```

### バックアップの作成

```python
# 自動バックアップ
backup_path = handler.create_backup("backups/")
print(f"バックアップ作成: {backup_path}")
# → backups/conversations_backup_20260204_103000.json
```

---

## よくある質問

### Q: 会話履歴はどこに保存されますか？

**A**: デフォルトでは以下の場所にSQLiteデータベースとして保存されます：

```
F:\llm-smart-router\data\conversations.db
```

保存先は設定で変更可能です：

```python
from conversation.db_manager import ConversationDB

db = ConversationDB("custom/path/database.db")
```

### Q: 古い会話は自動的に削除されますか？

**A**: いいえ、自動削除はありません。手動で削除するか、以下のスクリプトで整理してください：

```python
from datetime import datetime, timedelta

# 30日以上前の会話をアーカイブ
old_conversations = manager.list_conversations(
    date_to=datetime.now() - timedelta(days=30)
)

for conv in old_conversations:
    manager.archive_conversation(conv.id)
```

### Q: 会話タイトルを変更できますか？

**A**: はい、以下の方法で変更できます：

```python
manager.update_conversation(
    conversation_id=conv_id,
    title="新しいタイトル"
)
```

### Q: 同時にいくつの会話を保持できますか？

**A**: 技術的な制限はありません。パフォーマンスを考慮して、
- アクティブ会話: 100件程度
- アーカイブ: 数千件

を目安に管理することをお勧めします。

### Q: 検索で正規表現は使えますか？

**A**: 現在のバージョンでは部分一致検索のみ対応しています。正規表現は今後のアップデートで検討されています。

```python
# 現在対応している検索
results = db.search_conversations("Python")  # 部分一致

# 複数キーワード（AND検索相当）
results = db.search_messages("Python AND Django")
```

### Q: 会話を共有することはできますか？

**A**: JSONエクスポート機能を使用して会話をファイルとして共有できます：

1. 会話をエクスポート
2. JSONファイルを送信
3. 相手はインポート機能で読み込み

---

## トラブルシューティング

### 会話が表示されない

```
対処法:
1. アプリを再起動
2. データベースファイルの確認
   → F:\llm-smart-router\data\conversations.db
3. ログファイルの確認
   → F:\llm-smart-router\logs\
```

### 検索が遅い

大量の会話がある場合、インデックスの再構築を試行：

```sql
-- SQLiteで実行
REINDEX;
ANALYZE;
```

### エクスポートに失敗する

1. ディスク容量を確認
2. 出力先フォルダの書き込み権限を確認
3. ファイルが開かれていないか確認

---

## 関連ドキュメント

- [API リファレンス](./api_reference.md) - 詳細なAPI仕様
- [開発者ガイド](./developer_guide.md) - カスタマイズ方法
- [データベース設計](./database_schema.md) - スキーマ詳細

---

## フィードバック

会話履歴管理機能に関するフィードバックや機能リクエストは、
以下の方法でお寄せください：

- 💬 Discord: #feedback チャンネル
- 📧 Email: support@llm-router.local
- 🐛 GitHub Issues: バグ報告・機能要望

---

**Last Updated**: 2026-02-04  
**Version**: 1.0.0
