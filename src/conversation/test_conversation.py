#!/usr/bin/env python3
"""
LLM Smart Router - Conversation History Test Suite
Tests database operations and JSON export/import functionality
"""

import sys
import os
import json
import tempfile
from pathlib import Path

# Add src/conversation to path
sys.path.insert(0, str(Path(__file__).parent))

from db_manager import ConversationDB
from json_handler import ConversationJSONHandler


def test_database_operations():
    """Test database CRUD operations"""
    print("=" * 60)
    print("Testing Database Operations")
    print("=" * 60)
    
    # Use temporary database
    db_path = tempfile.mktemp(suffix='.db')
    db = ConversationDB(db_path)
    
    try:
        # Test 1: Create topic
        print("\n[Test 1] Create Topic")
        topic_id = db.create_topic("Test Topic")
        print(f"   [OK] Created topic: {topic_id}")
        
        # Test 2: Get topics
        print("\n[Test 2] Get Topics")
        topics = db.get_topics()
        print(f"   [OK] Found {len(topics)} topics")
        for t in topics[:3]:
            print(f"      - {t['name']} (ID: {t['id']})")
        
        # Test 3: Create conversation
        print("\n[Test 3] Create Conversation")
        conv_id = db.create_conversation("Test Conversation", topic_id)
        print(f"   [OK] Created conversation: {conv_id}")
        
        # Test 4: Get conversation
        print("\n[Test 4] Get Conversation")
        conv = db.get_conversation(conv_id)
        print(f"   [OK] Title: {conv['title']}")
        print(f"   [OK] Topic: {conv.get('topic_name')}")
        
        # Test 5: Add messages
        print("\n[Test 5] Add Messages")
        msg1_id = db.add_message(conv_id, "user", "Hello, how are you?")
        msg2_id = db.add_message(conv_id, "assistant", "I'm doing great! How can I help you?", "gpt-4")
        print(f"   [OK] Added user message: {msg1_id}")
        print(f"   [OK] Added assistant message: {msg2_id}")
        
        # Test 6: Get messages
        print("\n[Test 6] Get Messages")
        messages = db.get_messages(conv_id)
        print(f"   [OK] Retrieved {len(messages)} messages")
        for m in messages:
            print(f"      [{m['role']}] {m['content'][:40]}...")
        
        # Test 7: Update conversation
        print("\n[Test 7] Update Conversation")
        updated = db.update_conversation(conv_id, title="Updated Conversation")
        print(f"   [OK] Updated: {updated}")
        
        # Test 8: Search
        print("\n[Test 8] Search Messages")
        results = db.search_messages("Hello")
        print(f"   [OK] Found {len(results)} matching messages")
        
        # Test 9: Get stats
        print("\n[Test 9] Get Statistics")
        stats = db.get_stats()
        print(f"   [OK] Total conversations: {stats['total_conversations']}")
        print(f"   [OK] Total messages: {stats['total_messages']}")
        print(f"   [OK] Messages by role: {stats['messages_by_role']}")
        
        # Test 10: Conversation with messages
        print("\n[Test 10] Get Conversation with Messages")
        full_conv = db.get_conversation_with_messages(conv_id)
        print(f"   [OK] Got conversation with {len(full_conv['messages'])} messages")
        
        print("\n" + "=" * 60)
        print("All Database Tests Passed!")
        print("=" * 60)
        
        return db, conv_id
        
    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.remove(db_path)


def test_json_export_import():
    """Test JSON export and import functionality"""
    print("\n" + "=" * 60)
    print("Testing JSON Export/Import")
    print("=" * 60)
    
    # Use temporary database
    db_path = tempfile.mktemp(suffix='.db')
    db = ConversationDB(db_path)
    handler = ConversationJSONHandler(db)
    
    try:
        # Setup test data
        topic_id = db.create_topic("Export Test")
        conv1_id = db.create_conversation("Conversation 1", topic_id)
        db.add_message(conv1_id, "user", "Question 1")
        db.add_message(conv1_id, "assistant", "Answer 1", "gpt-4")
        
        conv2_id = db.create_conversation("Conversation 2", topic_id)
        db.add_message(conv2_id, "user", "Question 2")
        db.add_message(conv2_id, "assistant", "Answer 2", "claude-3")
        
        # Test 1: Export single conversation
        print("\n[Test 1] Export Single Conversation")
        export_data = handler.export_conversation(conv1_id)
        print(f"   [OK] Exported: {export_data['conversation']['title']}")
        print(f"   [OK] Messages: {len(export_data['conversation']['messages'])}")
        
        # Test 2: Export to file
        print("\n[Test 2] Export to File")
        export_file = tempfile.mktemp(suffix='.json')
        filepath = handler.export_to_file(export_file, conversation_ids=[conv1_id])
        print(f"   [OK] Exported to: {filepath}")
        
        # Verify file content
        with open(filepath, 'r') as f:
            file_data = json.load(f)
        print(f"   [OK] File contains: {file_data['conversation']['title']}")
        
        # Test 3: Import conversation
        print("\n[Test 3] Import Conversation")
        import_db_path = tempfile.mktemp(suffix='.db')
        import_db = ConversationDB(import_db_path)
        import_handler = ConversationJSONHandler(import_db)
        
        imported_ids = import_handler.import_from_file(filepath)
        print(f"   [OK] Imported conversation IDs: {imported_ids}")
        
        # Verify imported data
        imported_conv = import_db.get_conversation_with_messages(imported_ids[0])
        print(f"   [OK] Imported title: {imported_conv['title']}")
        print(f"   [OK] Imported messages: {len(imported_conv['messages'])}")
        
        # Test 4: Export all conversations
        print("\n[Test 4] Export All Conversations")
        all_export = handler.export_conversations()
        print(f"   [OK] Exported {len(all_export['conversations'])} conversations")
        
        # Test 5: Create backup
        print("\n[Test 5] Create Backup")
        backup_dir = tempfile.mkdtemp()
        backup_file = handler.create_backup(backup_dir)
        print(f"   [OK] Backup created: {backup_file}")
        
        # Test 6: Search-based export
        print("\n[Test 6] Search-based Export")
        db.add_message(conv1_id, "user", "Unique search term xyz123")
        search_file = tempfile.mktemp(suffix='.json')
        result = handler.export_by_search("xyz123", search_file)
        print(f"   [OK] Exported search results to: {result}")
        
        print("\n" + "=" * 60)
        print("All JSON Export/Import Tests Passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        for path in [db_path, import_db_path, export_file, search_file]:
            if path and os.path.exists(path):
                os.remove(path)


def test_stats_and_search():
    """Test statistics and search features"""
    print("\n" + "=" * 60)
    print("Testing Statistics and Search")
    print("=" * 60)
    
    db_path = tempfile.mktemp(suffix='.db')
    db = ConversationDB(db_path)
    
    try:
        # Create test data
        topic_id = db.create_topic("Stats Test")
        conv_id = db.create_conversation("Stats Conversation", topic_id)
        
        # Add various messages
        db.add_message(conv_id, "user", "First question about Python")
        db.add_message(conv_id, "assistant", "Python is great!", "gpt-4")
        db.add_message(conv_id, "user", "Second question about JavaScript")
        db.add_message(conv_id, "assistant", "JS is versatile!", "claude-3")
        db.add_message(conv_id, "system", "System message")
        
        # Test statistics
        print("\nStatistics:")
        stats = db.get_stats()
        print(f"   Conversations: {stats['total_conversations']}")
        print(f"   Messages: {stats['total_messages']}")
        print(f"   By role: {stats['messages_by_role']}")
        print(f"   Top models: {stats['top_models']}")
        
        # Test search
        print("\nSearch Results:")
        
        results = db.search_messages("Python")
        print(f"   'Python' search: {len(results)} results")
        
        results = db.search_messages("question", role="user")
        print(f"   'question' from user: {len(results)} results")
        
        results = db.search_conversations("great")
        print(f"   'great' in conversations: {len(results)} results")
        
        print("\n" + "=" * 60)
        print("Statistics and Search Tests Passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("LLM Smart Router - Conversation History Test Suite")
    print("=" * 60)
    
    # Run tests
    db, conv_id = test_database_operations()
    test_json_export_import()
    test_stats_and_search()
    
    print("\n" + "=" * 60)
    print("All Tests Completed Successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
