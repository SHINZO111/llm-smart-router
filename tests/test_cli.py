"""
Tests for CLI commands
"""
import sys
import pytest
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import Mock, patch

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from cli.commands import cli
from conversation.conversation_manager import ConversationManager
from models.conversation import Conversation, Topic, ConversationStatus
from models.message import Message, MessageRole


runner = CliRunner()


@pytest.fixture
def mock_manager():
    """Create a mock conversation manager"""
    manager = Mock(spec=ConversationManager)
    return manager


class TestListCommand:
    """Tests for list command"""
    
    def test_list_help(self):
        """Test list command help"""
        result = runner.invoke(cli, ['list', '--help'])
        assert result.exit_code == 0
        assert '--user' in result.output
        assert '--topic' in result.output
    
    def test_list_empty(self, mock_manager):
        """Test list with no conversations"""
        mock_manager.list_conversations.return_value = []
        
        with patch('cli.commands.get_manager', return_value=mock_manager):
            result = runner.invoke(cli, ['list'])
            assert result.exit_code == 0
            assert 'No conversations found' in result.output or result.output == ''


class TestShowCommand:
    """Tests for show command"""
    
    def test_show_not_found(self):
        """Test showing non-existent conversation"""
        with patch('cli.commands.ConversationManager') as mock_mgr_class:
            mock_manager = Mock()
            mock_manager.get_conversation.return_value = None
            mock_mgr_class.return_value = mock_manager
            
            result = runner.invoke(cli, ['show', 'fake-id'])
            assert result.exit_code == 1
            assert 'not found' in result.output


class TestCreateCommand:
    """Tests for create command"""
    
    def test_create_conversation(self):
        """Test creating a conversation"""
        mock_conv = Mock()
        mock_conv.id = 'test-id-123'
        mock_conv.title = 'Test Title'
        mock_conv.created_at = Mock()
        mock_conv.created_at.strftime = Mock(return_value='2024-01-01 12:00:00')
        
        with patch('cli.commands.ConversationManager') as mock_mgr_class:
            mock_manager = Mock()
            mock_manager.create_conversation.return_value = mock_conv
            mock_manager.get_conversation.return_value = mock_conv
            mock_mgr_class.return_value = mock_manager
            
            result = runner.invoke(cli, ['create', '--title', 'Test Title'])
            assert result.exit_code == 0
            assert 'Created' in result.output or 'test-id-123' in result.output


class TestSearchCommand:
    """Tests for search command"""
    
    def test_search_no_results(self):
        """Test search with no results"""
        with patch('cli.commands.ConversationManager') as mock_mgr_class:
            mock_manager = Mock()
            mock_manager.search_conversations.return_value = []
            mock_mgr_class.return_value = mock_manager
            
            result = runner.invoke(cli, ['search', 'nonexistentquery12345'])
            assert result.exit_code == 0


class TestExportCommand:
    """Tests for export command"""
    
    def test_export_requires_args(self):
        """Test export requires conversation_id, --all, or --topic"""
        result = runner.invoke(cli, ['export'])
        assert result.exit_code != 0
        assert 'Error' in result.output or 'conversation_id' in result.output


class TestTopicCommand:
    """Tests for topic commands"""
    
    def test_topics_list_empty(self):
        """Test topics list when empty"""
        with patch('cli.commands.ConversationManager') as mock_mgr_class:
            mock_manager = Mock()
            mock_manager.get_all_topics.return_value = []
            mock_mgr_class.return_value = mock_manager
            
            result = runner.invoke(cli, ['topics'])
            assert result.exit_code == 0
            assert 'No topics found' in result.output


class TestStatsCommand:
    """Tests for stats command"""
    
    def test_stats(self):
        """Test stats command"""
        mock_stats = {
            'total_conversations': 10,
            'active_conversations': 5,
            'total_messages': 100,
            'today_conversations': 2,
            'average_messages_per_conversation': 10.0
        }
        
        with patch('cli.commands.ConversationManager') as mock_mgr_class:
            mock_manager = Mock()
            mock_manager.get_stats.return_value = mock_stats
            mock_mgr_class.return_value = mock_manager
            
            result = runner.invoke(cli, ['stats'])
            assert result.exit_code == 0
            assert '10' in result.output  # Total conversations


class TestJsonOutput:
    """Tests for JSON output option"""
    
    def test_list_json_output(self):
        """Test list with JSON output"""
        mock_conv = Mock()
        mock_conv.to_dict.return_value = {'id': 'test', 'title': 'Test'}
        
        with patch('cli.commands.ConversationManager') as mock_mgr_class:
            mock_manager = Mock()
            mock_manager.list_conversations.return_value = [mock_conv]
            mock_mgr_class.return_value = mock_manager
            
            result = runner.invoke(cli, ['list', '--json-output'])
            assert result.exit_code == 0
            assert 'test' in result.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
