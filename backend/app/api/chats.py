"""
Chat API endpoints - Production Grade
GET /api/chats, POST /api/chats, GET /api/chats/:chatId/messages, POST /api/chats/:chatId/messages
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Path
from typing import Optional, List
from datetime import datetime
from bson import ObjectId
import logging

from app.models.schemas import (
    ChatCreate, ChatItemResponse, ChatListResponse,
    MessageCreate, MessageResponse, MessageListResponse,
    MemoryResponse
)
from app.auth.auth_middleware import get_current_user
from app.database import get_database

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("", response_model=ChatListResponse)
async def list_chats(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """List user's chats with pagination"""
    try:
        db = get_database()
        if db is None:
            raise HTTPException(status_code=500, detail="Database connection error")
        
        user_id = ObjectId(current_user["id"])
        skip = (page - 1) * per_page
        
        # Get chats sorted by last message time
        cursor = db.chats.find({"userId": user_id}).sort("lastMessageAt", -1).skip(skip).limit(per_page)
        chats = await cursor.to_list(length=per_page)
        
        # Get total count
        total = await db.chats.count_documents({"userId": user_id})
        
        chat_responses = []
        for chat in chats:
            chat_responses.append(ChatItemResponse(
                id=str(chat["_id"]),
                userId=str(chat["userId"]),
                title=chat.get("title", "Untitled Chat"),
                createdAt=chat.get("createdAt", chat.get("created_at")),
                lastMessageAt=chat.get("lastMessageAt", chat.get("last_message_at"))
            ))
        
        return ChatListResponse(
            chats=chat_responses,
            total=total,
            page=page,
            per_page=per_page,
            has_more=(skip + per_page) < total
        )
    except Exception as e:
        logger.error(f"Error listing chats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list chats")

@router.post("", response_model=ChatItemResponse, status_code=201)
async def create_chat(
    chat_data: Optional[ChatCreate] = None,
    current_user: dict = Depends(get_current_user)
):
    """Create a new chat"""
    try:
        db = get_database()
        if db is None:
            raise HTTPException(status_code=500, detail="Database connection error")
        
        user_id = ObjectId(current_user["id"])
        # Auto-generate title from first message if available, otherwise use "New Chat"
        title = chat_data.title if chat_data and chat_data.title else "New Chat"
        
        chat_doc = {
            "userId": user_id,
            "title": title,
            "createdAt": datetime.utcnow(),
            "lastMessageAt": None
        }
        
        result = await db.chats.insert_one(chat_doc)
        
        return ChatItemResponse(
            id=str(result.inserted_id),
            userId=str(user_id),
            title=title,
            createdAt=chat_doc["createdAt"],
            lastMessageAt=None
        )
    except Exception as e:
        logger.error(f"Error creating chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create chat")

@router.delete("/{chat_id}")
async def delete_chat(
    chat_id: str = Path(..., description="Chat ID"),
    current_user: dict = Depends(get_current_user)
):
    """Delete a chat and all its messages"""
    try:
        db = get_database()
        if db is None:
            raise HTTPException(status_code=500, detail="Database connection error")
        
        user_id = ObjectId(current_user["id"])
        chat_obj_id = ObjectId(chat_id)
        
        # Verify chat belongs to user
        chat = await db.chats.find_one({"_id": chat_obj_id, "userId": user_id})
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        # Delete all messages for this chat
        messages_deleted = await db.messages.delete_many({"chatId": chat_obj_id})
        logger.info(f"Deleted {messages_deleted.deleted_count} messages for chat {chat_id}")
        
        # Delete the chat
        await db.chats.delete_one({"_id": chat_obj_id, "userId": user_id})
        logger.info(f"Deleted chat {chat_id} for user {user_id}")
        
        return {"message": "Chat deleted successfully", "deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete chat")

@router.get("/{chat_id}/messages", response_model=MessageListResponse)
async def get_messages(
    chat_id: str = Path(..., description="Chat ID"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    cursor: Optional[str] = Query(None, description="Cursor for pagination"),
    current_user: dict = Depends(get_current_user)
):
    """Get messages for a chat with pagination (supports cursor-based pagination)"""
    try:
        db = get_database()
        if db is None:
            raise HTTPException(status_code=500, detail="Database connection error")
        
        user_id = ObjectId(current_user["id"])
        chat_obj_id = ObjectId(chat_id)
        
        # Verify chat belongs to user
        chat = await db.chats.find_one({"_id": chat_obj_id, "userId": user_id})
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        # Build query
        query = {"chatId": chat_obj_id}
        
        # Cursor-based pagination (for better performance with large datasets)
        if cursor:
            try:
                cursor_obj_id = ObjectId(cursor)
                query["_id"] = {"$lt": cursor_obj_id}  # Get messages before cursor
            except:
                pass  # Invalid cursor, fall back to page-based
        
        # Get messages (newest first for chat, but we'll reverse for display)
        skip = (page - 1) * per_page if not cursor else 0
        cursor_query = db.messages.find(query).sort("createdAt", -1)
        
        if cursor:
            cursor_query = cursor_query.limit(per_page + 1)  # +1 to check if more exists
        else:
            cursor_query = cursor_query.skip(skip).limit(per_page + 1)
        
        messages = await cursor_query.to_list(length=per_page + 1)
        has_more = len(messages) > per_page
        
        if has_more:
            messages = messages[:per_page]
        
        # Reverse for chronological order (oldest first)
        messages.reverse()
        
        # Get total count
        total = await db.messages.count_documents({"chatId": chat_obj_id})
        
        message_responses = []
        next_cursor = None
        for msg in messages:
            message_responses.append(MessageResponse(
                id=str(msg["_id"]),
                chatId=str(msg["chatId"]),
                userId=str(msg["userId"]),
                role=msg.get("role", "user"),
                content=msg.get("content", ""),
                attachments=msg.get("attachments", []),
                sources=msg.get("sources", []),
                metadata=msg.get("metadata", {}),
                createdAt=msg.get("createdAt", msg.get("created_at")),
                tokens=msg.get("tokens")
            ))
            next_cursor = str(msg["_id"])  # Last message ID as cursor
        
        return MessageListResponse(
            messages=message_responses,
            total=total,
            page=page,
            per_page=per_page,
            cursor=next_cursor if has_more else None,
            has_more=has_more
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get messages")

@router.post("/{chat_id}/messages", response_model=MessageResponse, status_code=201)
async def create_message(
    chat_id: str = Path(..., description="Chat ID"),
    message_data: MessageCreate = ...,
    current_user: dict = Depends(get_current_user)
):
    """Create a new message in a chat (triggers agent processing)"""
    try:
        db = get_database()
        if db is None:
            raise HTTPException(status_code=500, detail="Database connection error")
        
        user_id = ObjectId(current_user["id"])
        chat_obj_id = ObjectId(chat_id)
        
        # Verify chat belongs to user
        chat = await db.chats.find_one({"_id": chat_obj_id, "userId": user_id})
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        # Create message document
        message_doc = {
            "chatId": chat_obj_id,
            "userId": user_id,
            "role": message_data.role,
            "content": message_data.content,
            "attachments": message_data.attachments or [],
            "sources": [],
            "metadata": {},
            "createdAt": datetime.utcnow(),
            "tokens": None
        }
        
        result = await db.messages.insert_one(message_doc)
        
        # Update chat's last message time
        await db.chats.update_one(
            {"_id": chat_obj_id},
            {"$set": {"lastMessageAt": datetime.utcnow()}}
        )
        
        # TODO: Trigger agent processing in background
        # This should return jobId for async processing
        # For now, return the message immediately
        
        return MessageResponse(
            id=str(result.inserted_id),
            chatId=chat_id,
            userId=str(user_id),
            role=message_data.role,
            content=message_data.content,
            attachments=message_data.attachments or [],
            sources=[],
            metadata={},
            createdAt=message_doc["createdAt"],
            tokens=None
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create message")

@router.get("/{chat_id}/memory", response_model=MemoryResponse)
async def get_chat_memory(
    chat_id: str = Path(..., description="Chat ID"),
    current_user: dict = Depends(get_current_user)
):
    """Get memory summary for a chat"""
    try:
        db = get_database()
        if db is None:
            raise HTTPException(status_code=500, detail="Database connection error")
        
        user_id = ObjectId(current_user["id"])
        chat_obj_id = ObjectId(chat_id)
        
        # Verify chat belongs to user
        chat = await db.chats.find_one({"_id": chat_obj_id, "userId": user_id})
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")
        
        # Get recent messages for memory generation
        messages_cursor = db.messages.find(
            {"chatId": chat_obj_id}
        ).sort("createdAt", -1).limit(50)
        messages = await messages_cursor.to_list(length=50)
        
        if not messages:
            return MemoryResponse(
                summary="No messages in this chat yet.",
                keyInsights=[],
                updatedAt=datetime.utcnow()
            )
        
        # Generate memory summary using LLM
        try:
            from app.llm.gemini_engine import GeminiEngine
            llm_engine = GeminiEngine()
            
            # Prepare message history for LLM (limit to last 10 messages, shorter content)
            message_history = "\n".join([
                f"{msg.get('role', 'user').upper()}: {msg.get('content', '')[:100]}"
                for msg in reversed(messages[-10:])  # Last 10 messages, shorter
            ])
            
            # Shorter, more focused prompt
            prompt = f"""Summarize this chat in 2-3 sentences. List 3-5 key points.

Chat:
{message_history}

Return JSON: {{"summary": "...", "keyInsights": ["...", "..."]}}"""
            
            # generate is not async, call it directly (no await)
            try:
                response_text = llm_engine.generate(prompt, max_tokens=1000)
            except ValueError as e:
                # If prompt too long or other error, use fallback
                logger.warning(f"Memory generation failed: {e}, using fallback")
                response_text = None
            
            if response_text:
                # Try to parse JSON from response
                import json
                import re
                
                # Extract JSON from response (handle markdown code blocks)
                json_match = re.search(r'\{[^{}]*"summary"[^{}]*"keyInsights"[^{}]*\}', response_text, re.DOTALL)
                if json_match:
                    try:
                        response = json.loads(json_match.group())
                        return MemoryResponse(
                            summary=response.get("summary", "No summary available."),
                            keyInsights=response.get("keyInsights", []),
                            updatedAt=datetime.utcnow()
                        )
                    except json.JSONDecodeError:
                        pass
                
                # Fallback: extract summary from text
                summary = response_text[:300] if len(response_text) > 300 else response_text
                return MemoryResponse(
                    summary=summary,
                    keyInsights=[],
                    updatedAt=datetime.utcnow()
                )
        except Exception as e:
            logger.error(f"Error generating memory summary: {e}", exc_info=True)
        
        # Fallback: simple extraction
        user_messages = [m for m in messages if m.get("role") == "user"]
        assistant_messages = [m for m in messages if m.get("role") == "assistant"]
        
        summary = f"Chat with {len(user_messages)} user messages and {len(assistant_messages)} assistant responses."
        key_insights = []
        
        # Extract company names mentioned
        for msg in messages:
            content = msg.get("content", "").lower()
            if "research" in content or "company" in content:
                # Try to extract company name
                words = content.split()
                for i, word in enumerate(words):
                    if word in ["research", "analyze", "company"] and i + 1 < len(words):
                        potential_company = words[i + 1]
                        if len(potential_company) > 2 and potential_company not in key_insights:
                            key_insights.append(potential_company.capitalize())
                            if len(key_insights) >= 5:
                                break
        
        return MemoryResponse(
            summary=summary,
            keyInsights=key_insights[:5],
            updatedAt=datetime.utcnow()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chat memory: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get chat memory")

