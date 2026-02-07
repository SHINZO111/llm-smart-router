"""
FastAPI Application Entry Point

LLM Smart Router - Conversation History API Server
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.routes import router
from api.openai_compat import openai_router

# ログローテーション設定
def setup_logging():
    """ログローテーションを設定（最大50MB: 10MB×5ファイル）"""
    log_dir = project_root.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "api_server.log"

    # RotatingFileHandler: 10MB毎にローテーション、最大5ファイル保持
    handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)

    # ルートロガーに追加
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)

    # コンソール出力も追加
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

# ロギング初期化
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    logger.info("LLM Smart Router API Server starting...")
    yield
    # Shutdown
    logger.info("LLM Smart Router API Server shutting down...")


# Create FastAPI application
app = FastAPI(
    title="LLM Smart Router API",
    description=(
        "LLM Smart Routerの統合REST API。\n\n"
        "## 機能\n"
        "- **会話管理** (`/api/v1/conversations`): 会話のCRUD、メッセージ管理、検索、エクスポート/インポート\n"
        "- **トピック管理** (`/api/v1/topics`): 会話の階層的カテゴリ管理\n"
        "- **ルーティング** (`/api/v1/router`): ローカル/クラウドLLMへのインテリジェントルーティング\n"
        "- **モデル検出** (`/api/v1/models`): ローカルランタイム自動検出・レジストリ\n"
        "- **OpenAI互換** (`/v1/chat/completions`): nanobot/LiteLLM等からの利用\n\n"
        "## 認証\n"
        "ローカル利用のためAPI認証は不要。CORS設定は`ALLOWED_ORIGINS`環境変数で制御。"
    ),
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Conversations", "description": "会話のCRUD操作"},
        {"name": "Messages", "description": "メッセージの管理"},
        {"name": "Topics", "description": "トピック（カテゴリ）管理"},
        {"name": "Search", "description": "全文検索・フィルタリング"},
        {"name": "Export/Import", "description": "会話のエクスポート・インポート"},
        {"name": "Router", "description": "LLMルーティングエンジン連携"},
        {"name": "Models", "description": "モデル検出・レジストリ"},
        {"name": "OpenAI Compatible", "description": "OpenAI互換API（nanobot/LiteLLM対応）"},
        {"name": "Stats", "description": "統計情報"},
    ],
)

# CORS middleware
# Production: Set ALLOWED_ORIGINS environment variable (comma-separated)
# Example: ALLOWED_ORIGINS=http://localhost:3000,https://myapp.com
_allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080").split(",")
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
    max_age=600,
)

# Include routers
app.include_router(router, prefix="/api/v1")
app.include_router(openai_router, prefix="/v1", tags=["OpenAI Compatible"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "LLM Smart Router API",
        "version": "1.0.0",
        "docs_url": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    _debug = os.getenv("DEBUG", "false").lower() == "true"
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=_debug,
        log_level="debug" if _debug else "info"
    )
