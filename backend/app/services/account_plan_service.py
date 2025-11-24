"""
Service for managing account plans in MongoDB
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
import logging

from app.database import get_database

logger = logging.getLogger(__name__)

class AccountPlanService:
    """Service for account plan operations"""
    
    @staticmethod
    async def save_account_plan(
        user_id: str,
        company_name: str,
        plan_json: Dict[str, Any],
        chat_id: Optional[str] = None
    ) -> str:
        """Save or update account plan"""
        logger.info(f"Saving account plan - user_id: {user_id}, company_name: {company_name}, chat_id: {chat_id}")
        logger.info(f"Plan JSON keys: {list(plan_json.keys()) if plan_json else 'None'}")
        logger.info(f"Plan JSON size: {len(str(plan_json)) if plan_json else 0} chars")
        
        # Validate inputs
        if not user_id:
            raise ValueError("user_id is required")
        if not company_name or company_name.strip() == '':
            raise ValueError("company_name is required")
        if not plan_json or not isinstance(plan_json, dict):
            logger.warning(f"Invalid plan_json: {type(plan_json)}")
            raise ValueError("plan_json must be a non-empty dictionary")
        
        db = get_database()
        if db is None:
            raise ValueError("Database not available")
        
        try:
            user_obj_id = ObjectId(user_id)
        except Exception as e:
            logger.error(f"Invalid user_id format: {user_id}, error: {e}")
            raise ValueError(f"Invalid user_id format: {user_id}")
        
        # Check if plan exists (by chat_id if provided, otherwise by company_name)
        # Priority: 1) chat_id, 2) company_name (case-insensitive)
        existing = None
        
        # First, try to find by chat_id (most reliable for updates)
        if chat_id:
            try:
                chat_obj_id = ObjectId(chat_id)
                query = {"userId": user_obj_id, "chatId": chat_obj_id}
                logger.info(f"Looking for plan with chatId: {chat_id} and userId: {user_id}")
                existing = await db.account_plans.find_one(query)
                
                # If not found with new schema, try old schema
                if not existing:
                    old_query = {"user_id": user_obj_id, "chat_id": chat_obj_id}
                    existing = await db.account_plans.find_one(old_query)
                    logger.info(f"Tried old schema with chat_id: {existing is not None}")
            except Exception as e:
                logger.warning(f"Invalid chat_id format: {chat_id}, error: {e}. Falling back to company_name search.")
                chat_id = None  # Ignore invalid chat_id
        
        # If not found by chat_id, try by company_name (case-insensitive)
        if not existing:
            # Try exact match first (new schema)
            query = {"userId": user_obj_id, "companyName": company_name}
            logger.info(f"Looking for plan with companyName (exact): {company_name}")
            existing = await db.account_plans.find_one(query)
            
            # If not found, try case-insensitive match
            if not existing:
                # MongoDB case-insensitive search using regex
                import re
                query = {
                    "userId": user_obj_id,
                    "companyName": {"$regex": f"^{re.escape(company_name)}$", "$options": "i"}
                }
                logger.info(f"Looking for plan with companyName (case-insensitive): {company_name}")
                existing = await db.account_plans.find_one(query)
            
            # If still not found, try old schema
            if not existing:
                old_query = {"user_id": user_obj_id, "company_name": company_name}
                existing = await db.account_plans.find_one(old_query)
                
                # Try case-insensitive with old schema
                if not existing:
                    import re
                    old_query = {
                        "user_id": user_obj_id,
                        "company_name": {"$regex": f"^{re.escape(company_name)}$", "$options": "i"}
                    }
                    existing = await db.account_plans.find_one(old_query)
        
        logger.info(f"Existing plan found: {existing is not None}")
        if existing:
            logger.info(f"✅ Found existing plan ID: {existing.get('_id')}, company: {existing.get('companyName') or existing.get('company_name')}, chat_id: {existing.get('chatId') or existing.get('chat_id')}")
        else:
            logger.info(f"ℹ️ No existing plan found - will create new plan for company: {company_name}, chat_id: {chat_id}")
        
        if existing:
            # Update existing plan with versioning - ensure new schema fields
            current_version = existing.get("version", 1)
            new_version = current_version + 1
            
            # Build update document - ensure all fields use new schema
            update_doc = {
                "$set": {
                    "planJSON": plan_json,
                    "companyName": company_name,
                    "userId": ObjectId(user_id),  # Ensure new schema
                    "updatedAt": datetime.utcnow()
                },
                "$push": {
                    "versions": {
                        "versionId": str(ObjectId()),
                        "timestamp": datetime.utcnow(),
                        "userId": user_id,
                        "changes": {"type": "update", "planJSON": plan_json}
                    }
                }
            }
            
            # Add chatId if provided
            if chat_id:
                update_doc["$set"]["chatId"] = ObjectId(chat_id)
            
            # Remove old schema fields if they exist
            update_doc["$unset"] = {
                "user_id": "",
                "company_name": "",
                "plan_json": "",
                "chat_id": "",
                "created_at": "",
                "updated_at": ""
            }
            
            await db.account_plans.update_one(
                {"_id": existing["_id"]},
                update_doc
            )
            logger.info(f"✅ Successfully updated existing account plan: {existing['_id']} (not creating new one)")
            return str(existing["_id"])
        else:
            # Create new plan
            plan_doc = {
                "userId": user_obj_id,
                "companyName": company_name,
                "planJSON": plan_json,
                "versions": [{
                    "versionId": str(ObjectId()),
                    "timestamp": datetime.utcnow(),
                    "userId": user_id,
                    "changes": {"type": "create", "planJSON": plan_json}
                }],
                "sources": [],
                "status": "draft",
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow()
            }
            
            # Add chatId only if valid
            if chat_id:
                try:
                    plan_doc["chatId"] = ObjectId(chat_id)
                except Exception as e:
                    logger.warning(f"Invalid chat_id, not including in plan: {e}")
            
            logger.info(f"Inserting new plan document with keys: {list(plan_doc.keys())}")
            result = await db.account_plans.insert_one(plan_doc)
            plan_id = str(result.inserted_id)
            logger.info(f"✅ Successfully created account plan with ID: {plan_id}")
            return plan_id
    
    @staticmethod
    async def get_account_plan(
        user_id: str,
        company_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get account plan for a company"""
        db = get_database()
        if db is None:
            return None
        
        # Try new schema first, then fallback to old
        plan = await db.account_plans.find_one({
            "userId": ObjectId(user_id),
            "companyName": company_name
        })
        
        # Fallback to old schema if not found
        if not plan:
            plan = await db.account_plans.find_one({
                "user_id": ObjectId(user_id),
                "company_name": company_name
            })
        
        if plan:
            # Convert datetime objects to ISO strings for JSON serialization
            created_at = plan.get("createdAt") or plan.get("created_at")
            updated_at = plan.get("updatedAt") or plan.get("updated_at")
            company_name = plan.get("companyName") or plan.get("company_name", "")
            plan_json = plan.get("planJSON") or plan.get("plan_json", {})
            
            return {
                "id": str(plan["_id"]),
                "company_name": company_name,
                "plan_json": plan_json,
                "created_at": created_at.isoformat() if created_at else None,
                "updated_at": updated_at.isoformat() if updated_at else None
            }
        return None
    
    @staticmethod
    async def list_account_plans(user_id: str) -> List[Dict[str, Any]]:
        """List all account plans for a user"""
        db = get_database()
        if db is None:
            logger.warning("Database not available for list_account_plans")
            return []
        
        try:
            user_obj_id = ObjectId(user_id)
        except Exception as e:
            logger.error(f"Invalid user_id format: {user_id}, error: {e}")
            return []
        
        logger.info(f"Listing account plans for user_id: {user_id} (ObjectId: {user_obj_id})")
        
        # Try new schema first: userId (not user_id), companyName (not company_name)
        # Also try old schema in same query using $or
        try:
            plans_cursor = db.account_plans.find(
                {
                    "$or": [
                        {"userId": user_obj_id},  # New schema
                        {"user_id": user_obj_id}  # Old schema
                    ]
                }
            ).sort("updatedAt", -1)
        except Exception as e:
            logger.error(f"Error querying account_plans collection: {e}")
            return []
        
        result = []
        count = 0
        async for plan in plans_cursor:
            count += 1
            # Convert datetime objects to ISO strings for JSON serialization
            created_at = plan.get("createdAt") or plan.get("created_at")
            updated_at = plan.get("updatedAt") or plan.get("updated_at")
            company_name = plan.get("companyName") or plan.get("company_name", "")
            plan_json = plan.get("planJSON") or plan.get("plan_json", {})
            
            # Skip plans without company name or plan data
            if not company_name or not plan_json or len(plan_json) == 0:
                logger.debug(f"Skipping plan {count}: missing company_name or plan_json")
                continue
            
            logger.debug(f"Found plan {count}: company={company_name}, has_plan_json={bool(plan_json)}")
            
            # Migrate to new schema if using old schema
            if "user_id" in plan or "company_name" in plan or "plan_json" in plan:
                try:
                    await db.account_plans.update_one(
                        {"_id": plan["_id"]},
                        {
                            "$set": {
                                "userId": user_obj_id,
                                "companyName": company_name,
                                "planJSON": plan_json,
                                "updatedAt": updated_at or datetime.utcnow(),
                                "createdAt": created_at or datetime.utcnow()
                            },
                            "$unset": {
                                "user_id": "",
                                "company_name": "",
                                "plan_json": "",
                                "created_at": "",
                                "updated_at": ""
                            }
                        }
                    )
                    logger.info(f"Migrated plan {plan['_id']} from old schema to new schema")
                except Exception as e:
                    logger.warning(f"Failed to migrate plan {plan['_id']}: {e}")
            
            result.append({
                "id": str(plan["_id"]),
                "planId": str(plan["_id"]),  # Also include as planId for compatibility
                "company_name": company_name,
                "plan_json": plan_json,  # Include planJSON
                "created_at": created_at.isoformat() if created_at else None,
                "updated_at": updated_at.isoformat() if updated_at else None
            })
        
        # Note: We now check both schemas in the same query above, so this fallback is less needed
        # But keep it for safety
        
        logger.info(f"Returning {len(result)} account plans for user {user_id}")
        return result

