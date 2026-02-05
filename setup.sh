#!/usr/bin/env bash
# ============================================================
# LLM Smart Router - ワンクリック セットアップ (macOS/Linux)
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

ERRORS=0
WARNINGS=0

# 色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

ok()   { echo -e "  ${GREEN}OK${NC}  $1"; }
warn() { echo -e "  ${YELLOW}!${NC}   $1"; WARNINGS=$((WARNINGS+1)); }
fail() { echo -e "  ${RED}X${NC}   $1"; ERRORS=$((ERRORS+1)); }

echo ""
echo "  ╔══════════════════════════════════════════════════════════════╗"
echo "  ║                                                              ║"
echo "  ║         LLM Smart Router - セットアップ                      ║"
echo "  ║                                                              ║"
echo "  ╚══════════════════════════════════════════════════════════════╝"
echo ""

# ============================================================
# ステップ 1: 前提チェック
# ============================================================
echo "  [1/6] 前提条件を確認中..."
echo "  ─────────────────────────────────────────────────"
echo ""

# -- Python --
PYTHON_CMD=""
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
fi

if [ -z "$PYTHON_CMD" ]; then
    fail "Python が見つかりません"
    echo "      https://www.python.org/downloads/ からインストールしてください"
    exit 1
else
    ok "$($PYTHON_CMD --version 2>&1)"
fi

# -- pip --
if $PYTHON_CMD -m pip --version &>/dev/null; then
    ok "pip 利用可能"
else
    fail "pip が見つかりません"
fi

# -- Node.js --
HAS_NODE=0
if command -v node &>/dev/null; then
    ok "Node.js $(node --version 2>&1)"
    HAS_NODE=1
else
    warn "Node.js が見つかりません（オプション）"
    echo "      https://nodejs.org/ からインストールすると全機能が使えます"
fi
echo ""

# ============================================================
# ステップ 2: 仮想環境 + 依存関係
# ============================================================
echo "  [2/6] 依存関係をインストール中..."
echo "  ─────────────────────────────────────────────────"
echo ""

# -- 仮想環境 --
if [ ! -d "venv" ]; then
    echo "  仮想環境を作成中..."
    $PYTHON_CMD -m venv venv
    ok "仮想環境を作成しました"
else
    ok "仮想環境は既に存在します"
fi

source venv/bin/activate

# -- Python パッケージ (コア) --
echo "  Python パッケージをインストール中（コア）..."
pip install -q -r requirements.txt && ok "コアパッケージ インストール完了" || fail "コアパッケージのインストールに失敗"

# -- Python パッケージ (GUI) --
echo "  Python パッケージをインストール中（GUI）..."
pip install -q -r requirements-gui.txt 2>/dev/null && ok "GUIパッケージ インストール完了" || warn "GUIパッケージのインストールに失敗"

# -- Node.js パッケージ --
if [ "$HAS_NODE" = "1" ] && [ -f "package.json" ]; then
    echo "  Node.js パッケージをインストール中..."
    npm install --silent 2>/dev/null && ok "Node.js パッケージ インストール完了" || warn "Node.js パッケージのインストールに失敗"
fi
echo ""

# ============================================================
# ステップ 3: .env ファイル設定
# ============================================================
echo "  [3/6] API キーを設定中..."
echo "  ─────────────────────────────────────────────────"
echo ""

if [ -f ".env" ]; then
    ok ".env ファイルは既に存在します（スキップ）"
else
    if [ -f ".env.example" ]; then
        cp .env.example .env
        ok ".env ファイルを作成しました"
    else
        echo "# LLM Smart Router 環境設定" > .env
        ok ".env ファイルを新規作成しました"
    fi

    echo ""
    echo "  APIキーを設定します。後で設定する場合はそのまま Enter を押してください。"
    echo ""

    # -- Anthropic --
    echo -n "  Anthropic API Key (sk-ant-...): "
    read -s KEY_INPUT
    echo ""
    if [ -n "$KEY_INPUT" ]; then
        printf '%s\n' "ANTHROPIC_API_KEY=${KEY_INPUT}" >> .env
        ok "Anthropic API Key を保存しました"
    else
        echo "  -- スキップ"
    fi

    # -- OpenAI --
    echo -n "  OpenAI API Key (sk-...): "
    read -s KEY_INPUT
    echo ""
    if [ -n "$KEY_INPUT" ]; then
        printf '%s\n' "OPENAI_API_KEY=${KEY_INPUT}" >> .env
        ok "OpenAI API Key を保存しました"
    else
        echo "  -- スキップ"
    fi

    # -- Google --
    echo -n "  Google API Key: "
    read -s KEY_INPUT
    echo ""
    if [ -n "$KEY_INPUT" ]; then
        printf '%s\n' "GOOGLE_API_KEY=${KEY_INPUT}" >> .env
        ok "Google API Key を保存しました"
    else
        echo "  -- スキップ"
    fi

    # -- OpenRouter --
    echo -n "  OpenRouter API Key: "
    read -s KEY_INPUT
    echo ""
    if [ -n "$KEY_INPUT" ]; then
        printf '%s\n' "OPENROUTER_API_KEY=${KEY_INPUT}" >> .env
        ok "OpenRouter API Key を保存しました"
    else
        echo "  -- スキップ"
    fi

    # .env パーミッション制限（APIキー保護）
    chmod 600 .env
fi
echo ""

# ============================================================
# ステップ 4: ディレクトリ作成
# ============================================================
echo "  [4/6] ディレクトリを準備中..."
echo "  ─────────────────────────────────────────────────"
echo ""

mkdir -p data logs cache queue
ok "data/ logs/ cache/ queue/ を確認しました"
echo ""

# ============================================================
# ステップ 5: 初回モデルスキャン
# ============================================================
echo "  [5/6] LLM ランタイムをスキャン中..."
echo "  ─────────────────────────────────────────────────"
echo ""

# .env を安全に読み込み（source ではなく行単位パース）
if [ -f ".env" ]; then
    while IFS='=' read -r key value; do
        # コメント・空行をスキップ
        key=$(echo "$key" | tr -d '[:space:]')
        [ -z "$key" ] && continue
        case "$key" in \#*) continue ;; esac
        # 値の前後クオートを除去
        value=$(echo "$value" | sed "s/^['\"]//;s/['\"]$//")
        # 許可リストのキーのみexport
        case "$key" in
            ANTHROPIC_API_KEY|OPENAI_API_KEY|GOOGLE_API_KEY|OPENROUTER_API_KEY|LM_STUDIO_ENDPOINT|LOG_LEVEL|EXCHANGE_RATE)
                export "$key=$value"
                ;;
        esac
    done < .env
fi

cd "$SCRIPT_DIR/src"
$PYTHON_CMD -m scanner scan --timeout 3.0 2>/dev/null || true
cd "$SCRIPT_DIR"
echo ""

# ============================================================
# ステップ 6: 動作検証
# ============================================================
echo "  [6/6] インストールを検証中..."
echo "  ─────────────────────────────────────────────────"
echo ""

cd "$SCRIPT_DIR/src"
$PYTHON_CMD -m healthcheck 2>/dev/null || true
cd "$SCRIPT_DIR"
echo ""

# ============================================================
# 完了
# ============================================================
echo "  ╔══════════════════════════════════════════════════════════════╗"
echo "  ║                                                              ║"
echo "  ║         セットアップ完了！                                   ║"
echo "  ║                                                              ║"
echo "  ╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  次のステップ:"
echo ""
echo "    python src/gui/main_window.py  ... GUI アプリを起動"
echo "    python -m launcher             ... フルチェーン起動"
echo "    uvicorn src.api.main:app       ... API サーバーのみ起動"
echo ""
echo "  APIキーを後で変更するには .env ファイルを編集してください。"
echo "  セットアップの再検証は  python -m healthcheck  で実行できます。"
echo ""

if [ $ERRORS -gt 0 ]; then
    echo -e "  ${RED}[!] $ERRORS 個のエラーがあります。${NC}"
fi
if [ $WARNINGS -gt 0 ]; then
    echo -e "  ${YELLOW}[i] $WARNINGS 個の警告があります。${NC}"
fi

deactivate 2>/dev/null || true
