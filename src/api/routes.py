"""
FastAPI API Routes

REST API endpoints for conversation history management
"""
import json
import sys
from functools import wraps
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from conversation.conversation_manager import ConversationManager
from models.conversation import ConversationStatus, Topic
from models.message import MessageRole


router = APIRouter()

# Initialize manager
conversation_manager = ConversationManager()

# ==================== Constants ====================

VALID_SORT_FIELDS = {"created_at", "updated_at", "title", "message_count"}


# ==================== Helpers ====================

def _handle_errors(func):
    """共通エラーハンドリングデコレータ"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Internal error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")
    return wrapper


def _get_conversation_or_404(conversation_id: str):
    """会話を取得、存在しなければ404"""
    conv = conversation_manager.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


def _get_topic_or_404(topic_id: str):
    """トピックを取得、存在しなければ404"""
    topic = conversation_manager.get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic


def _parse_enum(enum_cls, value: str, field_name: str):
    """Enumバリデーション共通化"""
    try:
        return enum_cls(value.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}: {value}")


def _serialize_conversation_export(conv, messages):
    """会話エクスポート用のdict変換"""
    return {
        "id": conv.id,
        "title": conv.title,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        "messages": [
            {
                "role": msg.role.value,
                "content": msg.content.text,
                "model": getattr(msg, 'model', None),
                "timestamp": msg.created_at.isoformat() if msg.created_at else None,
            }
            for msg in messages
        ]
    }


# ==================== Pydantic Models ====================

class ConversationCreate(BaseModel):
    """Request model for creating a conversation"""
    user_id: str = ""
    first_message: Optional[str] = None
    topic_id: Optional[str] = None
    title: Optional[str] = None


class ConversationUpdate(BaseModel):
    """Request model for updating a conversation"""
    title: Optional[str] = None
    status: Optional[str] = None
    topic_id: Optional[str] = None


class MessageCreate(BaseModel):
    """Request model for adding a message"""
    role: str = Field(..., max_length=20, description="Message role: user, assistant, or system")
    content: str = Field(..., max_length=100000, description="Message content")
    model: Optional[str] = Field(None, max_length=100)
    tokens: Optional[int] = Field(None, ge=0)


class TopicCreate(BaseModel):
    """Request model for creating a topic"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    color: str = Field("#3B82F6", pattern=r'^#[0-9a-fA-F]{6}$')
    parent_id: Optional[str] = None


class TopicUpdate(BaseModel):
    """Request model for updating a topic"""
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None


class SearchQuery(BaseModel):
    """Request model for search"""
    query: str = Field(..., min_length=1)


class ExportRequest(BaseModel):
    """Request model for export"""
    conversation_ids: Optional[List[str]] = None
    topic_id: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class ImportResponse(BaseModel):
    """Response model for import"""
    imported_count: int
    conversation_ids: List[str]


# ==================== Conversation Endpoints ====================

@router.get("/conversations", response_model=List[Dict[str, Any]])
@_handle_errors
async def list_conversations(
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    topic_id: Optional[str] = Query(None, description="Filter by topic ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in title"),
    sort_by: str = Query("updated_at", description="Sort field"),
    ascending: bool = Query(False, description="Sort ascending"),
    limit: Optional[int] = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Get list of conversations with filtering and pagination

    - **user_id**: Filter by user ID
    - **topic_id**: Filter by topic ID (use 'null' for no topic)
    - **status**: Filter by status (active, paused, closed, archived)
    - **search**: Search in title and summary
    - **sort_by**: Sort field (created_at, updated_at, title, message_count)
    - **ascending**: Sort in ascending order
    - **limit**: Maximum number of results
    - **offset**: Pagination offset
    """
    # Validate sort_by
    if sort_by not in VALID_SORT_FIELDS:
        raise HTTPException(status_code=400, detail=f"Invalid sort_by: {sort_by}")

    # Handle topic_id='null' to filter for conversations without topic
    topic_filter = topic_id
    if topic_id == 'null':
        topic_filter = None

    # Parse status
    status_filter = _parse_enum(ConversationStatus, status, "status") if status else None

    conversations = conversation_manager.list_conversations(
        user_id=user_id,
        topic_id=topic_filter,
        status=status_filter,
        search_query=search,
        sort_by=sort_by,
        ascending=ascending,
        limit=limit,
        offset=offset
    )

    return [conv.to_dict() for conv in conversations]


@router.get("/conversations/{conversation_id}", response_model=Dict[str, Any])
async def get_conversation(conversation_id: str):
    """Get a specific conversation by ID"""
    return _get_conversation_or_404(conversation_id).to_dict()


@router.post("/conversations", response_model=Dict[str, Any], status_code=201)
@_handle_errors
async def create_conversation(request: ConversationCreate):
    """Create a new conversation"""
    conversation = conversation_manager.create_conversation(
        user_id=request.user_id,
        first_message=request.first_message,
        topic_id=request.topic_id
    )

    # Override title if provided
    if request.title:
        conversation = conversation_manager.update_conversation(
            conversation_id=conversation.id,
            title=request.title
        )

    return conversation.to_dict()


@router.put("/conversations/{conversation_id}", response_model=Dict[str, Any])
@_handle_errors
async def update_conversation(conversation_id: str, request: ConversationUpdate):
    """Update a conversation"""
    _get_conversation_or_404(conversation_id)

    # Parse status
    status_enum = _parse_enum(ConversationStatus, request.status, "status") if request.status else None

    updated = conversation_manager.update_conversation(
        conversation_id=conversation_id,
        title=request.title,
        status=status_enum,
        topic_id=request.topic_id
    )
    return updated.to_dict()


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation"""
    _get_conversation_or_404(conversation_id)

    success = conversation_manager.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete conversation")

    return {"message": "Conversation deleted successfully", "id": conversation_id}


# ==================== Message Endpoints ====================

@router.get("/conversations/{conversation_id}/messages", response_model=List[Dict[str, Any]])
async def get_messages(
    conversation_id: str,
    limit: Optional[int] = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get messages for a conversation"""
    _get_conversation_or_404(conversation_id)

    messages = conversation_manager.get_messages(
        conversation_id=conversation_id,
        limit=limit,
        offset=offset
    )

    return [msg.to_dict() for msg in messages]


@router.post("/conversations/{conversation_id}/messages", response_model=Dict[str, Any], status_code=201)
@_handle_errors
async def add_message(conversation_id: str, request: MessageCreate):
    """Add a message to a conversation"""
    _get_conversation_or_404(conversation_id)

    role = _parse_enum(MessageRole, request.role, "role")

    message = conversation_manager.add_message(
        conversation_id=conversation_id,
        role=role,
        text=request.content,
        model=request.model,
        tokens=request.tokens
    )
    return message.to_dict()


# ==================== Topic Endpoints ====================

@router.get("/topics", response_model=List[Dict[str, Any]])
async def list_topics():
    """Get all topics"""
    topics = conversation_manager.get_all_topics()
    return [topic.to_dict() for topic in topics]


@router.post("/topics", response_model=Dict[str, Any], status_code=201)
@_handle_errors
async def create_topic(request: TopicCreate):
    """Create a new topic"""
    topic = conversation_manager.create_topic(
        name=request.name,
        description=request.description,
        color=request.color,
        parent_id=request.parent_id
    )
    return topic.to_dict()


@router.get("/topics/{topic_id}", response_model=Dict[str, Any])
async def get_topic(topic_id: str):
    """Get a specific topic"""
    return _get_topic_or_404(topic_id).to_dict()


@router.put("/topics/{topic_id}", response_model=Dict[str, Any])
@_handle_errors
async def update_topic(topic_id: str, request: TopicUpdate):
    """Update a topic"""
    _get_topic_or_404(topic_id)

    updated = conversation_manager.update_topic(
        topic_id=topic_id,
        name=request.name,
        description=request.description,
        color=request.color
    )
    return updated.to_dict()


@router.delete("/topics/{topic_id}")
async def delete_topic(topic_id: str):
    """Delete a topic"""
    _get_topic_or_404(topic_id)

    success = conversation_manager.delete_topic(topic_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete topic")

    return {"message": "Topic deleted successfully", "id": topic_id}


# ==================== Search Endpoints ====================

@router.get("/search", response_model=List[Dict[str, Any]])
@_handle_errors
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Search conversations by title and summary

    - **q**: Search query string
    - **user_id**: Optional user ID filter
    - **limit**: Maximum number of results
    """
    conversations = conversation_manager.search_conversations(
        query=q,
        user_id=user_id,
        limit=limit
    )
    return [conv.to_dict() for conv in conversations]


@router.post("/search/messages", response_model=List[Dict[str, Any]])
@_handle_errors
async def search_messages(
    query: str = Form(..., min_length=1),
    conversation_id: Optional[str] = Form(None),
    role: Optional[str] = Form(None),
    limit: int = Form(100, ge=1, le=500)
):
    """
    Search messages across all conversations

    - **query**: Search text
    - **conversation_id**: Optional conversation filter
    - **role**: Optional role filter (user, assistant, system)
    - **limit**: Maximum number of results (default 100)
    """
    # Validate role if provided
    if role:
        valid_roles = ["user", "assistant", "system"]
        if role.lower() not in valid_roles:
            raise HTTPException(status_code=400, detail=f"Invalid role: {role}")
        role = role.lower()

    # Search through ConversationManager's in-memory messages
    results = []
    query_lower = query.lower()

    if conversation_id:
        # Search within a specific conversation
        _get_conversation_or_404(conversation_id)
        conv_ids = [conversation_id]
    else:
        # Search across all conversations
        all_convs = conversation_manager.list_conversations(limit=1000)
        conv_ids = [c.id for c in all_convs]

    for cid in conv_ids:
        messages = conversation_manager.get_messages(cid)
        for msg in messages:
            if role and msg.role.value != role:
                continue
            if query_lower in msg.content.text.lower():
                results.append({
                    "conversation_id": cid,
                    "role": msg.role.value,
                    "content": msg.content.text,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                })
                if len(results) >= limit:
                    break
        if len(results) >= limit:
            break

    return results


# ==================== Export/Import Endpoints ====================

@router.post("/export")
@_handle_errors
async def export_conversations(request: ExportRequest):
    """
    Export conversations to JSON

    - **conversation_ids**: Specific conversation IDs to export (None = all)
    - **topic_id**: Filter by topic
    - **date_from**: Filter by start date
    - **date_to**: Filter by end date

    Returns JSON data for download
    """
    # Export using ConversationManager (string UUID IDs)
    conversations_to_export = []

    if request.conversation_ids:
        for cid in request.conversation_ids:
            conv = conversation_manager.get_conversation(cid)
            if conv:
                conversations_to_export.append(conv)
    else:
        conversations_to_export = conversation_manager.list_conversations(
            topic_id=request.topic_id,
            limit=1000
        )

    # Apply date filters
    if request.date_from or request.date_to:
        filtered = []
        for conv in conversations_to_export:
            if request.date_from and conv.created_at < request.date_from:
                continue
            if request.date_to and conv.created_at > request.date_to:
                continue
            filtered.append(conv)
        conversations_to_export = filtered

    # Build export data
    export_data = []
    for conv in conversations_to_export:
        messages = conversation_manager.get_messages(conv.id)
        export_data.append(_serialize_conversation_export(conv, messages))

    data = {
        "version": "1.0",
        "export_date": datetime.now().isoformat(),
        "conversations": export_data,
        "metadata": {
            "total_conversations": len(export_data),
            "total_messages": sum(len(c["messages"]) for c in export_data),
        }
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return {
        "export_data": data,
        "filename": f"conversations_export_{timestamp}.json",
        "exported_at": datetime.now().isoformat()
    }


@router.post("/import", response_model=ImportResponse)
@_handle_errors
async def import_conversations(
    file: UploadFile = File(..., description="JSON file to import"),
    target_topic_id: Optional[str] = Form(None)
):
    """
    Import conversations from JSON file

    - **file**: JSON file containing conversation data
    - **target_topic_id**: Optional topic ID to assign to imported conversations
    """
    # Read uploaded file with size limit (10MB max)
    MAX_UPLOAD_SIZE = 10 * 1024 * 1024
    content = await file.read(MAX_UPLOAD_SIZE + 1)
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")

    try:
        data = json.loads(content.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON file")

    # Import conversations using ConversationManager
    imported_ids = []

    # Handle both single and multiple conversation formats
    if "conversation" in data:
        conv_list = [data["conversation"]]
    elif "conversations" in data:
        conv_list = data["conversations"]
    else:
        raise HTTPException(status_code=400, detail="Invalid format: missing 'conversations' or 'conversation'")

    for conv_data in conv_list:
        title = conv_data.get("title", "Imported Conversation")
        first_msg = None
        messages_data = conv_data.get("messages", [])
        if messages_data:
            first_msg = messages_data[0].get("content")

        conv = conversation_manager.create_conversation(
            first_message=first_msg,
            topic_id=target_topic_id
        )
        if title:
            conversation_manager.update_conversation(conv.id, title=title)

        # Add remaining messages (skip first if used as first_message)
        for msg in messages_data[1:] if first_msg else messages_data:
            try:
                role = MessageRole(msg.get("role", "user"))
            except ValueError:
                role = MessageRole.USER
            conversation_manager.add_message(
                conversation_id=conv.id,
                role=role,
                text=msg.get("content", "")
            )
        imported_ids.append(conv.id)

    return ImportResponse(
        imported_count=len(imported_ids),
        conversation_ids=imported_ids
    )


@router.get("/export/{conversation_id}")
@_handle_errors
async def export_single_conversation(conversation_id: str):
    """Export a single conversation"""
    conv = _get_conversation_or_404(conversation_id)
    messages = conversation_manager.get_messages(conversation_id)

    data = {
        "version": "1.0",
        "export_date": datetime.now().isoformat(),
        "conversation": _serialize_conversation_export(conv, messages)
    }
    return {
        "export_data": data,
        "exported_at": datetime.now().isoformat()
    }


# ==================== Statistics Endpoints ====================

@router.get("/stats")
@_handle_errors
async def get_stats(user_id: Optional[str] = Query(None)):
    """Get conversation statistics"""
    stats = conversation_manager.get_stats(user_id=user_id)
    return stats


@router.get("/conversations/{conversation_id}/history")
async def get_message_history(
    conversation_id: str,
    max_messages: int = Query(20, ge=1, le=100)
):
    """Get message history formatted for LLM context"""
    _get_conversation_or_404(conversation_id)

    history = conversation_manager.get_message_history(
        conversation_id=conversation_id,
        max_messages=max_messages
    )

    return {
        "conversation_id": conversation_id,
        "message_count": len(history),
        "messages": history
    }
