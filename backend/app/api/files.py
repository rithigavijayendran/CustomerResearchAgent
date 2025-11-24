"""
File upload API endpoints
"""

from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException, Depends
from app.models.schemas import FileUploadResponse
from app.rag.rag_pipeline import RAGPipeline
from app.auth.auth_middleware import get_current_user
from app.services.rag_chunk_service import RAGChunkService
import os
import aiofiles
import logging
from pathlib import Path
from app.config import UPLOAD_DIR

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    company_name: str = Form(None),
    request: Request = None,
    current_user: dict = Depends(get_current_user)
):
    """Upload and process a document for a specific company"""
    try:
        vector_store = request.state.vector_store if request else None
        if not vector_store:
            raise HTTPException(status_code=503, detail="Vector store not available")
        user_id = current_user["id"]
        
        # If company_name not provided, try to extract from filename
        if not company_name or not company_name.strip():
            filename_base = Path(file.filename).stem
            # Simple heuristic: take first word before underscore or dash
            if '_' in filename_base:
                company_name = filename_base.split('_')[0]
            elif '-' in filename_base:
                company_name = filename_base.split('-')[0]
            else:
                # Default: use "Unknown" - user should specify
                company_name = "Unknown"
                logger.warning(f"No company_name provided for file {file.filename}, using 'Unknown'")
        
        company_name = str(company_name).strip()
        logger.info(f"Uploading file {file.filename} for company '{company_name}' by user {user_id}")
        
        # Save file
        file_path = str(UPLOAD_DIR / file.filename)
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Process with RAG pipeline - include user_id and company_name in metadata
        rag_pipeline = RAGPipeline(vector_store)
        result = rag_pipeline.ingest_document(
            file_path,
            metadata={
                'user_id': user_id,
                'company_name': company_name,
                'uploaded_by': current_user.get('email', 'unknown')
            }
        )
        
        logger.info(f"✅ Successfully processed {result.get('chunks_processed', 0)} chunks for {company_name}")
        
        return FileUploadResponse(
            file_id=result.get('chunk_ids', [])[0] if result.get('chunk_ids') else "unknown",
            filename=file.filename,
            status="processed",
            chunks_processed=result.get('chunks_processed', 0)
        )
    
    except Exception as e:
        logger.error(f"File upload error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list")
async def list_files():
    """List uploaded files"""
    files = []
    if UPLOAD_DIR.exists():
        for file_path in UPLOAD_DIR.iterdir():
            if file_path.is_file():
                files.append({
                    "filename": file_path.name,
                    "size": file_path.stat().st_size
                })
    
    return {"files": files}

