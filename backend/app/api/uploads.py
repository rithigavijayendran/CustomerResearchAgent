"""
Chunked Upload API endpoints
POST /api/uploads/init, POST /api/uploads/:uploadId/chunk, POST /api/uploads/:uploadId/complete
"""

from fastapi import APIRouter, HTTPException, Depends, Path, UploadFile, File, Request, Query, Body
from typing import Optional
from pydantic import BaseModel
import os
import uuid
import base64
import logging
import re
from datetime import datetime
from pathlib import Path as PathLib

from app.models.schemas import UploadInitResponse, UploadChunkRequest, UploadCompleteResponse
from app.auth.auth_middleware import get_current_user
from app.database import get_database
from app.rag.document_processor import DocumentProcessor
from app.rag.vector_store import VectorStore
from app.rag.rag_pipeline import RAGPipeline
from app.config import VECTOR_DB_PATH, UPLOAD_DIR

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory storage for uploads (in production, use Redis)
upload_sessions = {}

class CompleteUploadRequest(BaseModel):
    companyName: Optional[str] = None
    chatId: Optional[str] = None
    companyName: Optional[str] = None
    chatId: Optional[str] = None

@router.post("/init", response_model=UploadInitResponse)
async def init_upload(
    request: Request,
    current_user: dict = Depends(get_current_user),
    company_name: Optional[str] = Query(None),
    chat_id: Optional[str] = Query(None)
):
    """Initialize a chunked upload session"""
    try:
        upload_id = str(uuid.uuid4())
        chunk_size = 5 * 1024 * 1024  # 5MB chunks
        
        upload_sessions[upload_id] = {
            "userId": current_user["id"],
            "chunks": {},
            "totalChunks": 0,
            "chunkSize": chunk_size,
            "createdAt": datetime.utcnow(),
            "filename": None,
            "fileType": None,
            "company_name": company_name,  # Store company name for later processing
            "chat_id": chat_id  # Store chat_id to link document to chat
        }
        
        logger.info(f"Initialized upload session {upload_id} for company: {company_name}, chat: {chat_id}")
        
        return UploadInitResponse(
            uploadId=upload_id,
            chunkSize=chunk_size
        )
    except Exception as e:
        logger.error(f"Error initializing upload: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to initialize upload")

@router.post("/{upload_id}/chunk")
async def upload_chunk(
    upload_id: str = Path(..., description="Upload ID"),
    chunk_index: int = 0,
    total_chunks: int = 1,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload a chunk of a file"""
    try:
        # Verify upload session
        if upload_id not in upload_sessions:
            raise HTTPException(status_code=404, detail="Upload session not found")
        
        session = upload_sessions[upload_id]
        if session["userId"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        # Read chunk data
        chunk_data = await file.read()
        
        # Store chunk
        session["chunks"][chunk_index] = chunk_data
        session["totalChunks"] = total_chunks
        
        # Store filename and type from first chunk
        if chunk_index == 0:
            session["filename"] = file.filename
            session["fileType"] = file.content_type
        
        return {
            "uploadId": upload_id,
            "chunkIndex": chunk_index,
            "received": len(chunk_data),
            "totalChunks": total_chunks
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading chunk: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to upload chunk")

@router.post("/{upload_id}/complete", response_model=UploadCompleteResponse)
async def complete_upload(
    upload_id: str = Path(..., description="Upload ID"),
    request_body: Optional[CompleteUploadRequest] = Body(None),
    current_user: dict = Depends(get_current_user),
    request: Request = None
):
    """Complete upload and process document with RAG pipeline"""
    try:
        # Verify upload session
        if upload_id not in upload_sessions:
            raise HTTPException(status_code=404, detail="Upload session not found")
        
        session = upload_sessions[upload_id]
        if session["userId"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        # Reassemble file from chunks
        chunks = session["chunks"]
        total_chunks = session["totalChunks"]
        
        # Verify all chunks received
        if len(chunks) != total_chunks:
            raise HTTPException(
                status_code=400,
                detail=f"Missing chunks. Received {len(chunks)}/{total_chunks}"
            )
        
        # Combine chunks in order
        file_data = b""
        for i in range(total_chunks):
            if i not in chunks:
                raise HTTPException(status_code=400, detail=f"Missing chunk {i}")
            file_data += chunks[i]
        
        # Save file to uploads directory
        UPLOAD_DIR.mkdir(exist_ok=True)
        filename = session["filename"] or f"upload_{upload_id}"
        file_path = UPLOAD_DIR / filename
        
        with open(file_path, "wb") as f:
            f.write(file_data)
        
        logger.info(f"File saved: {file_path}, size: {len(file_data)} bytes")
        
        # Get company_name - priority: request body > session > filename extraction
        company_name = None
        if request_body and request_body.companyName:
            company_name = request_body.companyName
        elif session.get("company_name"):
            company_name = session.get("company_name")
        
        if not company_name or company_name.strip() == "":
            # Try to extract from filename
            filename_base = PathLib(filename).stem  # Remove extension, e.g., "Microsoft (2)" from "Microsoft (2).pdf"
            
            # Remove common patterns: (1), (2), - Copy, etc.
            # Remove parentheses and numbers inside them: "Microsoft (2)" -> "Microsoft"
            filename_base = re.sub(r'\s*\([^)]*\)\s*', '', filename_base)
            # Remove " - Copy", " - Copy (1)", etc.
            filename_base = re.sub(r'\s*-\s*Copy.*$', '', filename_base, flags=re.IGNORECASE)
            # Remove leading/trailing spaces and common separators
            filename_base = filename_base.strip()
            
            # Extract company name based on separators
            if '_' in filename_base:
                # "Company_Name_Info" -> "Company"
                company_name = filename_base.split('_')[0]
            elif '-' in filename_base:
                # "Company-Name-Info" -> "Company"
                company_name = filename_base.split('-')[0]
            elif ' ' in filename_base:
                # "Company Name Info" -> "Company Name" (take first two words if multiple, otherwise first word)
                parts = filename_base.split()
                if len(parts) > 1:
                    # Take first two words for compound names like "Microsoft Corporation"
                    company_name = ' '.join(parts[:2]) if len(parts) >= 2 else parts[0]
                else:
                    company_name = parts[0]
            else:
                # Single word or no separators: use the whole name
                company_name = filename_base if filename_base else "Unknown"
            
            # Clean up: remove any remaining special characters at the end
            company_name = re.sub(r'[^\w\s-]+$', '', company_name).strip()
            
            if not company_name or company_name == "":
                company_name = "Unknown"
                logger.warning(f"Could not extract company_name from filename '{filename}', using 'Unknown'")
            else:
                logger.info(f"Extracted company_name '{company_name}' from filename '{filename}'")
        
        company_name = str(company_name).strip()
        
        # Get chat_id - priority: request body > session
        chat_id = None
        if request_body and request_body.chatId:
            chat_id = request_body.chatId
        elif session.get("chat_id"):
            chat_id = session.get("chat_id")
        
        # Update session with final values
        if company_name and company_name != "Unknown":
            session["company_name"] = company_name
        if chat_id:
            session["chat_id"] = chat_id
        
        logger.info(f"Processing upload with company_name: {company_name}, chat_id: {chat_id}")
        
        # Process file with RAG pipeline immediately
        vector_store = request.state.vector_store if request else None
        if not vector_store:
            logger.warning("Vector store not available - file saved but not processed")
        else:
            try:
                rag_pipeline = RAGPipeline(vector_store)
                # Ensure user_id is stored as string for consistent filtering
                user_id_str = str(current_user["id"])
                result = rag_pipeline.ingest_document(
                    str(file_path),
                    metadata={
                        'user_id': user_id_str,  # Store as string for consistent filtering
                        'company_name': company_name,
                        'uploaded_by': current_user.get('email', 'unknown'),
                        'chat_id': str(chat_id) if chat_id else None,  # Link to chat if provided
                        'source_type': 'uploaded_document'
                    }
                )
                logger.info(f"✅ Successfully processed {result.get('chunks_processed', 0)} chunks for {company_name}")
            except Exception as e:
                logger.error(f"Error processing document with RAG: {e}", exc_info=True)
                # Don't fail the upload, just log the error
        
        # Store job info
        job_id = str(uuid.uuid4())
        db = get_database()
        if db is not None:
            from bson import ObjectId
            job_doc = {
                "userId": ObjectId(current_user["id"]),
                "type": "ingestion",
                "uploadId": upload_id,
                "filePath": str(file_path),
                "filename": filename,
                "company_name": company_name,
                "chat_id": chat_id,
                "status": "completed",
                "createdAt": datetime.utcnow()
            }
            await db.research_jobs.insert_one(job_doc)
            job_id = str(job_doc["_id"])
        
        # Clean up session
        del upload_sessions[upload_id]
        
        return UploadCompleteResponse(
            uploadId=upload_id,
            status="completed",
            fileId=str(file_path),
            jobId=job_id
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing upload: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to complete upload")

