"""
Account Plan API endpoints - Production Grade
GET /api/plans/:planId, PUT /api/plans/:planId/section/:sectionKey, 
POST /api/plans/:planId/section/:sectionKey/regenerate
"""

from fastapi import APIRouter, HTTPException, Depends, Path
from fastapi.responses import StreamingResponse
from typing import Optional, Dict, Any
from datetime import datetime
from bson import ObjectId
import json
import uuid
import logging
from io import BytesIO

from app.models.schemas import PlanResponse, SectionUpdate, SectionRegenerateResponse
from app.auth.auth_middleware import get_current_user
from app.database import get_database
from app.llm.gemini_engine import GeminiEngine
from app.rag.retrieval_api import RetrievalAPI
from app.rag.vector_store import VectorStore
from app.config import VECTOR_DB_PATH
from app.api.pdf_export import create_pdf_from_account_plan
from app.api.pdf_generator import generate_pdf_from_plan

logger = logging.getLogger(__name__)

router = APIRouter()


def _clean_generated_content(content: str) -> str:
    """
    Remove sources, RAG context, and confidence information from generated content
    """
    if not content:
        return content
    
    import re
    
    # Remove "Sources:" section and everything after it
    sources_pattern = r'\n\s*Sources?\s*:.*$'
    content = re.sub(sources_pattern, '', content, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
    
    # Remove "RAG Context:" section and everything after it
    rag_pattern = r'\n\s*RAG\s+Context\s*:.*$'
    content = re.sub(rag_pattern, '', content, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
    
    # Remove lines with confidence percentages
    lines = content.split('\n')
    cleaned_lines = []
    skip_mode = False
    
    for line in lines:
        line_lower = line.lower().strip()
        
        # Start skipping if we see sources/rag context keywords
        if any(keyword in line_lower for keyword in ['sources:', 'rag context:', 'confidence:']):
            skip_mode = True
            continue
        
        # Skip lines with percentages that are likely confidence scores
        if skip_mode:
            if not line.strip():
                skip_mode = False
            elif '%' in line and any(keyword in line_lower for keyword in ['confidence', 'rag', 'source']):
                continue
            else:
                skip_mode = False
        
        # Skip standalone percentage lines that look like confidence scores
        if line.strip().endswith('%') and len(line.strip()) < 20:
            continue
        
        cleaned_lines.append(line)
    
    cleaned_content = '\n'.join(cleaned_lines).strip()
    
    # Final cleanup - remove any trailing sections
    cleaned_content = re.sub(r'\n\s*(Sources?|RAG\s+Context|Confidence)\s*:.*$', '', cleaned_content, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
    
    return cleaned_content.strip()


@router.get("/by-chat/{chat_id}", response_model=PlanResponse)
async def get_plan_by_chat(
    chat_id: str = Path(..., description="Chat ID"),
    current_user: dict = Depends(get_current_user)
):
    """Get account plan by chat ID"""
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
        
        # Get plan by chatId
        plan = await db.account_plans.find_one({"chatId": chat_obj_id, "userId": user_id})
        if not plan:
            raise HTTPException(status_code=404, detail="Account plan not found for this chat")
        
        return PlanResponse(
            id=str(plan["_id"]),
            userId=str(plan["userId"]),
            chatId=str(plan.get("chatId", "")) if plan.get("chatId") else None,
            companyName=plan.get("companyName", plan.get("company_name", "")),
            planJSON=plan.get("planJSON", plan.get("plan_json", {})),
            versions=plan.get("versions", []),
            sources=plan.get("sources", []),
            status=plan.get("status", "draft"),
            createdAt=plan.get("createdAt", plan.get("created_at")),
            updatedAt=plan.get("updatedAt", plan.get("updated_at"))
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting plan by chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get plan")

@router.get("/{plan_id}", response_model=PlanResponse)
async def get_plan(
    plan_id: str = Path(..., description="Plan ID"),
    current_user: dict = Depends(get_current_user)
):
    """Get account plan with version history"""
    try:
        db = get_database()
        if db is None:
            raise HTTPException(status_code=500, detail="Database connection error")
        
        user_id = ObjectId(current_user["id"])
        plan_obj_id = ObjectId(plan_id)
        
        # Get plan
        plan = await db.account_plans.find_one({"_id": plan_obj_id, "userId": user_id})
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        return PlanResponse(
            id=str(plan["_id"]),
            userId=str(plan["userId"]),
            chatId=str(plan.get("chatId", "")) if plan.get("chatId") else None,
            companyName=plan.get("companyName", plan.get("company_name", "")),
            planJSON=plan.get("planJSON", plan.get("plan_json", {})),
            versions=plan.get("versions", []),
            sources=plan.get("sources", []),
            status=plan.get("status", "draft"),
            createdAt=plan.get("createdAt", plan.get("created_at")),
            updatedAt=plan.get("updatedAt", plan.get("updated_at"))
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting plan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get plan")

@router.put("/{plan_id}/section/{section_key}")
async def update_section(
    plan_id: str = Path(..., description="Plan ID"),
    section_key: str = Path(..., description="Section key (e.g., 'company_overview', 'swot.strengths')"),
    update: SectionUpdate = ...,
    current_user: dict = Depends(get_current_user)
):
    """Update a section of the plan (draft mode)"""
    try:
        db = get_database()
        if db is None:
            raise HTTPException(status_code=500, detail="Database connection error")
        
        user_id = ObjectId(current_user["id"])
        plan_obj_id = ObjectId(plan_id)
        
        # Get plan
        plan = await db.account_plans.find_one({"_id": plan_obj_id, "userId": user_id})
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        # Update section in planJSON
        plan_json = plan.get("planJSON", plan.get("plan_json", {}))
        
        # Handle nested sections (e.g., "swot.strengths")
        if "." in section_key:
            parts = section_key.split(".")
            current = plan_json
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[parts[-1]] = update.content
        else:
            plan_json[section_key] = update.content
        
        # Update plan
        await db.account_plans.update_one(
            {"_id": plan_obj_id},
            {
                "$set": {
                    "planJSON": plan_json,
                    "updatedAt": datetime.utcnow()
                }
            }
        )
        
        return {
            "id": plan_id,
            "section": section_key,
            "content": update.content,
            "updatedAt": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating section: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update section")

@router.post("/{plan_id}/section/{section_key}/regenerate", response_model=SectionRegenerateResponse)
async def regenerate_section(
    plan_id: str = Path(..., description="Plan ID"),
    section_key: str = Path(..., description="Section key"),
    current_user: dict = Depends(get_current_user)
):
    """Regenerate a section using RAG + Gemini with strict JSON"""
    try:
        db = get_database()
        if db is None:
            raise HTTPException(status_code=500, detail="Database connection error")
        
        user_id = ObjectId(current_user["id"])
        plan_obj_id = ObjectId(plan_id)
        
        # Get plan
        plan = await db.account_plans.find_one({"_id": plan_obj_id, "userId": user_id})
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        company_name = plan.get("companyName", plan.get("company_name", ""))
        plan_json = plan.get("planJSON", plan.get("plan_json", {}))
        
        # Lock plan (in production, use proper locking mechanism)
        # For now, we'll just proceed
        
        # Retrieve RAG context for this section
        context = ""
        chunks = []
        sources = []
        confidence = 0.8
        
        try:
            vector_store = VectorStore(VECTOR_DB_PATH)
            retrieval_api = RetrievalAPI(vector_store)
            
            # Build query for section
            query = f"{company_name} {section_key.replace('_', ' ')}"
            chunks = retrieval_api.retrieve_relevant_chunks(
                query=query,
                company=company_name,
                top_k=5,
                user_id=str(user_id)
            )
            
            # Build context from chunks
            if chunks:
                context = "\n\n".join([
                    f"Source: {chunk.get('metadata', {}).get('sourceUrl', 'unknown')}\n{chunk.get('text', '')}"
                    for chunk in chunks
                ])
                # Extract sources and confidence from chunks
                for chunk in chunks[:3]:
                    metadata = chunk.get("metadata", {})
                    sources.append({
                        "url": metadata.get("sourceUrl", ""),
                        "type": metadata.get("sourceType", "unknown"),
                        "confidence": metadata.get("confidence", 0.8)
                    })
                    confidence = max(confidence, metadata.get("confidence", 0.8))
            else:
                # If no chunks found, use current plan content as context
                context = f"Company: {company_name}\nCurrent plan data: {json.dumps(plan_json, indent=2)[:2000]}"
                logger.warning(f"No RAG chunks found for {section_key}, using plan context")
        except Exception as e:
            logger.warning(f"Error retrieving RAG context: {e}, continuing with plan context")
            # Fallback to using current plan content
            context = f"Company: {company_name}\nCurrent plan data: {json.dumps(plan_json, indent=2)[:2000]}"
        
        # Get current section content for context
        current_content = ""
        if "." in section_key:
            parts = section_key.split(".")
            current = plan_json
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    current = ""
                    break
            current_content = str(current) if current else ""
        else:
            current_content = str(plan_json.get(section_key, ""))
        
        # Generate strict JSON prompt for Gemini
        gemini = GeminiEngine()
        
        # Build section-specific prompt
        section_prompts = {
            "company_overview": "Generate a comprehensive company overview (400-600 words) with specific details about history, business model, market position.",
            "market_summary": "Generate a detailed market analysis (250-400 words) with specific market data, growth rates, and competitive positioning.",
            "key_insights": "Generate 5-7 key strategic insights (300-450 words) with specific examples and business implications.",
            "pain_points": "Generate 4-6 major pain points (250-350 words) with specific challenges and examples.",
            "opportunities": "Generate 4-6 growth opportunities (200-300 words) with specific market opportunities and potential impact.",
            "competitor_analysis": "Generate comprehensive competitor analysis (250-350 words) with specific competitors and market positioning.",
            "strategic_recommendations": "Generate 4-6 strategic recommendations (250-350 words) with specific actionable steps.",
            "final_account_plan": "Generate executive summary (300-400 words) synthesizing all findings."
        }
        
        section_instruction = section_prompts.get(section_key, f"Generate content for {section_key}")
        
        prompt = f"""You are an enterprise research assistant. Generate content for the '{section_key}' section of an account plan for {company_name}.

CRITICAL REQUIREMENTS:
- Return ONLY the text content for this section (no JSON wrapper, no markdown code blocks)
- Use the RAG context below as your primary source
- Write in professional business English
- Be specific and data-driven
- DO NOT include sources, citations, confidence scores, or RAG context information in your response
- DO NOT include "Sources:" or "RAG Context:" sections
- Return ONLY the business content, nothing else

RAG Context:
{context[:3000]}

Current Section Content (for reference):
{current_content[:500]}

{section_instruction}

Return ONLY the text content, no explanations, no markdown, no JSON structure, no sources, no citations."""
        
        # Generate content
        try:
            generated_content = gemini.generate(
                prompt=prompt,
                system_prompt="You are a senior business analyst. Return ONLY the requested text content, no markdown, no JSON, no explanations, no sources, no citations, no confidence scores, no RAG context information.",
                temperature=0.7,
                max_tokens=4000,
                timeout=60
            )
            
            if not generated_content or not generated_content.strip():
                raise ValueError("Generated content is empty")
            
            # Clean up any sources/RAG context that might have been included
            generated_content = _clean_generated_content(generated_content)
                
        except Exception as e:
            logger.error(f"Error generating content with Gemini: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to generate content: {str(e)}. Please check your Gemini API key and try again."
            )
        
        # Create version entry
        version_id = str(uuid.uuid4())
        version_entry = {
            "versionId": version_id,
            "timestamp": datetime.utcnow(),
            "userId": str(user_id),
            "changes": {
                "section": section_key,
                "oldContent": current_content,
                "newContent": generated_content
            },
            "diff": {
                "section": section_key,
                "type": "regenerated"
            }
        }
        
        # Update plan with new section and version
        updated_plan_json = plan_json.copy()
        if "." in section_key:
            parts = section_key.split(".")
            current = updated_plan_json
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[parts[-1]] = generated_content
        else:
            updated_plan_json[section_key] = generated_content
        
        versions = plan.get("versions", [])
        versions.append(version_entry)
        
        await db.account_plans.update_one(
            {"_id": plan_obj_id},
            {
                "$set": {
                    "planJSON": updated_plan_json,
                    "versions": versions,
                    "updatedAt": datetime.utcnow()
                }
            }
        )
        
        return SectionRegenerateResponse(
            section=section_key,
            content=generated_content,
            sources=sources,
            confidence=confidence,
            versionId=version_id
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating section: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to regenerate section")

@router.delete("/{plan_id}")
async def delete_plan(
    plan_id: str = Path(..., description="Plan ID"),
    current_user: dict = Depends(get_current_user)
):
    """Delete an account plan"""
    try:
        db = get_database()
        if db is None:
            raise HTTPException(status_code=500, detail="Database connection error")
        
        user_id = ObjectId(current_user["id"])
        plan_obj_id = ObjectId(plan_id)
        
        # Verify plan belongs to user
        plan = await db.account_plans.find_one({"_id": plan_obj_id, "userId": user_id})
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        # Delete the plan
        result = await db.account_plans.delete_one({"_id": plan_obj_id, "userId": user_id})
        if result.deleted_count > 0:
            logger.info(f"Deleted plan {plan_id} for user {user_id}")
            return {"message": "Account plan deleted successfully", "deleted": True}
        else:
            raise HTTPException(status_code=404, detail="Plan not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting plan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete plan")

@router.get("/{plan_id}/download")
async def download_plan_pdf(
    plan_id: str = Path(..., description="Plan ID"),
    current_user: dict = Depends(get_current_user)
):
    """Download account plan as PDF (server-side generation)"""
    try:
        db = get_database()
        if db is None:
            raise HTTPException(status_code=500, detail="Database connection error")
        
        user_id = ObjectId(current_user["id"])
        plan_obj_id = ObjectId(plan_id)
        
        # Get plan
        plan = await db.account_plans.find_one({"_id": plan_obj_id, "userId": user_id})
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        company_name = plan.get("companyName", plan.get("company_name", "Company"))
        plan_json = plan.get("planJSON", plan.get("plan_json", {}))
        sources = plan.get("sources", [])
        user_name = current_user.get("name", current_user.get("email", "User"))
        
        # Generate PDF using Playwright (with fallback to ReportLab)
        pdf_buffer = await generate_pdf_from_plan(
            plan_json=plan_json,
            company_name=company_name,
            user_name=user_name,
            sources=sources
        )
        
        # Generate filename with date
        date_str = datetime.utcnow().strftime("%Y%m%d")
        filename = f"{company_name.replace(' ', '_')}_AccountPlan_{date_str}.pdf"
        
        return StreamingResponse(
            BytesIO(pdf_buffer.read()),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate PDF")

