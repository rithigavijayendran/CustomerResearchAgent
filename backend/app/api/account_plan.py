"""
Account Plan API endpoints
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from app.models.schemas import AccountPlanSection, AccountPlanUpdate
from app.agent.agent_controller import AgentController
from app.auth.auth_middleware import get_current_user
from app.services.account_plan_service import AccountPlanService
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/list")
async def list_account_plans(current_user: dict = Depends(get_current_user)):
    """List all account plans for the current user"""
    try:
        user_id = current_user["id"]
        logger.info(f"Listing account plans for user_id: {user_id} (type: {type(user_id)})")
        plans = await AccountPlanService.list_account_plans(user_id)
        logger.info(f"Found {len(plans)} account plans for user {user_id}")
        logger.debug(f"Plans data: {plans}")
        return {"plans": plans}
    except Exception as e:
        logger.error(f"List account plans error: {e}", exc_info=True)
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{company_name}")
async def get_account_plan(
    company_name: str,
    current_user: dict = Depends(get_current_user)
):
    """Get account plan for a company (by company name)"""
    try:
        plan = await AccountPlanService.get_account_plan(
            current_user["id"],
            company_name
        )
        
        if not plan:
            raise HTTPException(status_code=404, detail="Account plan not found")
        
        return {
            "id": plan.get("id"),
            "company_name": plan.get("company_name", ""),
            "plan_json": plan.get("plan_json", {}),
            "updated_at": plan.get("updated_at")
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get account plan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/by-id/{plan_id}")
async def get_account_plan_by_id(
    plan_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get account plan by plan ID"""
    try:
        from app.database import get_database
        from bson import ObjectId
        
        db = get_database()
        if db is None:
            raise HTTPException(status_code=500, detail="Database connection error")
        
        user_id = ObjectId(current_user["id"])
        plan_obj_id = ObjectId(plan_id)
        
        # Get plan using new schema
        plan = await db.account_plans.find_one({"_id": plan_obj_id, "userId": user_id})
        
        if not plan:
            raise HTTPException(status_code=404, detail="Account plan not found")
        
        company_name = plan.get("companyName") or plan.get("company_name", "")
        plan_json = plan.get("planJSON") or plan.get("plan_json", {})
        updated_at = plan.get("updatedAt") or plan.get("updated_at")
        
        return {
            "id": str(plan["_id"]),
            "company_name": company_name,
            "plan_json": plan_json,
            "updated_at": updated_at.isoformat() if updated_at else None
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get account plan by ID error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/update")
async def update_account_plan(
    update: AccountPlanUpdate, 
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Update a specific section of the account plan"""
    try:
        vector_store = request.state.vector_store
        session_memory = request.state.session_memory
        
        session = session_memory.get_session(update.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if not session.get('account_plan'):
            raise HTTPException(status_code=404, detail="Account plan not found")
        
        # Initialize agent controller
        agent = AgentController(vector_store, session_memory)
        
        # Update section
        account_plan = session['account_plan']
        
        if update.regenerate:
            # Regenerate section using agent
            company_name = session.get('company_name', 'the company')
            research_data = session.get('research_data', [])
            
            updated_content = await agent._regenerate_section(
                company_name,
                update.section,
                research_data,
                account_plan
            )
        else:
            updated_content = update.new_content
        
        # Update account plan
        if '.' in update.section:
            # Nested section
            parts = update.section.split('.')
            if len(parts) == 2:
                if parts[0] not in account_plan:
                    account_plan[parts[0]] = {}
                account_plan[parts[0]][parts[1]] = updated_content
        else:
            account_plan[update.section] = updated_content
        
        # Save to MongoDB
        session = session_memory.get_session(update.session_id)
        company_name = session.get('company_name') if session else None
        if company_name:
            await AccountPlanService.save_account_plan(
                current_user["id"],
                company_name,
                account_plan
            )
        
        return {
            "status": "success",
            "section": update.section,
            "account_plan": account_plan
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update account plan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

