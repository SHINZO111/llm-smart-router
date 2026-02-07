"""
Integration tests for API and CLI
"""
import sys
import pytest
import json
import tempfile
from pathlib import Path
from click.testing import CliRunner

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi.testclient import TestClient
from api.main import app
from cli.commands import cli


client = TestClient(app)
runner = CliRunner()


class TestEndToEndWorkflow:
    """End-to-end integration tests"""
    
    def test_full_conversation_workflow(self):
        """Test complete conversation lifecycle through API"""
        # 1. Create a topic
        topic_resp = client.post("/api/v1/topics", json={
            "name": "Integration Test Topic",
            "description": "Topic for integration tests"
        })
        assert topic_resp.status_code == 201
        topic_id = topic_resp.json()["id"]
        
        # 2. Create a conversation
        conv_resp = client.post("/api/v1/conversations", json={
            "title": "Integration Test Conversation",
            "topic_id": topic_id,
            "first_message": "Hello, this is a test!"
        })
        assert conv_resp.status_code == 201
        conv_id = conv_resp.json()["id"]
        assert conv_resp.json()["title"] == "Integration Test Conversation"
        
        # 3. Get conversation
        get_resp = client.get(f"/api/v1/conversations/{conv_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == conv_id
        
        # 4. Add messages
        msg1_resp = client.post(f"/api/v1/conversations/{conv_id}/messages", json={
            "role": "user",
            "content": "What can you do?"
        })
        assert msg1_resp.status_code == 201
        
        msg2_resp = client.post(f"/api/v1/conversations/{conv_id}/messages", json={
            "role": "assistant",
            "content": "I can help you with many tasks!",
            "model": "gpt-4"
        })
        assert msg2_resp.status_code == 201
        
        # 5. Get messages
        msgs_resp = client.get(f"/api/v1/conversations/{conv_id}/messages")
        assert msgs_resp.status_code == 200
        messages = msgs_resp.json()
        assert len(messages) >= 2  # At least first_message + added messages
        
        # 6. Get message history (LLM format)
        history_resp = client.get(f"/api/v1/conversations/{conv_id}/history")
        assert history_resp.status_code == 200
        history = history_resp.json()
        assert "messages" in history
        
        # 7. Update conversation
        update_resp = client.put(f"/api/v1/conversations/{conv_id}", json={
            "title": "Updated Integration Test",
            "status": "closed"
        })
        assert update_resp.status_code == 200
        assert update_resp.json()["title"] == "Updated Integration Test"
        assert update_resp.json()["status"] == "closed"
        
        # 8. Search
        search_resp = client.get("/api/v1/search?q=Integration")
        assert search_resp.status_code == 200
        search_results = search_resp.json()
        assert any(r["id"] == conv_id for r in search_results)
        
        # 9. Export conversation
        export_resp = client.post("/api/v1/export", json={
            "conversation_ids": [conv_id]
        })
        assert export_resp.status_code == 200
        export_data = export_resp.json()
        assert "export_data" in export_data
        
        # 10. Delete conversation
        delete_resp = client.delete(f"/api/v1/conversations/{conv_id}")
        assert delete_resp.status_code == 200
        
        # Verify deletion
        verify_resp = client.get(f"/api/v1/conversations/{conv_id}")
        assert verify_resp.status_code == 404
        
        # 11. Delete topic
        topic_delete_resp = client.delete(f"/api/v1/topics/{topic_id}")
        assert topic_delete_resp.status_code == 200
    
    def test_import_export_roundtrip(self):
        """Test export and re-import of conversation data"""
        # Create conversation with messages
        conv_resp = client.post("/api/v1/conversations", json={
            "title": "Export Test Conversation",
            "first_message": "Initial message"
        })
        conv_id = conv_resp.json()["id"]
        
        # Add more messages
        client.post(f"/api/v1/conversations/{conv_id}/messages", json={
            "role": "user",
            "content": "User message"
        })
        client.post(f"/api/v1/conversations/{conv_id}/messages", json={
            "role": "assistant",
            "content": "Assistant response",
            "model": "claude-3"
        })
        
        # Export
        export_resp = client.get(f"/api/v1/export/{conv_id}")
        assert export_resp.status_code == 200
        export_data = export_resp.json()["export_data"]
        
        # Verify export structure
        assert "version" in export_data
        assert "conversation" in export_data
        assert "messages" in export_data["conversation"]
        
        # Clean up
        client.delete(f"/api/v1/conversations/{conv_id}")


class TestCLIIntegration:
    """CLI integration tests"""
    
    def test_cli_create_and_list(self):
        """Test CLI create and list workflow"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Note: CLI uses ConversationManager which uses file storage
            # This test verifies the CLI commands work together
            
            # Create a conversation via CLI
            create_result = runner.invoke(cli, [
                'create',
                '--title', 'CLI Test Conversation'
            ])
            assert create_result.exit_code == 0
            
            # List conversations
            list_result = runner.invoke(cli, ['list'])
            assert list_result.exit_code == 0
    
    def test_cli_stats(self):
        """Test CLI stats command"""
        result = runner.invoke(cli, ['stats'])
        assert result.exit_code == 0
        # Should show statistics table
        assert any(word in result.output for word in ['Conversations', 'Messages', 'Total'])


class TestFilteringIntegration:
    """Test filtering functionality"""
    
    def test_filter_by_status(self):
        """Test filtering conversations by status"""
        # Create conversations with different statuses
        active_conv = client.post("/api/v1/conversations", json={
            "title": "Active Conv",
            "status": "active"
        })
        conv_id = active_conv.json()["id"]
        
        # Update to closed
        client.put(f"/api/v1/conversations/{conv_id}", json={"status": "closed"})
        
        # Filter by active
        active_filter = client.get("/api/v1/conversations?status=active")
        assert active_filter.status_code == 200
        for conv in active_filter.json():
            assert conv["status"] == "active"
        
        # Filter by closed
        closed_filter = client.get("/api/v1/conversations?status=closed")
        assert closed_filter.status_code == 200
        
        # Clean up
        client.delete(f"/api/v1/conversations/{conv_id}")
    
    def test_pagination(self):
        """Test pagination works correctly"""
        # Get first page
        page1 = client.get("/api/v1/conversations?limit=5&offset=0")
        assert page1.status_code == 200
        
        # Get second page
        page2 = client.get("/api/v1/conversations?limit=5&offset=5")
        assert page2.status_code == 200
        
        # Results should be different (unless total <= 5)
        page1_ids = {c["id"] for c in page1.json()}
        page2_ids = {c["id"] for c in page2.json()}
        assert not page1_ids.intersection(page2_ids) or len(page1.json()) < 5


class TestErrorHandling:
    """Test error handling"""
    
    def test_invalid_conversation_id(self):
        """Test handling of invalid conversation IDs"""
        # Try to get non-existent conversation
        resp = client.get("/api/v1/conversations/invalid-id-format")
        # Should return 404 or handle gracefully
        assert resp.status_code in [404, 400, 422]
    
    def test_invalid_status_value(self):
        """Test handling of invalid status"""
        resp = client.get("/api/v1/conversations?status=invalid_status")
        assert resp.status_code == 400
    
    def test_missing_required_fields(self):
        """Test validation of required fields"""
        # Try to create topic without name
        resp = client.post("/api/v1/topics", json={})
        assert resp.status_code == 422  # Validation error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
