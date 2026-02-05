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
    description="Conversation History Management API for LLM Smart Router",
    version="1.0.0",
    lifespan=lifespan
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
