"""
Pydantic schemas for request/response models
"""

from pydantic import BaseModel, Field, EmailStr, field_validator, ValidationError
from typing import Optional, List, Dict, Any
from datetime import datetime

class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str
    agent_thinking: Optional[str] = None
    progress_updates: Optional[List[str]] = None
    questions: Optional[List[str]] = None
    account_plan: Optional[Dict[str, Any]] = None

class VoiceInput(BaseModel):
    audio_data: str  # Base64 encoded audio
    session_id: Optional[str] = None

class VoiceResponse(BaseModel):
    text: str
    audio_url: Optional[str] = None
    session_id: str

class FileUploadResponse(BaseModel):
    file_id: str
    filename: str
    status: str
    chunks_processed: int

class FinancialValue(BaseModel):
    """Financial value with source attribution and confidence"""
    value: str
    source: List[str] = Field(default_factory=list)
    confidence: float = 0.8

class FinancialSummary(BaseModel):
    """Financial summary with source attribution"""
    revenue: Optional[FinancialValue] = None
    profit: Optional[FinancialValue] = None
    employees: Optional[FinancialValue] = None
    market_cap: Optional[FinancialValue] = None

class KeyPerson(BaseModel):
    """Key person with source attribution"""
    name: str
    title: str
    source: str

class Competitor(BaseModel):
    """Competitor with source attribution"""
    name: str
    reason: str
    source: str

class SourceReference(BaseModel):
    """Source reference for account plan sections"""
    url: str
    type: str  # "news", "pdf", "website", "api"
    extracted_at: str  # ISO timestamp

class AccountPlanSection(BaseModel):
    """Account Plan JSON structure matching exact specification"""
    company_name: str
    company_overview: str
    financial_summary: Optional[FinancialSummary] = None
    products_services: str
    key_people: List[KeyPerson] = Field(default_factory=list)
    swot: Dict[str, str] = Field(default_factory=lambda: {
        "strengths": "",
        "weaknesses": "",
        "opportunities": "",
        "threats": ""
    })
    competitors: List[Competitor] = Field(default_factory=list)
    recommended_strategy: str
    sources: List[SourceReference] = Field(default_factory=list)
    last_updated: str  # ISO timestamp

# SourceReference moved above to AccountPlanSection

class AccountPlanEdit(BaseModel):
    """Edit history entry"""
    section: str
    old_content: str
    new_content: str
    edited_by: str  # user_id
    edited_at: datetime
    edit_type: str  # "manual", "regenerated"

class AccountPlan(BaseModel):
    """Complete account plan matching exact specification"""
    company_name: str
    plan_json: AccountPlanSection  # The exact JSON structure
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: str  # user_id
    edits: List[AccountPlanEdit] = Field(default_factory=list)
    research_history_id: Optional[str] = None

class AccountPlanUpdate(BaseModel):
    session_id: str
    section: str  # e.g., "competitor_analysis", "swot.strengths"
    new_content: str
    regenerate: bool = False

class ConflictDetection(BaseModel):
    topic: str
    sources: List[Dict[str, Any]]
    conflicting_values: List[str]
    recommendation: str

class ResearchProgress(BaseModel):
    step: str
    status: str
    message: str
    data_collected: Optional[int] = None
    conflicts_detected: Optional[int] = None

# Authentication Schemas
class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6, max_length=72)

class ForgotPasswordResponse(BaseModel):
    message: str
    success: bool

class UserRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Full name (2-100 characters)")
    email: EmailStr = Field(..., description="Valid email address")
    password: str = Field(
        ..., 
        min_length=6, 
        max_length=72,
        description="Password (6-72 characters). For security, passwords longer than 72 characters are not supported."
    )
    created_at: Optional[datetime] = None
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password length and requirements (bcrypt uses byte length, not character length)"""
        # Strip whitespace (passwords shouldn't have leading/trailing spaces)
        v = v.strip()
        
        # Check character length first (minimum)
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters long")
        
        # Check byte length (bcrypt limit is 72 bytes, not characters)
        password_bytes = v.encode('utf-8')
        byte_length = len(password_bytes)
        
        # Only raise error if actually over 72 bytes
        if byte_length > 72:
            raise ValueError(
                f"Password is too long ({byte_length} bytes). "
                "Maximum length is 72 bytes (approximately 72 characters for most text). "
                "Please use a shorter password."
            )
        
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    avatarUrl: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

# Chat & Message Schemas
class ChatCreate(BaseModel):
    title: Optional[str] = None

class ChatItemResponse(BaseModel):
    id: str
    userId: str
    title: str
    createdAt: datetime
    lastMessageAt: Optional[datetime] = None

class ChatListResponse(BaseModel):
    chats: List[ChatItemResponse]
    total: int
    page: int
    per_page: int
    has_more: bool

class MessageCreate(BaseModel):
    content: str
    attachments: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    role: str = "user"

class MessageResponse(BaseModel):
    id: str
    chatId: str
    userId: str
    role: str
    content: str
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    createdAt: datetime
    tokens: Optional[int] = None

class MessageListResponse(BaseModel):
    messages: List[MessageResponse]
    total: int
    page: int
    per_page: int
    cursor: Optional[str] = None
    has_more: bool

class MemoryResponse(BaseModel):
    summary: str
    keyInsights: List[str] = Field(default_factory=list)
    updatedAt: datetime

# Plan Schemas
class PlanVersion(BaseModel):
    versionId: str
    timestamp: datetime
    userId: str
    changes: Dict[str, Any]
    diff: Optional[Dict[str, Any]] = None

class PlanResponse(BaseModel):
    id: str
    userId: str
    chatId: Optional[str] = None
    companyName: str
    planJSON: Dict[str, Any]
    versions: List[PlanVersion] = Field(default_factory=list)
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    status: str
    createdAt: datetime
    updatedAt: datetime

class SectionUpdate(BaseModel):
    content: str

class SectionRegenerateResponse(BaseModel):
    section: str
    content: str
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float
    versionId: str

# Upload Schemas
class UploadInitResponse(BaseModel):
    uploadId: str
    chunkSize: int

class UploadChunkRequest(BaseModel):
    chunk: str  # Base64 encoded chunk
    chunkIndex: int
    totalChunks: int

class UploadCompleteResponse(BaseModel):
    uploadId: str
    status: str
    fileId: Optional[str] = None
    jobId: Optional[str] = None

# Research Job Schemas
class ResearchJobCreate(BaseModel):
    query: str
    company: Optional[str] = None

class ResearchJobResponse(BaseModel):
    jobId: str
    status: str
    query: str
    company: Optional[str] = None

class ResearchJobStatusResponse(BaseModel):
    jobId: str
    status: str
    logs: List[Dict[str, Any]] = Field(default_factory=list)
    resultsMeta: Optional[Dict[str, Any]] = None

