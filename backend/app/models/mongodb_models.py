"""
MongoDB models using Pydantic for validation
Production-grade models with all required fields
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId

class PyObjectId(ObjectId):
    """Custom ObjectId for Pydantic"""
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")

# User Model - Production Grade
class User(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    name: str
    email: EmailStr
    passwordHash: str = Field(..., alias="password")  # Hashed password (bcrypt)
    avatarUrl: Optional[str] = None
    settings: Dict[str, Any] = Field(default_factory=lambda: {"theme": "light"})
    createdAt: datetime = Field(default_factory=datetime.utcnow, alias="created_at")
    
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

# Chat Model
class Chat(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    userId: PyObjectId = Field(..., alias="user_id")
    title: str
    createdAt: datetime = Field(default_factory=datetime.utcnow, alias="created_at")
    lastMessageAt: Optional[datetime] = Field(default=None, alias="last_message_at")
    
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

# Message Model
class Message(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    chatId: PyObjectId = Field(..., alias="chat_id")
    userId: PyObjectId = Field(..., alias="user_id")
    role: str  # "user" or "assistant"
    content: str
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    createdAt: datetime = Field(default_factory=datetime.utcnow, alias="created_at")
    tokens: Optional[int] = None
    
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

# Account Plan Model - Production Grade with Version History
class AccountPlan(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    userId: PyObjectId = Field(..., alias="user_id")
    chatId: Optional[PyObjectId] = Field(default=None, alias="chat_id")
    companyName: str = Field(..., alias="company_name")
    planJSON: Dict[str, Any] = Field(default_factory=dict, alias="plan_json")
    versions: List[Dict[str, Any]] = Field(default_factory=list)  # Version history
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    status: str = "draft"  # "draft", "published", "archived"
    createdAt: datetime = Field(default_factory=datetime.utcnow, alias="created_at")
    updatedAt: datetime = Field(default_factory=datetime.utcnow, alias="updated_at")
    
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

# Research Job Model
class ResearchJob(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    userId: PyObjectId = Field(..., alias="user_id")
    query: str
    company: Optional[str] = None
    status: str = "pending"  # "pending", "running", "completed", "failed"
    logs: List[Dict[str, Any]] = Field(default_factory=list)
    resultsMeta: Dict[str, Any] = Field(default_factory=dict, alias="results_meta")
    createdAt: datetime = Field(default_factory=datetime.utcnow, alias="created_at")
    updatedAt: datetime = Field(default_factory=datetime.utcnow, alias="updated_at")
    
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

# Research History Model (legacy, kept for compatibility)
class ResearchHistory(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: PyObjectId
    company_name: str
    logs: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

# RAG Chunk Model - Production Grade
class RAGChunk(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    chunkId: Optional[str] = Field(default=None, alias="chunk_id")
    text: str = Field(..., alias="text_chunk")
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)  # {userId, companyName, sourceUrl, confidence, timestamp}
    createdAt: datetime = Field(default_factory=datetime.utcnow, alias="created_at")
    
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

