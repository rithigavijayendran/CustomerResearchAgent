"""
WebSocket streaming endpoint for chat token streaming
/ws/chats/:chatId/stream
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Path
from typing import Optional
import json
import logging
import asyncio
from datetime import datetime
from bson import ObjectId

try:
    from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError
except ImportError:
    # Fallback if websockets package structure is different
    ConnectionClosedOK = Exception
    ConnectionClosedError = Exception

from app.auth.auth_utils import verify_token
from app.database import get_database
from app.agent.agent_controller import AgentController
from app.agent.memory import SessionMemory
from app.rag.vector_store import VectorStore
from fastapi import Request

logger = logging.getLogger(__name__)

router = APIRouter()

async def get_user_from_token(token: str) -> Optional[dict]:
    """Verify WebSocket token and return user"""
    try:
        payload = verify_token(token)
        if payload:
            return {"id": payload.get("sub"), "email": payload.get("email")}
    except:
        pass
    return None

@router.websocket("/chats/{chat_id}/stream")
async def chat_stream(
    websocket: WebSocket,
    chat_id: str = Path(..., description="Chat ID"),
    token: Optional[str] = None
):
    """WebSocket endpoint for streaming chat responses with full agent integration"""
    """WebSocket endpoint for streaming chat responses"""
    await websocket.accept()
    
    try:
        # Get token from query string or headers
        if not token:
            # Try to get from query params
            query_params = dict(websocket.query_params)
            token = query_params.get("token")
        
        if not token:
            await websocket.send_json({"error": "Authentication required"})
            await websocket.close()
            return
        
        # Verify user
        user = await get_user_from_token(token)
        if not user:
            await websocket.send_json({"error": "Invalid token"})
            await websocket.close()
            return
        
        user_id = ObjectId(user["id"])
        chat_obj_id = ObjectId(chat_id)
        
        # Verify chat belongs to user
        db = get_database()
        if db is None:
            await websocket.send_json({"error": "Database error"})
            await websocket.close()
            return
        
        chat = await db.chats.find_one({"_id": chat_obj_id, "userId": user_id})
        if not chat:
            await websocket.send_json({"error": "Chat not found"})
            await websocket.close()
            return
        
        # Send connection confirmation (with error handling)
        try:
            await websocket.send_json({
                "type": "connected",
                "message": "WebSocket connected",
                "timestamp": datetime.utcnow().isoformat()
            })
        except (WebSocketDisconnect, ConnectionClosedOK, ConnectionClosedError) as e:
            logger.info(f"Client disconnected before confirmation could be sent: {e}")
            return
        except Exception as e:
            logger.error(f"Error sending connection confirmation: {e}")
            return
        
        # Keep connection open and wait for messages
        while True:
            try:
                # Wait for message from client (with timeout to keep connection alive)
                try:
                    data = await asyncio.wait_for(websocket.receive_json(), timeout=300.0)
                except asyncio.TimeoutError:
                    # Send keepalive ping
                    try:
                        await websocket.send_json({
                            "type": "ping",
                            "timestamp": datetime.utcnow().isoformat()
                        })
                    except (WebSocketDisconnect, ConnectionClosedOK, ConnectionClosedError):
                        break
                    continue
                
                message_content = data.get("message", "")
                
                if not message_content:
                    continue
        
                # Create user message in database
                message_doc = {
                    "chatId": chat_obj_id,
                    "userId": user_id,
                    "role": "user",
                    "content": message_content,
                    "attachments": data.get("attachments", []),
                    "sources": [],
                    "metadata": {},
                    "createdAt": datetime.utcnow(),
                    "tokens": None
                }
                msg_result = await db.messages.insert_one(message_doc)
                
                # Update chat's last message time
                await db.chats.update_one(
                    {"_id": chat_obj_id},
                    {"$set": {"lastMessageAt": datetime.utcnow()}}
                )
                
                # Get vector_store and session_memory from main module (global state)
                try:
                    import sys
                    import importlib
                    # Import from main module
                    if 'main' in sys.modules:
                        main_module = sys.modules['main']
                        vector_store = getattr(main_module, 'vector_store', None)
                        session_memory = getattr(main_module, 'session_memory', None)
                    else:
                        # Direct import
                        from main import vector_store, session_memory
                except Exception as e:
                    logger.warning(f"Could not import vector_store from main: {e}")
                    # Fallback: create new instances
                    from app.config import VECTOR_DB_PATH
                    try:
                        vector_store = VectorStore(VECTOR_DB_PATH)
                    except:
                        vector_store = None
                    session_memory = SessionMemory()
                
                # Get orchestrator for request coordination
                from app.orchestrator.research_orchestrator import get_orchestrator
                orchestrator = get_orchestrator()
                
                # Initialize AgentController with full pipeline
                agent = AgentController(
                    vector_store=vector_store,
                    session_memory=session_memory
                )
                
                # Use chat_id as session_id for agent
                session_id = str(chat_obj_id)
                
                # Store user_id in session for agent
                session = session_memory.get_session(session_id)
                if session:
                    session['user_id'] = str(user_id)
                
                # Send initial progress
                try:
                    await websocket.send_json({
                        "type": "progress",
                        "message": "🔍 Analyzing your request...",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except (WebSocketDisconnect, ConnectionClosedOK, ConnectionClosedError):
                    break
                
                # Process message with agent
                try:
                    # Process message and get response
                    result = await agent.process_message(message_content, session_id)
                    
                    # Stream progress updates
                    if agent.progress_updates:
                        for progress_msg in agent.progress_updates:
                            try:
                                await websocket.send_json({
                                    "type": "progress",
                                    "message": progress_msg,
                                    "timestamp": datetime.utcnow().isoformat()
                                })
                                await asyncio.sleep(0.1)  # Small delay between progress updates
                            except (WebSocketDisconnect, ConnectionClosedOK, ConnectionClosedError):
                                break
                    
                    # Get response text and sources
                    response_text = result.get("response", "I'm processing your request. Please wait...")
                    sources = result.get("sources", [])
                    metadata = result.get("metadata", {})
                    account_plan = result.get("account_plan")
                    
                    # Save account plan to database if generated or updated
                    if account_plan:
                        try:
                            from app.services.account_plan_service import AccountPlanService
                            # Get company_name from multiple sources (priority order)
                            company_name = None
                            
                            # 1. Try from account_plan itself (most reliable - it's in the plan JSON)
                            if account_plan and isinstance(account_plan, dict):
                                company_name = account_plan.get('company_name')
                            
                            # 2. Try from session
                            if not company_name and session:
                                company_name = session.get('company_name')
                            
                            # 3. Try from metadata
                            if not company_name:
                                company_name = metadata.get('company_name', 'Unknown')
                            
                            # 4. Clean up company_name - remove "research" or "reserach" prefix if present
                            if company_name:
                                company_name = str(company_name).strip()
                                # Remove "research" prefix if present (e.g., "research IBM" -> "IBM")
                                if company_name.lower().startswith('research '):
                                    company_name = company_name[9:].strip()
                                # Remove "reserach" typo prefix if present
                                if company_name.lower().startswith('reserach '):
                                    company_name = company_name[9:].strip()
                            
                            logger.info(f"Account plan received - extracted company_name: '{company_name}', plan_keys: {list(account_plan.keys()) if account_plan else 'None'}")
                            
                            if company_name and company_name != 'Unknown' and company_name.strip() != '' and account_plan:
                                try:
                                    plan_id = await AccountPlanService.save_account_plan(
                                        user_id=str(user_id),
                                        company_name=company_name,
                                        plan_json=account_plan,
                                        chat_id=str(chat_obj_id)
                                    )
                                    logger.info(f"✅ Account plan saved successfully: {plan_id} for company: {company_name}")
                                    
                                    # Send plan update notification to client
                                    try:
                                        await websocket.send_json({
                                            "type": "plan_updated",
                                            "planId": plan_id,
                                            "companyName": company_name,
                                            "timestamp": datetime.utcnow().isoformat()
                                        })
                                    except:
                                        pass  # Client may have disconnected
                                    
                                    # Update chat title with company name if not already set or if it's generic
                                    try:
                                        current_chat = await db.chats.find_one({"_id": chat_obj_id})
                                        if current_chat:
                                            current_title = current_chat.get("title", "")
                                            if not current_title or current_title == "New Chat" or current_title == "Untitled Chat":
                                                await db.chats.update_one(
                                                    {"_id": chat_obj_id},
                                                    {"$set": {"title": company_name}}
                                                )
                                    except Exception as title_error:
                                        logger.warning(f"Failed to update chat title: {title_error}")
                                        
                                except Exception as save_error:
                                    logger.error(f"❌ Failed to save account plan: {save_error}", exc_info=True)
                            else:
                                logger.warning(f"⚠️ Skipping account plan save - company_name: '{company_name}', has_plan: {bool(account_plan)}")
                        except Exception as e:
                            logger.error(f"Error saving account plan: {e}", exc_info=True)
                    
                    # Stream response text token by token
                    tokens = response_text.split()
                    assistant_message_parts = []
                    
                    for token in tokens:
                        assistant_message_parts.append(token)
                        current_text = " ".join(assistant_message_parts)
                        
                        # Send token
                        try:
                            await websocket.send_json({
                                "type": "token",
                                "token": token,
                                "text": current_text,
                                "timestamp": datetime.utcnow().isoformat()
                            })
                        except (WebSocketDisconnect, ConnectionClosedOK, ConnectionClosedError):
                            break
                        
                        # Small delay for streaming effect
                        await asyncio.sleep(0.03)
                    
                    # Send completion with sources
                    try:
                        await websocket.send_json({
                            "type": "complete",
                            "text": response_text,
                            "sources": sources,
                            "metadata": metadata,
                            "timestamp": datetime.utcnow().isoformat()
                        })
                    except (WebSocketDisconnect, ConnectionClosedOK, ConnectionClosedError):
                        break
                    
                except Exception as e:
                    logger.error(f"Error in agent processing: {e}", exc_info=True)
                    # Send error message
                    error_msg = f"I encountered an error while processing your request: {str(e)}"
                    try:
                        await websocket.send_json({
                            "type": "error",
                            "message": error_msg,
                            "timestamp": datetime.utcnow().isoformat()
                        })
                        response_text = error_msg
                    except (WebSocketDisconnect, ConnectionClosedOK, ConnectionClosedError):
                        break
                
                # Save assistant message to database
                assistant_msg_doc = {
                    "chatId": chat_obj_id,
                    "userId": user_id,
                    "role": "assistant",
                    "content": response_text,
                    "attachments": [],
                    "sources": sources if 'sources' in locals() else [],
                    "metadata": metadata if 'metadata' in locals() else {},
                    "createdAt": datetime.utcnow(),
                    "tokens": len(tokens) if 'tokens' in locals() else 0
                }
                await db.messages.insert_one(assistant_msg_doc)
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for chat {chat_id}")
                break
            except (ConnectionClosedOK, ConnectionClosedError) as e:
                logger.info(f"Connection closed: {e}")
                break
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                try:
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e),
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except (WebSocketDisconnect, ConnectionClosedOK, ConnectionClosedError):
                    break
        
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for chat {chat_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
        except:
            pass
        try:
            await websocket.close()
        except:
            pass

