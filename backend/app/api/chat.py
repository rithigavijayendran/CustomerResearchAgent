"""
Chat API endpoints
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from app.models.schemas import ChatMessage, ChatResponse
from app.agent.agent_controller import AgentController
from app.auth.auth_middleware import get_current_user
from app.services.research_history_service import ResearchHistoryService
from app.services.account_plan_service import AccountPlanService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/", response_model=ChatResponse)
async def chat_endpoint(
    message: ChatMessage, 
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Handle chat messages"""
    try:
        logger.info(f"Received chat message: {message.message[:50]}...")
        vector_store = request.state.vector_store
        session_memory = request.state.session_memory
        
        # Check if vector store is available
        if not vector_store:
            logger.warning("Vector store not initialized - RAG features disabled")
        
        # Get or create session
        session_id = message.session_id
        if not session_id:
            session_id = session_memory.create_session()
            logger.info(f"Created new session: {session_id}")
        
        # Initialize agent controller
        logger.info("Initializing agent controller...")
        logger.info("Creating Gemini LLM engine...")
        agent = AgentController(vector_store, session_memory)
        logger.info(f"Agent controller initialized with LLM provider: {agent.llm_provider}")
        
        # Store user_id in session for later use
        session = session_memory.get_session(session_id)
        if session:
            session['user_id'] = current_user["id"]
            # Session is a reference, so changes are automatically saved
        else:
            # Create session if it doesn't exist
            session_id = session_memory.create_session(session_id)
            session = session_memory.get_session(session_id)
            if session:
                session['user_id'] = current_user["id"]
        
        # Process message
        logger.info("Processing message...")
        result = await agent.process_message(message.message, session_id)
        logger.info("Message processed successfully")
        
        # Get session for company name
        session = session_memory.get_session(session_id)
        
        # Save research logs to MongoDB
        if result.get("progress_updates"):
            company_name = session.get('company_name') if session else None
            if company_name:
                for update in result.get("progress_updates", []):
                    await ResearchHistoryService.add_log(
                        current_user["id"],
                        company_name,
                        {"message": update, "type": "progress"}
                    )
        
        # Save account plan to MongoDB if generated or updated
        account_plan = result.get("account_plan")
        if account_plan:
            logger.info(f"Account plan received in chat endpoint - keys: {list(account_plan.keys()) if account_plan else 'None'}")
            company_name = session.get('company_name') if session else None
            logger.info(f"Company name from session: {company_name}")
            
            if company_name and account_plan:
                # Extract chat_id from session_id if it's a chat ID
                chat_id = None
                if session_id:
                    # Check if session_id is a valid ObjectId (chat ID)
                    try:
                        from bson import ObjectId
                        ObjectId(session_id)  # Validate it's a valid ObjectId
                        chat_id = session_id
                        logger.info(f"Using session_id as chat_id: {chat_id}")
                    except:
                        logger.info(f"session_id is not a valid ObjectId: {session_id}")
                        pass  # Not a chat ID, skip
                
                try:
                    plan_id = await AccountPlanService.save_account_plan(
                        current_user["id"],
                        company_name,
                        account_plan,
                        chat_id=chat_id
                    )
                    logger.info(f"✅ Account plan saved successfully via chat endpoint: {plan_id}")
                except Exception as save_error:
                    logger.error(f"❌ Failed to save account plan via chat endpoint: {save_error}", exc_info=True)
            else:
                logger.warning(f"⚠️ Skipping account plan save - company_name: {company_name}, has_plan: {bool(account_plan)}")
                
                # Update chat title with company name if not already set
                if chat_id:
                    try:
                        from app.database import get_database
                        from bson import ObjectId
                        db = get_database()
                        if db:
                            chat_obj_id = ObjectId(chat_id)
                            current_chat = await db.chats.find_one({"_id": chat_obj_id})
                            if current_chat:
                                current_title = current_chat.get("title", "")
                                if not current_title or current_title == "New Chat" or current_title == "Untitled Chat":
                                    await db.chats.update_one(
                                        {"_id": chat_obj_id},
                                        {"$set": {"title": company_name}}
                                    )
                    except Exception as e:
                        logger.warning(f"Failed to update chat title: {e}")
        
        return ChatResponse(
            response=result.get("response", ""),
            session_id=result.get("session_id", session_id),
            agent_thinking=result.get("agent_thinking"),
            progress_updates=result.get("progress_updates"),
            questions=result.get("questions"),
            account_plan=result.get("account_plan")
        )
    
    except ValueError as e:
        error_msg = str(e)
        logger.error(f"Configuration error: {error_msg}")
        raise HTTPException(
            status_code=400, 
            detail=f"Configuration error: {error_msg}. Please check your API keys in backend/.env file."
        )
    except TimeoutError as e:
        error_msg = str(e)
        logger.error(f"Timeout error: {error_msg}")
        raise HTTPException(
            status_code=504,
            detail=f"Request timed out: {error_msg}. The research is taking longer than expected. Please try again or break down your request into smaller parts."
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Chat error: {error_msg}", exc_info=True)
        
        # Provide user-friendly error messages
        if "API" in error_msg and ("key" in error_msg.lower() or "quota" in error_msg.lower()):
            user_message = "API configuration issue detected. Please check your API keys and quotas in backend/.env"
        elif "timeout" in error_msg.lower():
            user_message = "The request took too long. Please try again or ask for a simpler research task."
        else:
            user_message = f"I encountered an error: {error_msg[:200]}. Please try again or contact support if the issue persists."
        
        raise HTTPException(
            status_code=500, 
            detail=user_message
        )

