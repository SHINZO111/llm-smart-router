"""
FastAPI API Routes

REST API endpoints for conversation history management
"""
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel, Field

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from conversation.conversation_manager import ConversationManager
from conversation.json_handler import ConversationJSONHandler
from models.conversation import ConversationStatus, Topic
from models.message import MessageRole


router = APIRouter()

# Initialize managers
conversation_manager = ConversationManager()
json_handler = ConversationJSONHandler()


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
    role: str = Field(..., description="Message role: user, assistant, or system")
    content: str = Field(..., description="Message content")
    model: Optional[str] = None
    tokens: Optional[int] = None


class TopicCreate(BaseModel):
    """Request model for creating a topic"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    color: str = "#3B82F6"
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
    try:
        # Handle topic_id='null' to filter for conversations without topic
        topic_filter = topic_id
        if topic_id == 'null':
            topic_filter = None
        
        # Parse status
        status_filter = None
        if status:
            try:
                status_filter = ConversationStatus(status.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}", response_model=Dict[str, Any])
async def get_conversation(conversation_id: str):
    """Get a specific conversation by ID"""
    conversation = conversation_manager.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation.to_dict()


@router.post("/conversations", response_model=Dict[str, Any], status_code=201)
async def create_conversation(request: ConversationCreate):
    """Create a new conversation"""
    try:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/conversations/{conversation_id}", response_model=Dict[str, Any])
async def update_conversation(conversation_id: str, request: ConversationUpdate):
    """Update a conversation"""
    # Check if conversation exists
    existing = conversation_manager.get_conversation(conversation_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Parse status
    status_enum = None
    if request.status:
        try:
            status_enum = ConversationStatus(request.status.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {request.status}")
    
    try:
        updated = conversation_manager.update_conversation(
            conversation_id=conversation_id,
            title=request.title,
            status=status_enum,
            topic_id=request.topic_id
        )
        return updated.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation"""
    existing = conversation_manager.get_conversation(conversation_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    success = conversation_manager.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete conversation")
    
    return {"message": "Conversation deleted successfully", "id": conversation_id}


# ==================== Message Endpoints ====================

@router.get("/conversations/{conversation_id}/messages", response_model=List[Dict[str, Any]])
async def get_messages(
    conversation_id: str,
    limit: Optional[int] = Query(None, ge=1),
    offset: int = Query(0, ge=0)
):
    """Get messages for a conversation"""
    conversation = conversation_manager.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    messages = conversation_manager.get_messages(
        conversation_id=conversation_id,
        limit=limit,
        offset=offset
    )
    
    return [msg.to_dict() for msg in messages]


@router.post("/conversations/{conversation_id}/messages", response_model=Dict[str, Any], status_code=201)
async def add_message(conversation_id: str, request: MessageCreate):
    """Add a message to a conversation"""
    conversation = conversation_manager.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Validate role
    try:
        role = MessageRole(request.role.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {request.role}")
    
    try:
        message = conversation_manager.add_message(
            conversation_id=conversation_id,
            role=role,
            text=request.content,
            model=request.model,
            tokens=request.tokens
        )
        return message.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Topic Endpoints ====================

@router.get("/topics", response_model=List[Dict[str, Any]])
async def list_topics():
    """Get all topics"""
    topics = conversation_manager.get_all_topics()
    return [topic.to_dict() for topic in topics]


@router.post("/topics", response_model=Dict[str, Any], status_code=201)
async def create_topic(request: TopicCreate):
    """Create a new topic"""
    try:
        topic = conversation_manager.create_topic(
            name=request.name,
            description=request.description,
            color=request.color,
            parent_id=request.parent_id
        )
        return topic.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/topics/{topic_id}", response_model=Dict[str, Any])
async def get_topic(topic_id: str):
    """Get a specific topic"""
    topic = conversation_manager.get_topic(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic.to_dict()


@router.put("/topics/{topic_id}", response_model=Dict[str, Any])
async def update_topic(topic_id: str, request: TopicUpdate):
    """Update a topic"""
    existing = conversation_manager.get_topic(topic_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    try:
        updated = conversation_manager.update_topic(
            topic_id=topic_id,
            name=request.name,
            description=request.description,
            color=request.color
        )
        return updated.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/topics/{topic_id}")
async def delete_topic(topic_id: str):
    """Delete a topic"""
    existing = conversation_manager.get_topic(topic_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    success = conversation_manager.delete_topic(topic_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete topic")
    
    return {"message": "Topic deleted successfully", "id": topic_id}


# ==================== Search Endpoints ====================

@router.get("/search", response_model=List[Dict[str, Any]])
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
    try:
        conversations = conversation_manager.search_conversations(
            query=q,
            user_id=user_id,
            limit=limit
        )
        return [conv.to_dict() for conv in conversations]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search/messages", response_model=List[Dict[str, Any]])
async def search_messages(
    query: str = Form(..., min_length=1),
    conversation_id: Optional[str] = Form(None),
    role: Optional[str] = Form(None)
):
    """
    Search messages across all conversations
    
    - **query**: Search text
    - **conversation_id**: Optional conversation filter
    - **role**: Optional role filter (user, assistant, system)
    """
    # This would require database search implementation
    # For now, we'll return an empty list with a note
    raise HTTPException(
        status_code=501, 
        detail="Message search requires database implementation. Use GET /search for conversation search."
    )


# ==================== Export/Import Endpoints ====================

@router.post("/export")
async def export_conversations(request: ExportRequest):
    """
    Export conversations to JSON
    
    - **conversation_ids**: Specific conversation IDs to export (None = all)
    - **topic_id**: Filter by topic
    - **date_from**: Filter by start date
    - **date_to**: Filter by end date
    
    Returns JSON data for download
    """
    try:
        import tempfile
        from pathlib import Path
        
        # Create temp file for export
        temp_dir = Path(tempfile.gettempdir())
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_path = temp_dir / f"conversations_export_{timestamp}.json"
        
        # Convert string IDs to int for database layer if needed
        # Here we use the conversation_manager's file-based storage
        # So we need to handle the export differently
        
        if request.conversation_ids and len(request.conversation_ids) == 1:
            # Single conversation export
            data = json_handler.export_conversation(int(request.conversation_ids[0]))
        else:
            # Multiple or all conversations
            # Convert topic_id to int if provided
            topic_id_int = int(request.topic_id) if request.topic_id else None
            conv_ids_int = [int(cid) for cid in request.conversation_ids] if request.conversation_ids else None
            data = json_handler.export_conversations(
                conversation_ids=conv_ids_int,
                topic_id=topic_id_int,
                date_from=request.date_from,
                date_to=request.date_to
            )
        
        return {
            "export_data": data,
            "filename": export_path.name,
            "exported_at": datetime.now().isoformat()
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid ID format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import", response_model=ImportResponse)
async def import_conversations(
    file: UploadFile = File(..., description="JSON file to import"),
    target_topic_id: Optional[str] = Form(None)
):
    """
    Import conversations from JSON file
    
    - **file**: JSON file containing conversation data
    - **target_topic_id**: Optional topic ID to assign to imported conversations
    """
    try:
        import json
        import tempfile
        
        # Read uploaded file
        content = await file.read()
        data = json.loads(content.decode('utf-8'))
        
        # Convert topic_id to int if provided
        topic_id_int = int(target_topic_id) if target_topic_id else None
        
        # Import conversations
        imported_ids = json_handler.import_conversations(data, topic_id_int)
        
        return ImportResponse(
            imported_count=len(imported_ids),
            conversation_ids=[str(cid) for cid in imported_ids]
        )
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid data: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/{conversation_id}")
async def export_single_conversation(conversation_id: str):
    """Export a single conversation"""
    try:
        conv_id_int = int(conversation_id)
        data = json_handler.export_conversation(conv_id_int)
        return {
            "export_data": data,
            "exported_at": datetime.now().isoformat()
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid conversation ID")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Statistics Endpoints ====================

@router.get("/stats")
async def get_stats(user_id: Optional[str] = Query(None)):
    """Get conversation statistics"""
    try:
        stats = conversation_manager.get_stats(user_id=user_id)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}/history")
async def get_message_history(
    conversation_id: str,
    max_messages: int = Query(20, ge=1, le=100)
):
    """Get message history formatted for LLM context"""
    conversation = conversation_manager.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    history = conversation_manager.get_message_history(
        conversation_id=conversation_id,
        max_messages=max_messages
    )
    
    return {
        "conversation_id": conversation_id,
        "message_count": len(history),
        "messages": history
    }
