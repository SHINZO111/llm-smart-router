"""
LLM Smart Router - Conversation Database Manager
SQLite database operations for conversation history
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from contextlib import contextmanager


class ConversationDB:
    """SQLite database manager for conversation history"""
    
    def __init__(self, db_path: str = "data/conversations.db"):
        """
        Initialize database connection
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_database(self):
        """Initialize database with schema"""
        schema_path = Path(__file__).parent / "schema.sql"
        if schema_path.exists():
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema = f.read()
            
            with self._get_connection() as conn:
                conn.executescript(schema)
    
    # ==================== Topic Operations ====================
    
    def create_topic(self, name: str) -> int:
        """Create a new topic"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO topics (name) VALUES (?)",
                (name,)
            )
            return cursor.lastrowid
    
    def get_topics(self) -> List[Dict[str, Any]]:
        """Get all topics"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT id, name, created_at FROM topics ORDER BY name"
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_topic_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get topic by name"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT id, name, created_at FROM topics WHERE name = ?",
                (name,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def delete_topic(self, topic_id: int) -> bool:
        """Delete a topic (conversations will have topic_id set to NULL)"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM topics WHERE id = ?",
                (topic_id,)
            )
            return cursor.rowcount > 0
    
    # ==================== Conversation Operations ====================
    
    def create_conversation(self, title: str = "New Conversation", 
                          topic_id: Optional[int] = None) -> int:
        """
        Create a new conversation
        
        Args:
            title: Conversation title
            topic_id: Optional topic ID
            
        Returns:
            Created conversation ID
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO conversations (title, topic_id) 
                   VALUES (?, ?)""",
                (title, topic_id)
            )
            return cursor.lastrowid
    
    def get_conversation(self, conversation_id: int) -> Optional[Dict[str, Any]]:
        """Get conversation by ID"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT c.id, c.title, c.created_at, c.updated_at, 
                          c.topic_id, t.name as topic_name
                   FROM conversations c
                   LEFT JOIN topics t ON c.topic_id = t.id
                   WHERE c.id = ?""",
                (conversation_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_conversations(self, topic_id: Optional[int] = None,
                         limit: int = 100,
                         offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get conversations with optional filtering
        
        Args:
            topic_id: Filter by topic
            limit: Maximum number of results
            offset: Pagination offset
        """
        with self._get_connection() as conn:
            if topic_id:
                cursor = conn.execute(
                    """SELECT c.id, c.title, c.created_at, c.updated_at,
                              c.topic_id, t.name as topic_name,
                              (SELECT COUNT(*) FROM messages m 
                               WHERE m.conversation_id = c.id) as message_count
                       FROM conversations c
                       LEFT JOIN topics t ON c.topic_id = t.id
                       WHERE c.topic_id = ?
                       ORDER BY c.updated_at DESC
                       LIMIT ? OFFSET ?""",
                    (topic_id, limit, offset)
                )
            else:
                cursor = conn.execute(
                    """SELECT c.id, c.title, c.created_at, c.updated_at,
                              c.topic_id, t.name as topic_name,
                              (SELECT COUNT(*) FROM messages m 
                               WHERE m.conversation_id = c.id) as message_count
                       FROM conversations c
                       LEFT JOIN topics t ON c.topic_id = t.id
                       ORDER BY c.updated_at DESC
                       LIMIT ? OFFSET ?""",
                    (limit, offset)
                )
            return [dict(row) for row in cursor.fetchall()]
    
    def update_conversation(self, conversation_id: int, 
                           title: Optional[str] = None,
                           topic_id: Optional[int] = None) -> bool:
        """Update conversation metadata"""
        updates = []
        params = []
        
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if topic_id is not None:
            updates.append("topic_id = ?")
            params.append(topic_id)
        
        if not updates:
            return False
        
        params.append(conversation_id)
        
        with self._get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE conversations SET {', '.join(updates)} WHERE id = ?",
                params
            )
            return cursor.rowcount > 0
    
    def delete_conversation(self, conversation_id: int) -> bool:
        """Delete a conversation and all its messages"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM conversations WHERE id = ?",
                (conversation_id,)
            )
            return cursor.rowcount > 0
    
    # ==================== Message Operations ====================
    
    def add_message(self, conversation_id: int, role: str, 
                   content: str, model: Optional[str] = None) -> int:
        """
        Add a message to a conversation
        
        Args:
            conversation_id: Parent conversation ID
            role: Message role ('user', 'assistant', or 'system')
            content: Message content
            model: Optional model name used for generation
            
        Returns:
            Created message ID
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO messages (conversation_id, role, content, model)
                   VALUES (?, ?, ?, ?)""",
                (conversation_id, role, content, model)
            )
            return cursor.lastrowid
    
    def get_messages(self, conversation_id: int,
                    limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all messages for a conversation"""
        with self._get_connection() as conn:
            if limit:
                cursor = conn.execute(
                    """SELECT id, conversation_id, role, content, model, timestamp
                       FROM messages
                       WHERE conversation_id = ?
                       ORDER BY timestamp ASC
                       LIMIT ?""",
                    (conversation_id, limit)
                )
            else:
                cursor = conn.execute(
                    """SELECT id, conversation_id, role, content, model, timestamp
                       FROM messages
                       WHERE conversation_id = ?
                       ORDER BY timestamp ASC""",
                    (conversation_id,)
                )
            return [dict(row) for row in cursor.fetchall()]
    
    def get_message(self, message_id: int) -> Optional[Dict[str, Any]]:
        """Get a single message by ID"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT id, conversation_id, role, content, model, timestamp
                   FROM messages WHERE id = ?""",
                (message_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def update_message(self, message_id: int, content: str) -> bool:
        """Update message content"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE messages SET content = ? WHERE id = ?",
                (content, message_id)
            )
            return cursor.rowcount > 0
    
    def delete_message(self, message_id: int) -> bool:
        """Delete a message"""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM messages WHERE id = ?",
                (message_id,)
            )
            return cursor.rowcount > 0
    
    # ==================== Search Operations ====================
    
    def search_conversations(self, query: str, 
                           date_from: Optional[datetime] = None,
                           date_to: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Search conversations by content
        
        Args:
            query: Search query string
            date_from: Optional start date filter
            date_to: Optional end date filter
            
        Returns:
            List of matching conversations with match count
        """
        sql = """
            SELECT DISTINCT 
                c.id, c.title, c.created_at, c.updated_at,
                c.topic_id, t.name as topic_name,
                COUNT(m.id) as match_count
            FROM conversations c
            LEFT JOIN topics t ON c.topic_id = t.id
            INNER JOIN messages m ON m.conversation_id = c.id
            WHERE m.content LIKE ?
        """
        params = [f"%{query}%"]
        
        if date_from:
            sql += " AND m.timestamp >= ?"
            params.append(date_from.strftime("%Y-%m-%d %H:%M:%S"))
        if date_to:
            sql += " AND m.timestamp <= ?"
            params.append(date_to.strftime("%Y-%m-%d %H:%M:%S"))
        
        sql += " GROUP BY c.id ORDER BY c.updated_at DESC"
        
        with self._get_connection() as conn:
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def search_messages(self, query: str,
                       conversation_id: Optional[int] = None,
                       role: Optional[str] = None,
                       date_from: Optional[datetime] = None,
                       date_to: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Search messages with filters
        
        Args:
            query: Search query string
            conversation_id: Filter by conversation
            role: Filter by role ('user', 'assistant', 'system')
            date_from: Optional start date filter
            date_to: Optional end date filter
        """
        sql = """
            SELECT m.id, m.conversation_id, m.role, m.content, 
                   m.model, m.timestamp, c.title as conversation_title
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE m.content LIKE ?
        """
        params = [f"%{query}%"]
        
        if conversation_id:
            sql += " AND m.conversation_id = ?"
            params.append(conversation_id)
        if role:
            sql += " AND m.role = ?"
            params.append(role)
        if date_from:
            sql += " AND m.timestamp >= ?"
            params.append(date_from.strftime("%Y-%m-%d %H:%M:%S"))
        if date_to:
            sql += " AND m.timestamp <= ?"
            params.append(date_to.strftime("%Y-%m-%d %H:%M:%S"))
        
        sql += " ORDER BY m.timestamp DESC"
        
        with self._get_connection() as conn:
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
    
    # ==================== Statistics ====================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        with self._get_connection() as conn:
            stats = {}
            
            # Total counts
            cursor = conn.execute("SELECT COUNT(*) FROM conversations")
            stats['total_conversations'] = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM messages")
            stats['total_messages'] = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM topics")
            stats['total_topics'] = cursor.fetchone()[0]
            
            # Messages by role
            cursor = conn.execute(
                """SELECT role, COUNT(*) as count 
                   FROM messages GROUP BY role"""
            )
            stats['messages_by_role'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Recent activity (last 7 days)
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            cursor = conn.execute(
                """SELECT COUNT(*) FROM messages WHERE timestamp >= ?""",
                (week_ago,)
            )
            stats['messages_last_7_days'] = cursor.fetchone()[0]
            
            # Top models
            cursor = conn.execute(
                """SELECT model, COUNT(*) as count 
                   FROM messages 
                   WHERE model IS NOT NULL 
                   GROUP BY model 
                   ORDER BY count DESC 
                   LIMIT 5"""
            )
            stats['top_models'] = [{"model": row[0], "count": row[1]} 
                                  for row in cursor.fetchall()]
            
            return stats
    
    # ==================== Utility ====================
    
    def get_conversation_with_messages(self, conversation_id: int) -> Optional[Dict[str, Any]]:
        """Get full conversation with all messages"""
        conversation = self.get_conversation(conversation_id)
        if conversation:
            conversation['messages'] = self.get_messages(conversation_id)
        return conversation


# Singleton instance
_db_instance: Optional[ConversationDB] = None


def get_db(db_path: str = "data/conversations.db") -> ConversationDB:
    """Get or create singleton database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = ConversationDB(db_path)
    return _db_instance
