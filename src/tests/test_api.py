"""
Tests for FastAPI routes
"""
import sys
import pytest
import uuid
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi.testclient import TestClient
from api.main import app


client = TestClient(app)


class TestHealthEndpoints:
    """Tests for health check endpoints"""
    
    def test_root(self):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "LLM Smart Router API"
        assert "version" in data
    
    def test_health_check(self):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestConversationEndpoints:
    """Tests for conversation CRUD endpoints"""
    
    def test_list_conversations_empty(self):
        """Test listing conversations (may be empty)"""
        response = client.get("/api/v1/conversations")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_create_conversation(self):
        """Test creating a conversation"""
        response = client.post(
            "/api/v1/conversations",
            json={"user_id": "test_user", "first_message": "Hello!"}
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["user_id"] == "test_user"
        assert data["status"] == "active"
        return data["id"]
    
    def test_get_conversation(self):
        """Test getting a conversation"""
        # First create a conversation
        create_resp = client.post(
            "/api/v1/conversations",
            json={"title": "Test Conversation", "user_id": "test_user"}
        )
        conv_id = create_resp.json()["id"]
        
        # Get the conversation
        response = client.get(f"/api/v1/conversations/{conv_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == conv_id
        assert data["title"] == "Test Conversation"
    
    def test_get_conversation_not_found(self):
        """Test getting non-existent conversation"""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/conversations/{fake_id}")
        assert response.status_code == 404
    
    def test_update_conversation(self):
        """Test updating a conversation"""
        # Create
        create_resp = client.post(
            "/api/v1/conversations",
            json={"title": "Original Title"}
        )
        conv_id = create_resp.json()["id"]
        
        # Update
        response = client.put(
            f"/api/v1/conversations/{conv_id}",
            json={"title": "Updated Title", "status": "closed"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["status"] == "closed"
    
    def test_update_conversation_not_found(self):
        """Test updating non-existent conversation"""
        fake_id = str(uuid.uuid4())
        response = client.put(
            f"/api/v1/conversations/{fake_id}",
            json={"title": "New Title"}
        )
        assert response.status_code == 404
    
    def test_delete_conversation(self):
        """Test deleting a conversation"""
        # Create
        create_resp = client.post(
            "/api/v1/conversations",
            json={"title": "To Delete"}
        )
        conv_id = create_resp.json()["id"]
        
        # Delete
        response = client.delete(f"/api/v1/conversations/{conv_id}")
        assert response.status_code == 200
        
        # Verify deletion
        get_resp = client.get(f"/api/v1/conversations/{conv_id}")
        assert get_resp.status_code == 404


class TestMessageEndpoints:
    """Tests for message endpoints"""
    
    @pytest.fixture
    def conversation_id(self):
        """Create a test conversation and return its ID"""
        response = client.post(
            "/api/v1/conversations",
            json={"title": "Test for Messages"}
        )
        return response.json()["id"]
    
    def test_get_messages_empty(self, conversation_id):
        """Test getting messages from empty conversation"""
        response = client.get(f"/api/v1/conversations/{conversation_id}/messages")
        assert response.status_code == 200
        assert response.json() == []
    
    def test_add_message(self, conversation_id):
        """Test adding a message"""
        response = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"role": "user", "content": "Test message", "model": "gpt-4"}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "user"
        assert data["content"]["text"] == "Test message"
        assert data["model"] == "gpt-4"
    
    def test_add_message_invalid_role(self, conversation_id):
        """Test adding message with invalid role"""
        response = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"role": "invalid_role", "content": "Test"}
        )
        assert response.status_code == 400
    
    def test_get_messages(self, conversation_id):
        """Test getting messages"""
        # Add a message first
        client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"role": "user", "content": "Hello"}
        )
        
        response = client.get(f"/api/v1/conversations/{conversation_id}/messages")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["content"]["text"] == "Hello"


class TestTopicEndpoints:
    """Tests for topic endpoints"""
    
    def test_list_topics(self):
        """Test listing topics"""
        response = client.get("/api/v1/topics")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_create_topic(self):
        """Test creating a topic"""
        response = client.post(
            "/api/v1/topics",
            json={"name": "Test Topic", "description": "Test description", "color": "#FF0000"}
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Topic"
        assert data["description"] == "Test description"
        assert data["color"] == "#FF0000"
        return data["id"]
    
    def test_get_topic(self):
        """Test getting a topic"""
        # Create
        create_resp = client.post(
            "/api/v1/topics",
            json={"name": "Get Test Topic"}
        )
        topic_id = create_resp.json()["id"]
        
        # Get
        response = client.get(f"/api/v1/topics/{topic_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Get Test Topic"
    
    def test_update_topic(self):
        """Test updating a topic"""
        # Create
        create_resp = client.post(
            "/api/v1/topics",
            json={"name": "Original Name"}
        )
        topic_id = create_resp.json()["id"]
        
        # Update
        response = client.put(
            f"/api/v1/topics/{topic_id}",
            json={"name": "Updated Name"}
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"
    
    def test_delete_topic(self):
        """Test deleting a topic"""
        # Create
        create_resp = client.post(
            "/api/v1/topics",
            json={"name": "To Delete"}
        )
        topic_id = create_resp.json()["id"]
        
        # Delete
        response = client.delete(f"/api/v1/topics/{topic_id}")
        assert response.status_code == 200
        
        # Verify
        get_resp = client.get(f"/api/v1/topics/{topic_id}")
        assert get_resp.status_code == 404


class TestSearchEndpoints:
    """Tests for search endpoints"""
    
    def test_search_requires_query(self):
        """Test that search requires query parameter"""
        response = client.get("/api/v1/search")
        assert response.status_code == 422  # Validation error
    
    def test_search_with_query(self):
        """Test search with query"""
        # Create a conversation with a unique title
        unique_title = f"Search Test {datetime.now().isoformat()}"
        client.post(
            "/api/v1/conversations",
            json={"title": unique_title}
        )
        
        # Search for it
        response = client.get(f"/api/v1/search?q={unique_title[:10]}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestStatsEndpoints:
    """Tests for statistics endpoints"""
    
    def test_get_stats(self):
        """Test getting statistics"""
        response = client.get("/api/v1/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_conversations" in data
        assert "total_messages" in data


class TestFilterAndSort:
    """Tests for filtering and sorting"""
    
    def test_list_with_status_filter(self):
        """Test filtering by status"""
        response = client.get("/api/v1/conversations?status=active")
        assert response.status_code == 200
        data = response.json()
        # All returned conversations should have active status
        for conv in data:
            assert conv["status"] == "active"
    
    def test_list_with_sort(self):
        """Test sorting conversations"""
        response = client.get("/api/v1/conversations?sort_by=created_at&ascending=true")
        assert response.status_code == 200
        data = response.json()
        # Verify it's a list
        assert isinstance(data, list)
    
    def test_list_with_pagination(self):
        """Test pagination"""
        response = client.get("/api/v1/conversations?limit=5&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 5


class TestHistoryEndpoint:
    """Tests for message history endpoint"""
    
    def test_get_message_history(self):
        """Test getting formatted message history"""
        # Create conversation
        create_resp = client.post(
            "/api/v1/conversations",
            json={"title": "History Test"}
        )
        conv_id = create_resp.json()["id"]
        
        # Add messages
        client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"role": "user", "content": "Hi"}
        )
        client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"role": "assistant", "content": "Hello!"}
        )
        
        # Get history
        response = client.get(f"/api/v1/conversations/{conv_id}/history")
        assert response.status_code == 200
        data = response.json()
        assert data["conversation_id"] == conv_id
        assert "messages" in data
        assert len(data["messages"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
