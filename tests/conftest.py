"""
LLM Smart Router - テスト用共通フィクスチャ

使用方法:
    pytest tests/ -v
"""
import sys
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock
from datetime import datetime

# パス設定
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from conversation.db_manager import ConversationDB
from conversation.conversation_manager import ConversationManager


# ============================================================
# 基本フィクスチャ
# ============================================================

@pytest.fixture
def temp_dir():
    """テスト用一時ディレクトリ"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_db_path(temp_dir):
    """テスト用DBパス"""
    return temp_dir / "test.db"


@pytest.fixture
def conversation_db(temp_db_path):
    """テスト用ConversationDBインスタンス"""
    db = ConversationDB(str(temp_db_path))
    yield db


@pytest.fixture
def conversation_manager(temp_dir):
    """テスト用ConversationManagerインスタンス"""
    class MockTitleGenerator:
        def generate(self, text: str) -> str:
            if not text:
                return "新規会話"
            title = text[:20].strip()
            if len(text) > 20:
                title += "..."
            return title
    
    manager = ConversationManager(
        storage_path=str(temp_dir / "conversations"),
        title_generator=MockTitleGenerator()
    )
    yield manager


# ============================================================
# データファクトリーヘルパー
# ============================================================

class ConversationFactory:
    """会話データ作成ヘルパー"""
    
    def __init__(self, db: ConversationDB):
        self.db = db
    
    def create_conversation(self, title: str = "Test Conversation", 
                           topic_id: int = None) -> int:
        """会話を作成"""
        return self.db.create_conversation(title, topic_id)
    
    def create_topic(self, name: str = "Test Topic") -> int:
        """トピックを作成"""
        return self.db.create_topic(name)
    
    def add_message(self, conversation_id: int, role: str = "user",
                   content: str = "Test message", model: str = None) -> int:
        """メッセージを追加"""
        return self.db.add_message(conversation_id, role, content, model)
    
    def create_conversation_with_messages(self, message_count: int = 5,
                                         title: str = "Test") -> tuple:
        """メッセージ付き会話を作成"""
        conv_id = self.create_conversation(title)
        for i in range(message_count):
            role = "user" if i % 2 == 0 else "assistant"
            self.add_message(conv_id, role, f"Message {i}")
        return conv_id, message_count


@pytest.fixture
def factory(conversation_db):
    """ConversationFactoryインスタンス"""
    return ConversationFactory(conversation_db)


# ============================================================
# モックフィクスチャ
# ============================================================

@pytest.fixture
def mock_callback():
    """モックコールバック"""
    return Mock()


@pytest.fixture
def mock_title_generator():
    """モックタイトル生成器"""
    mock = Mock()
    mock.generate.return_value = "Mocked Title"
    return mock


# ============================================================
# テストデータ
# ============================================================

EDGE_CASE_STRINGS = [
    ("", "空文字"),
    ("   ", "空白のみ"),
    ("a" * 10000, "非常に長い文字列"),
    ("日本語テスト🎌", "日本語と絵文字"),
    ("<script>alert('xss')</script>", "HTMLタグ"),
    ("' OR '1'='1", "SQLインジェクション試行"),
    ("\\n\\t\\r", "エスケープ文字"),
    ("你好世界", "中国語"),
    ("🎉🎊🎁", "絵文字のみ"),
]


@pytest.fixture(params=EDGE_CASE_STRINGS, ids=[name for _, name in EDGE_CASE_STRINGS])
def edge_case_string(request):
    """エッジケース文字列パラメータ"""
    return request.param[0]


# ============================================================
# アサーションヘルパー
# ============================================================

def assert_conversation_exists(db: ConversationDB, conv_id: int):
    """会話が存在することをアサート"""
    conv = db.get_conversation(conv_id)
    assert conv is not None, f"Conversation {conv_id} should exist"
    return conv


def assert_conversation_not_exists(db: ConversationDB, conv_id: int):
    """会話が存在しないことをアサート"""
    conv = db.get_conversation(conv_id)
    assert conv is None, f"Conversation {conv_id} should not exist"


def assert_message_count(db: ConversationDB, conv_id: int, expected_count: int):
    """メッセージ数をアサート"""
    messages = db.get_messages(conv_id)
    actual_count = len(messages)
    assert actual_count == expected_count, \
        f"Expected {expected_count} messages, got {actual_count}"
    return messages


def assert_topic_exists(db: ConversationDB, topic_id: int):
    """トピックが存在することをアサート"""
    topics = db.get_topics()
    topic_ids = [t['id'] for t in topics]
    assert topic_id in topic_ids, f"Topic {topic_id} should exist"


# ============================================================
# Pytest設定
# ============================================================

def pytest_configure(config):
    """Pytest設定"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "edge_case: marks tests as edge case tests"
    )
