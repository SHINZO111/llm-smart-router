"""
会話管理モジュール - Conversation Module

LLM Smart Routerの会話履歴管理機能を提供します。
"""

# メインクラス
from .conversation_manager import ConversationManager
from .title_generator import (
    TitleGenerator,
    SimpleTitleGenerator,
    TitleGenerationMethod,
    create_title_generator
)

# バージョン情報
__version__ = "0.1.0"
__all__ = [
    # メインクラス
    "ConversationManager",
    "TitleGenerator",
    "SimpleTitleGenerator",
    "TitleGenerationMethod",
    "create_title_generator",
]
