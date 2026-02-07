#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
デザイントークン定義

色、スペーシング、角丸、タイポグラフィ、ローカライズ文字列を一元管理。
全GUIファイルはこのモジュールからトークンをインポートして使用する。
"""


# ============================================================
# カラーパレット
# ============================================================

class Colors:
    """統一カラーパレット (ダークテーマ)"""

    # サーフェス階層 (深い順)
    SURFACE_0 = '#0a0a0f'       # ウィンドウ背景
    SURFACE_1 = '#10101a'       # メインコンテンツ
    SURFACE_2 = '#161625'       # カード・サイドバー
    SURFACE_3 = '#1c1c30'       # ホバー・浮上要素
    SURFACE_4 = '#252545'       # アクティブ・選択状態

    # 後方互換エイリアス
    BG_DARK = SURFACE_0
    BG_MAIN = SURFACE_1
    BG_CARD = SURFACE_2
    BG_CARD_HOVER = SURFACE_3
    BG_INPUT = '#12121f'
    BG_TERTIARY = '#1e1e35'
    BG_HOVER = SURFACE_4

    # ボーダー
    BORDER = '#252540'
    BORDER_FOCUS = '#6366f1'

    # プライマリ (インディゴ — ブランドカラー)
    PRIMARY = '#6366f1'
    PRIMARY_LIGHT = '#818cf8'
    PRIMARY_DARK = '#4f46e5'
    PRIMARY_GLOW = '#6366f140'

    # セカンダリ (エメラルド — 成功・ローカル)
    SECONDARY = '#10b981'
    SECONDARY_LIGHT = '#34d399'

    # アクセント
    ACCENT = '#f59e0b'          # アンバー — ローカルモデル・警告
    DANGER = '#ef4444'          # レッド — エラー・停止
    CYAN = '#06b6d4'            # シアン — クラウド・情報

    # テキスト
    TEXT = '#eef2ff'
    TEXT_PRIMARY = '#eef2ff'
    TEXT_DIM = '#94a3b8'
    TEXT_MUTED = '#64748b'

    # ステータスカラー
    STATUS_ONLINE = '#10b981'   # 稼働中
    STATUS_WARNING = '#f59e0b'  # 劣化・切替中
    STATUS_ERROR = '#ef4444'    # オフライン・エラー
    STATUS_UNKNOWN = '#64748b'  # 未確認
    STATUS_INFO = '#06b6d4'     # 情報

    # 設定ソースバッジ
    CONFIG_YAML = '#10b981'     # config.yaml (緑)
    CONFIG_ENV = '#3b82f6'      # .env (青)
    CONFIG_JSON = '#a855f7'     # data/*.json (紫)
    CONFIG_KEYSTORE = '#06b6d4' # OSキーストア (シアン)

    # セマンティック
    WARNING = '#f59e0b'
    ERROR = '#ef4444'

    # グラデーション
    GRADIENT_START = '#6366f1'
    GRADIENT_END = '#8b5cf6'


# ============================================================
# スペーシング
# ============================================================

class Spacing:
    """統一スペーシング (px)"""
    XS = 4      # コンパクトな行内ギャップ
    SM = 8      # 標準要素間ギャップ
    MD = 12     # セクション内パディング
    LG = 16     # カード・パネル内パディング
    XL = 24     # セクション間ギャップ
    XXL = 32    # ページレベルマージン


# ============================================================
# 角丸
# ============================================================

class Radius:
    """統一ボーダーラジアス (px)"""
    SM = 4      # 小さなボタン、インラインバッジ
    MD = 8      # 入力フィールド、ドロップダウン、リストアイテム
    LG = 12     # カード、パネル、グループボックス
    XL = 16     # ダイアログ、モーダル
    PILL = 999  # ピル型バッジ


# ============================================================
# タイポグラフィ
# ============================================================

class Typography:
    """統一フォント設定"""
    FAMILY = '"Segoe UI", "Yu Gothic UI", "Meiryo", "Noto Sans JP", sans-serif'
    FAMILY_MONO = '"Cascadia Code", "Source Han Code JP", Consolas, monospace'

    SIZE_XS = 10    # カウンター、タイムスタンプ
    SIZE_SM = 11    # 二次ラベル、バッジテキスト
    SIZE_MD = 13    # 本文、フォームラベル
    SIZE_LG = 15    # セクションヘッダー
    SIZE_XL = 18    # ページタイトル
    SIZE_XXL = 22   # 統計カード値

    WEIGHT_NORMAL = 400
    WEIGHT_MEDIUM = 500
    WEIGHT_SEMIBOLD = 600
    WEIGHT_BOLD = 700

    LINE_HEIGHT = 1.7   # 日本語テキスト用


# ============================================================
# 日本語ローカライズ文字列
# ============================================================

class L10n:
    """全UI文字列の日本語定義"""

    # アプリ
    APP_TITLE = "LLM Smart Router Pro"
    APP_VERSION = "3.0.0"

    # メニューバー
    MENU_FILE = "ファイル"
    MENU_EDIT = "編集"
    MENU_VIEW = "表示"
    MENU_SETTINGS = "設定"
    MENU_TOOLS = "ツール"
    MENU_HELP = "ヘルプ"

    # ファイルメニュー
    FILE_NEW = "新規会話"
    FILE_OPEN = "開く"
    FILE_SAVE = "保存"
    FILE_EXPORT = "エクスポート"
    FILE_IMPORT = "インポート"
    FILE_QUIT = "終了"

    # 編集メニュー
    EDIT_COPY = "コピー"
    EDIT_PASTE = "貼り付け"
    EDIT_CUT = "切り取り"
    EDIT_CLEAR = "クリア"
    EDIT_SELECT_ALL = "すべて選択"

    # 表示メニュー
    VIEW_SIDEBAR = "サイドバー"
    VIEW_DASHBOARD = "ダッシュボード"
    VIEW_FONT_LARGER = "文字を大きく"
    VIEW_FONT_SMALLER = "文字を小さく"
    VIEW_FONT_RESET = "文字サイズリセット"

    # ヘルプメニュー
    HELP_SHORTCUTS = "ショートカット一覧"
    HELP_ABOUT = "このアプリについて"

    # サイドバー
    SIDEBAR_TITLE = "会話一覧"
    SIDEBAR_NEW = "+ 新規"
    SIDEBAR_SEARCH = "会話を検索..."
    SIDEBAR_EMPTY_TITLE = "会話がありません"
    SIDEBAR_EMPTY_DESC = "「+ 新規」ボタンで最初の会話を作成しましょう"

    # 日付グループ
    DATE_TODAY = "今日"
    DATE_YESTERDAY = "昨日"
    DATE_THIS_WEEK = "今週"
    DATE_OLDER = "それ以前"

    # 時間フィルター
    FILTER_ALL_TIME = "すべて"
    FILTER_TODAY = "今日"
    FILTER_YESTERDAY = "昨日"
    FILTER_THIS_WEEK = "今週"
    FILTER_THIS_MONTH = "今月"

    # モデルフィルター
    FILTER_ALL_MODELS = "すべてのモデル"

    # チャットパネル
    CHAT_TITLE = "チャット"
    CHAT_INPUT_PLACEHOLDER = "質問やタスクを入力..."
    CHAT_EXECUTE = "実行"
    CHAT_STOP = "停止"
    CHAT_CLEAR_INPUT = "入力クリア"
    CHAT_COPY_OUTPUT = "出力をコピー"

    # モデル選択
    MODEL_TITLE = "モデル"
    MODEL_AUTO = "自動（推奨）"
    MODEL_LOCAL = "ローカルLLM"
    MODEL_CLOUD = "クラウドAPI"
    MODEL_TOOLTIP = (
        "使用するモデルを選択\n"
        "自動: 入力内容に応じて最適なモデルを自動選択\n"
        "ローカル: ローカルLLM（LM Studio等）を使用\n"
        "クラウド: クラウドAPI（Claude等）を使用"
    )
    MODEL_ONLINE = "オンライン"
    MODEL_CONFIGURED = "設定済み"
    MODEL_NO_KEY = "キー未設定"

    # プリセット
    PRESET_TITLE = "プリセット"
    PRESET_AUTO = "自動検出"

    # 画像入力
    IMAGE_TITLE = "画像入力"
    IMAGE_DROP = "画像をドラッグ＆ドロップ\nまたはクリックして選択"
    IMAGE_PASTE = "貼り付け"
    IMAGE_CLEAR = "クリア"

    # ステータスバー
    STATUS_READY = "待機中"
    STATUS_PROCESSING = "処理中..."
    STATUS_STOPPED = "停止しました"
    STATUS_RUNTIMES = "ランタイム: {count}基稼働"
    STATUS_API_KEYS = "APIキー: {configured}/{total}設定済み"

    # タブ
    TAB_UNTITLED = "無題"
    TAB_NEW = "新規会話"
    TAB_CLOSE = "閉じる"
    TAB_CLOSE_OTHERS = "他のタブを閉じる"
    TAB_CLOSE_RIGHT = "右のタブを閉じる"
    TAB_CLOSE_ALL = "すべて閉じる"

    # コンテキストメニュー
    CTX_OPEN = "開く"
    CTX_PIN = "ピン留め"
    CTX_UNPIN = "ピン解除"
    CTX_RENAME = "名前を変更"
    CTX_DELETE = "削除"
    CTX_ARCHIVE = "アーカイブ"

    # メッセージロール
    ROLE_USER = "あなた"
    ROLE_ASSISTANT = "アシスタント"
    ROLE_SYSTEM = "システム"

    # 設定ダイアログ
    SETTINGS_TITLE = "設定"
    SETTINGS_SAVE = "保存"
    SETTINGS_CANCEL = "キャンセル"
    SETTINGS_RESET = "リセット"

    # 設定セクション
    SECTION_CONNECTION = "接続・認証"
    SECTION_RUNTIME = "ランタイム管理"
    SECTION_ROUTING = "ルーティング"
    SECTION_ADVANCED = "詳細設定"

    # 接続・認証
    API_KEY_LABEL = "APIキー"
    API_KEY_SHOW = "表示"
    API_KEY_HIDE = "隠す"
    API_KEY_TEST = "接続テスト"
    API_KEY_DELETE = "キー削除"
    API_KEY_SAVED = "保存済み"
    API_KEY_NOT_SET = "未設定"
    API_KEY_VALID = "接続成功"
    API_KEY_INVALID = "接続失敗"
    ENDPOINT_LABEL = "エンドポイント"

    # ランタイム管理
    RUNTIME_START = "起動"
    RUNTIME_STOP = "停止"
    RUNTIME_CHECK = "確認"
    RUNTIME_SCAN = "スキャン"
    RUNTIME_RUNNING = "稼働中"
    RUNTIME_STOPPED = "停止中"
    RUNTIME_MODELS = "モデル一覧"

    # Ollama
    OLLAMA_PULL = "モデル取得"
    OLLAMA_DELETE = "モデル削除"
    OLLAMA_REFRESH = "更新"

    # llama.cpp
    LLAMACPP_BROWSE = "GGUFファイル選択"

    # ルーティング設定
    ROUTING_DEFAULT_MODEL = "デフォルトモデル"
    ROUTING_CONFIDENCE = "確信度閾値"
    ROUTING_CONFIDENCE_DESC = "この閾値未満の場合、フォールバックモデルを使用"
    ROUTING_TIMEOUT_LOCAL = "ローカルタイムアウト (秒)"
    ROUTING_TIMEOUT_CLOUD = "クラウドタイムアウト (秒)"
    ROUTING_FALLBACK_TITLE = "フォールバック優先順位"
    ROUTING_FALLBACK_DESC = "上から順に試行されます。ドラッグで並べ替え可能"
    ROUTING_COST_NOTIFY = "コスト通知"
    ROUTING_COST_THRESHOLD = "通知閾値 (円)"

    # 詳細設定
    ADVANCED_PRESET = "プリセット管理"
    ADVANCED_CACHE = "キャッシュ設定"
    ADVANCED_CACHE_ENABLED = "キャッシュ有効"
    ADVANCED_CACHE_TTL = "TTL (秒)"
    ADVANCED_CACHE_MAX = "最大エントリ数"
    ADVANCED_OPENCLAW = "OpenClaw連携"
    ADVANCED_OPENCLAW_SYNC = "モデルスキャン後に自動同期"
    ADVANCED_OPENCLAW_FALLBACK = "フォールバック時に同期"
    ADVANCED_OPENCLAW_PATH = "設定ファイルパス"
    ADVANCED_LOGGING = "ログ設定"
    ADVANCED_LOG_LEVEL = "ログレベル"
    ADVANCED_DISCORD = "Discord Bot"
    ADVANCED_DISCORD_ENABLED = "Discord Bot有効"
    ADVANCED_DISCORD_TOKEN = "Botトークン"
    ADVANCED_DISCORD_PREFIX = "コマンドプレフィックス"
    ADVANCED_DISCORD_ADMIN_IDS = "管理者ID（カンマ区切り）"
    ADVANCED_DISCORD_RATE_LIMIT = "レートリミット (ミリ秒)"

    # LM Studio
    LMSTUDIO_TITLE = "LM Studio"

    # OpenClaw (拡張)
    OPENCLAW_ENABLED = "OpenClaw連携有効"

    # ランタイム共通
    RUNTIME_ENABLED = "自動起動"

    # 設定ソースバッジ
    SOURCE_YAML = "YAML"
    SOURCE_ENV = ".env"
    SOURCE_JSON = "JSON"
    SOURCE_KEYSTORE = "OS"
    SOURCE_LIVE = "即時反映"
    SOURCE_RESTART = "要再起動"

    # エラー
    ERROR_EMPTY_INPUT = "入力が空です"
    ERROR_CONFIG_NOT_FOUND = "config.yaml が見つかりません"
    ERROR_CONNECTION_FAILED = "接続に失敗しました"
    ERROR_SAVE_FAILED = "保存に失敗しました"

    # 確認ダイアログ
    CONFIRM_DELETE = "削除しますか？"
    CONFIRM_RESET = "設定をリセットしますか？"
    CONFIRM_OVERWRITE = "上書きしますか？"

    # コスト警告
    COST_WARNING_TITLE = "課金警告"
    COST_WARNING_MSG = (
        "ローカルLLMが利用できなかったため、"
        "有料のクラウドAPIにフォールバックしました。\n"
        "継続使用すると課金が発生します。"
    )

    # モデルバッジ
    BADGE_AUTO = "Auto"
    BADGE_LOCAL = "Local"
    BADGE_CLOUD = "Cloud"
    BADGE_TOOLTIP = "現在選択中のモデル\nAuto=緑 / Local=黄 / Cloud=青"

    # ダッシュボード
    DASHBOARD_TITLE = "ダッシュボード"
    DASHBOARD_TOTAL_REQUESTS = "総リクエスト数"
    DASHBOARD_COST_SAVINGS = "コスト削減額"
    DASHBOARD_AVG_RESPONSE = "平均応答時間"

    # ツールチップ
    TIP_PROGRESS = "リクエスト処理中..."
    TIP_MEMORY = "アプリケーションのメモリ使用量"
    TIP_STATUS_DOT = "モデル接続状態（緑=正常 / 黄=切替中 / 赤=エラー）"
    TIP_SCAN = "ローカルLLMランタイムを再スキャン"
    TIP_EXECUTE = "入力内容をLLMに送信して応答を取得 (Ctrl+Enter)"
    TIP_STOP = "実行中のリクエストを中止 (Esc)"
