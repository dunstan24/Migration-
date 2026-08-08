"""
routers/conversation.py
Conversation history and session management
GET/DELETE /api/conversation/sessions - manage conversation sessions
GET /api/conversation/history/{session_id} - retrieve message history
DELETE /api/conversation/delete/{session_id} - delete conversation
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc
from db.database import SessionLocal
from db.models import ConversationSession, ConversationMessage
import uuid
import json
from datetime import datetime
from typing import Optional, List

router = APIRouter()


class MessageSchema(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str
    created_at: str
    tokens_used: Optional[int] = None


class SessionSchema(BaseModel):
    session_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


class HistoryResponse(BaseModel):
    session_id: str
    title: str
    created_at: str
    messages: List[MessageSchema]


def generate_session_id():
    """Generate unique session ID"""
    return str(uuid.uuid4())[:12]


@router.post("/sessions/new")
async def create_session(title: Optional[str] = None):
    """
    Create a new conversation session
    
    Usage:
        POST /api/conversation/sessions/new
        {
            "title": "My Chat (optional)"
        }
    
    Response:
        {
            "session_id": "abc123def456",
            "title": "My Chat",
            "created_at": "2026-04-07T10:30:00"
        }
    """
    db = SessionLocal()
    try:
        session_id = generate_session_id()
        session_title = title or f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        new_session = ConversationSession(
            session_id=session_id,
            title=session_title,
            message_count=0
        )
        
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        
        return {
            "session_id": new_session.session_id,
            "title": new_session.title,
            "created_at": new_session.created_at.isoformat() if new_session.created_at else None
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/sessions")
async def get_all_sessions(limit: int = Query(50, ge=1, le=100)):
    """
    Get all conversation sessions for the user
    
    Usage:
        GET /api/conversation/sessions?limit=20
    
    Response:
        [
            {
                "session_id": "abc123def456",
                "title": "Chat about nurses",
                "created_at": "2026-04-07T10:30:00",
                "updated_at": "2026-04-07T11:45:00",
                "message_count": 5
            },
            ...
        ]
    """
    db = SessionLocal()
    try:
        sessions = db.query(ConversationSession)\
            .order_by(desc(ConversationSession.updated_at))\
            .limit(limit)\
            .all()
        
        return [
            {
                "session_id": s.session_id,
                "title": s.title,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
                "message_count": s.message_count
            }
            for s in sessions
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/history/{session_id}")
async def get_conversation_history(session_id: str):
    """
    Get all messages in a conversation session
    
    Usage:
        GET /api/conversation/history/abc123def456
    
    Response:
        {
            "session_id": "abc123def456",
            "title": "Chat about nurses",
            "created_at": "2026-04-07T10:30:00",
            "messages": [
                {
                    "role": "user",
                    "content": "Tell me about nurses",
                    "created_at": "2026-04-07T10:31:00",
                    "tokens_used": null
                },
                {
                    "role": "assistant",
                    "content": "Registered Nurses are in high demand...",
                    "created_at": "2026-04-07T10:31:05",
                    "tokens_used": 256
                },
                ...
            ]
        }
    """
    db = SessionLocal()
    try:
        session = db.query(ConversationSession)\
            .filter(ConversationSession.session_id == session_id)\
            .first()
        
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        messages = db.query(ConversationMessage)\
            .filter(ConversationMessage.session_id == session_id)\
            .order_by(ConversationMessage.created_at)\
            .all()
        
        return {
            "session_id": session.session_id,
            "title": session.title,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "message_count": len(messages),
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                    "tokens_used": m.tokens_used
                }
                for m in messages
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.delete("/delete/{session_id}")
async def delete_conversation(session_id: str):
    """
    Delete a conversation session and all its messages
    
    Usage:
        DELETE /api/conversation/delete/abc123def456
    
    Response:
        {
            "status": "success",
            "message": "Conversation deleted",
            "session_id": "abc123def456",
            "messages_deleted": 5
        }
    """
    db = SessionLocal()
    try:
        # Count messages to be deleted
        message_count = db.query(ConversationMessage)\
            .filter(ConversationMessage.session_id == session_id)\
            .count()
        
        # Delete all messages in session
        db.query(ConversationMessage)\
            .filter(ConversationMessage.session_id == session_id)\
            .delete()
        
        # Delete session
        result = db.query(ConversationSession)\
            .filter(ConversationSession.session_id == session_id)\
            .delete()
        
        if result == 0:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        db.commit()
        
        return {
            "status": "success",
            "message": "Conversation deleted",
            "session_id": session_id,
            "messages_deleted": message_count
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.delete("/delete-all")
async def delete_all_conversations():
    """
    Delete ALL conversation history (WARNING: permanent!)
    
    Usage:
        DELETE /api/conversation/delete-all
    
    Response:
        {
            "status": "success",
            "message": "All conversations deleted",
            "sessions_deleted": 23,
            "messages_deleted": 156
        }
    """
    db = SessionLocal()
    try:
        message_count = db.query(ConversationMessage).count()
        session_count = db.query(ConversationSession).count()
        
        db.query(ConversationMessage).delete()
        db.query(ConversationSession).delete()
        
        db.commit()
        
        return {
            "status": "success",
            "message": "All conversations deleted",
            "sessions_deleted": session_count,
            "messages_deleted": message_count
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


def save_message(session_id: str, role: str, content: str, tokens_used: Optional[int] = None, metadata: Optional[dict] = None):
    """
    Helper function to save a message to a session
    Internal use only - called from llm.py
    """
    db = SessionLocal()
    try:
        # Create message
        message = ConversationMessage(
            session_id=session_id,
            role=role,
            content=content,
            tokens_used=tokens_used,
            message_metadata=json.dumps(metadata) if metadata else None
        )
        
        db.add(message)
        
        # Update session's message count and updated_at
        session = db.query(ConversationSession)\
            .filter(ConversationSession.session_id == session_id)\
            .first()
        
        if session:
            session.message_count += 1
            db.add(session)
        
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error saving message: {e}")
    finally:
        db.close()
