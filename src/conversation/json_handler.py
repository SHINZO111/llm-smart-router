"""
LLM Smart Router - JSON Handler for Conversation Import/Export
Export and import conversation data in JSON format
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import logging

from conversation.db_manager import ConversationDB, get_db

logger = logging.getLogger(__name__)


class ConversationJSONHandler:
    """Handle JSON export and import of conversation data"""
    
    def __init__(self, db: Optional[ConversationDB] = None):
        """
        Initialize handler
        
        Args:
            db: ConversationDB instance (creates new if None)
        """
        self.db = db or get_db()
    
    def export_conversation(self, conversation_id: int, 
                           include_metadata: bool = True) -> Dict[str, Any]:
        """
        Export a single conversation to JSON format
        
        Args:
            conversation_id: ID of conversation to export
            include_metadata: Include additional metadata
            
        Returns:
            Dictionary representing the conversation
        """
        conversation = self.db.get_conversation_with_messages(conversation_id)
        
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")
        
        export_data = {
            "version": "1.0",
            "export_date": datetime.now().isoformat(),
            "conversation": {
                "id": conversation["id"],
                "title": conversation["title"],
                "created_at": conversation["created_at"],
                "updated_at": conversation["updated_at"],
                "topic": conversation.get("topic_name"),
                "messages": [
                    {
                        "role": msg["role"],
                        "content": msg["content"],
                        "model": msg.get("model"),
                        "timestamp": msg["timestamp"]
                    }
                    for msg in conversation.get("messages", [])
                ]
            }
        }
        
        if include_metadata:
            export_data["metadata"] = {
                "message_count": len(conversation.get("messages", [])),
                "user_messages": sum(1 for m in conversation.get("messages", []) 
                                    if m["role"] == "user"),
                "assistant_messages": sum(1 for m in conversation.get("messages", []) 
                                         if m["role"] == "assistant"),
                "models_used": list(set(
                    m.get("model") for m in conversation.get("messages", [])
                    if m.get("model")
                ))
            }
        
        return export_data
    
    def export_conversations(self, conversation_ids: Optional[List[int]] = None,
                            topic_id: Optional[int] = None,
                            date_from: Optional[datetime] = None,
                            date_to: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Export multiple conversations
        
        Args:
            conversation_ids: Specific conversation IDs to export
            topic_id: Filter by topic
            date_from: Filter by start date
            date_to: Filter by end date
            
        Returns:
            Dictionary with all exported conversations
        """
        export_data = {
            "version": "1.0",
            "export_date": datetime.now().isoformat(),
            "export_type": "multiple_conversations",
            "conversations": []
        }
        
        if conversation_ids:
            conversations = []
            for cid in conversation_ids:
                conv = self.db.get_conversation(cid)
                if conv:
                    conversations.append(conv)
        else:
            conversations = self.db.get_conversations(topic_id=topic_id, limit=10000)
            
            # Apply date filters if provided
            if date_from or date_to:
                filtered = []
                for conv in conversations:
                    conv_date = datetime.fromisoformat(conv["created_at"].replace('Z', '+00:00'))
                    if date_from and conv_date < date_from:
                        continue
                    if date_to and conv_date > date_to:
                        continue
                    filtered.append(conv)
                conversations = filtered
        
        for conv in conversations:
            conv_with_messages = self.db.get_conversation_with_messages(conv["id"])
            export_data["conversations"].append({
                "id": conv["id"],
                "title": conv["title"],
                "created_at": conv["created_at"],
                "updated_at": conv["updated_at"],
                "topic": conv.get("topic_name"),
                "messages": [
                    {
                        "role": msg["role"],
                        "content": msg["content"],
                        "model": msg.get("model"),
                        "timestamp": msg["timestamp"]
                    }
                    for msg in conv_with_messages.get("messages", [])
                ]
            })
        
        export_data["metadata"] = {
            "total_conversations": len(export_data["conversations"]),
            "total_messages": sum(
                len(c["messages"]) for c in export_data["conversations"]
            ),
            "filters_applied": {
                "topic_id": topic_id,
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None
            }
        }
        
        return export_data
    
    def export_to_file(self, filepath: Union[str, Path],
                      conversation_ids: Optional[List[int]] = None,
                      **kwargs) -> Path:
        """
        Export conversations to JSON file
        
        Args:
            filepath: Output file path
            conversation_ids: Specific conversation IDs (None = all)
            **kwargs: Additional filters for export_conversations
            
        Returns:
            Path to created file
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        if conversation_ids and len(conversation_ids) == 1:
            data = self.export_conversation(conversation_ids[0])
        else:
            data = self.export_conversations(conversation_ids=conversation_ids, **kwargs)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Exported conversations to {filepath}")
        return filepath
    
    def import_conversation(self, data: Dict[str, Any],
                           target_topic_id: Optional[int] = None) -> int:
        """
        Import a single conversation from JSON
        
        Args:
            data: Conversation data dictionary
            target_topic_id: Optional topic ID to assign
            
        Returns:
            Created conversation ID
        """
        # Handle both single conversation and wrapped formats
        if "conversation" in data:
            conv_data = data["conversation"]
        elif "conversations" in data:
            raise ValueError("Use import_conversations for multiple conversations")
        else:
            conv_data = data
        
        # Create conversation
        title = conv_data.get("title", "Imported Conversation")
        topic_id = target_topic_id
        
        # Try to find or create topic if specified in data
        if "topic" in conv_data and conv_data["topic"] and not target_topic_id:
            existing_topic = self.db.get_topic_by_name(conv_data["topic"])
            if existing_topic:
                topic_id = existing_topic["id"]
            else:
                topic_id = self.db.create_topic(conv_data["topic"])
        
        conversation_id = self.db.create_conversation(title, topic_id)
        
        # Add messages
        for msg in conv_data.get("messages", []):
            self.db.add_message(
                conversation_id=conversation_id,
                role=msg["role"],
                content=msg["content"],
                model=msg.get("model")
            )
        
        logger.info(f"Imported conversation {conversation_id} with "
                   f"{len(conv_data.get('messages', []))} messages")
        
        return conversation_id
    
    def import_conversations(self, data: Dict[str, Any],
                            target_topic_id: Optional[int] = None) -> List[int]:
        """
        Import multiple conversations from JSON
        
        Args:
            data: JSON data with conversations
            target_topic_id: Optional topic ID to assign to all
            
        Returns:
            List of created conversation IDs
        """
        if "conversations" in data:
            conversations = data["conversations"]
        elif "conversation" in data:
            return [self.import_conversation(data, target_topic_id)]
        else:
            raise ValueError("Invalid data format: missing 'conversations' or 'conversation'")
        
        imported_ids = []
        for conv_data in conversations:
            conv_id = self.import_conversation(
                {"conversation": conv_data}, 
                target_topic_id
            )
            imported_ids.append(conv_id)
        
        logger.info(f"Imported {len(imported_ids)} conversations")
        return imported_ids
    
    def import_from_file(self, filepath: Union[str, Path],
                        target_topic_id: Optional[int] = None) -> List[int]:
        """
        Import conversations from JSON file
        
        Args:
            filepath: Path to JSON file
            target_topic_id: Optional topic ID to assign
            
        Returns:
            List of created conversation IDs
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"Import file not found: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        result = self.import_conversations(data, target_topic_id)
        logger.info(f"Imported from file {filepath}: {len(result)} conversations")
        return result
    
    def export_by_search(self, query: str,
                        output_path: Union[str, Path],
                        date_from: Optional[datetime] = None,
                        date_to: Optional[datetime] = None) -> Path:
        """
        Export conversations matching a search query
        
        Args:
            query: Search query
            output_path: Output file path
            date_from: Optional start date filter
            date_to: Optional end date filter
            
        Returns:
            Path to created file
        """
        matching = self.db.search_conversations(query, date_from, date_to)
        conversation_ids = [m["id"] for m in matching]
        
        return self.export_to_file(
            output_path, 
            conversation_ids=conversation_ids
        )
    
    def create_backup(self, backup_dir: Union[str, Path] = "backups") -> Path:
        """
        Create a full database backup as JSON
        
        Args:
            backup_dir: Directory to save backup
            
        Returns:
            Path to backup file
        """
        backup_dir = Path(backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"conversations_backup_{timestamp}.json"
        filepath = backup_dir / filename
        
        return self.export_to_file(filepath)


# Convenience functions
def export_conversation(conversation_id: int, filepath: str, **kwargs) -> Path:
    """Export a single conversation to file"""
    handler = ConversationJSONHandler()
    data = handler.export_conversation(conversation_id, **kwargs)
    
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return path


def import_conversation(filepath: str, **kwargs) -> int:
    """Import a conversation from file"""
    handler = ConversationJSONHandler()
    return handler.import_from_file(filepath, **kwargs)[0]


def create_backup(backup_dir: str = "backups") -> Path:
    """Create full database backup"""
    handler = ConversationJSONHandler()
    return handler.create_backup(backup_dir)
