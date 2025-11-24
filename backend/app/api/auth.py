"""
Authentication API endpoints: registration, login, logout
"""

from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Form
from fastapi.security import HTTPBearer
from pydantic import EmailStr, ValidationError, BaseModel
from typing import Optional
import logging
from datetime import timedelta, datetime
import base64
import os
import secrets
import hashlib
from pathlib import Path

from app.models.schemas import UserRegister, UserLogin, UserResponse, TokenResponse, ForgotPasswordRequest, ResetPasswordRequest, ForgotPasswordResponse
from app.auth.auth_middleware import get_current_user
from app.database import get_database
from app.auth.auth_utils import (
    verify_password,
    get_password_hash,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from bson import ObjectId

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister):
    """Register a new user"""
    try:
        db = get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database connection error"
            )
        
        # Check if user already exists
        existing_user = await db.users.find_one({"email": user_data.email})
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Hash password (validation should have caught length issues, but handle gracefully)
        try:
            # Log password length for debugging (don't log actual password!)
            password_byte_length = len(user_data.password.encode('utf-8'))
            logger.debug(f"Attempting to hash password of {password_byte_length} bytes")
            
            hashed_password = get_password_hash(user_data.password)
        except ValueError as e:
            error_msg = str(e)
            logger.warning(f"Password hashing failed: {error_msg}")
            
            # CRITICAL: Only show "too long" error if password is ACTUALLY > 72 bytes
            # Bcrypt sometimes throws false positive errors about 72 bytes even for short passwords
            if "too long" in error_msg.lower():
                if password_byte_length > 72:
                    # Password is actually too long
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Password is too long. Maximum length is 72 bytes (approximately 72 characters for most text). Please use a shorter password."
                    )
                else:
                    # False positive - password is NOT too long, but error mentioned it
                    # Show generic error without mentioning length
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Password hashing failed. Please try a different password. If the problem persists, contact support."
                    )
            
            # For other errors, show the actual error message
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # Create user document
        user_doc = {
            "name": user_data.name,
            "email": user_data.email,
            "password": hashed_password,
            "created_at": user_data.created_at
        }
        
        # Insert user
        result = await db.users.insert_one(user_doc)
        user_id = result.inserted_id
        
        logger.info(f"User registered: {user_data.email}")
        
        return UserResponse(
            id=str(user_id),
            name=user_data.name,
            email=user_data.email,
            created_at=user_data.created_at
        )
    
    except HTTPException:
        raise
    except ValidationError as e:
        # Pydantic validation errors
        error_messages = []
        for error in e.errors():
            field = error.get('loc', ['unknown'])[-1]
            msg = error.get('msg', 'Validation error')
            error_messages.append(f"{field}: {msg}")
        error_msg = "; ".join(error_messages)
        logger.warning(f"Validation error during registration: {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    except ValueError as e:
        # Custom validation errors (from field_validator or password hashing)
        error_msg = str(e)
        logger.warning(f"Validation error during registration: {error_msg}")
        
        # Provide user-friendly error messages
        if "password" in error_msg.lower() and ("72" in error_msg or "bytes" in error_msg.lower() or "longer" in error_msg.lower()):
            user_message = "Password is too long. Maximum length is 72 bytes (approximately 72 characters for most text). Please use a shorter password."
        elif "password" in error_msg.lower() and ("shorter" in error_msg.lower() or "6" in error_msg or "at least" in error_msg.lower()):
            user_message = "Password must be at least 6 characters long."
        else:
            user_message = error_msg
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=user_message
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Registration error: {error_msg}", exc_info=True)
        
        # Provide user-friendly error messages
        if "password" in error_msg.lower() and ("72" in error_msg or "bytes" in error_msg.lower() or "longer" in error_msg.lower() or "truncate" in error_msg.lower()):
            user_message = "Password is too long. Maximum length is 72 bytes (approximately 72 characters for most text). Please use a shorter password."
        elif "password" in error_msg.lower() and ("shorter" in error_msg.lower() or "6" in error_msg):
            user_message = "Password must be at least 6 characters long."
        elif "email" in error_msg.lower():
            user_message = "Invalid email address. Please check your email format and try again."
        elif "name" in error_msg.lower() and ("length" in error_msg.lower() or "2" in error_msg):
            user_message = "Name must be between 2 and 100 characters long."
        elif "duplicate" in error_msg.lower() or "already exists" in error_msg.lower() or "already registered" in error_msg.lower():
            user_message = "This email is already registered. Please use a different email or try logging in."
        else:
            user_message = f"Registration failed. Please check your input and try again."
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST if "password" in error_msg.lower() or "email" in error_msg.lower() else status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=user_message
        )

@router.post("/login", response_model=TokenResponse)
async def login(user_data: UserLogin):
    """Login and get JWT token"""
    try:
        db = get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database connection error"
            )
        
        # Find user
        user = await db.users.find_one({"email": user_data.email})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Verify password
        if not verify_password(user_data.password, user["password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": str(user["_id"]), "email": user["email"]},
            expires_delta=access_token_expires
        )
        
        logger.info(f"User logged in: {user_data.email}")
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse(
                id=str(user["_id"]),
                name=user["name"],
                email=user["email"],
                created_at=user["created_at"]
            )
        )
    
    except HTTPException:
        raise
    except ValueError as e:
        # Validation errors
        error_msg = str(e)
        logger.warning(f"Validation error during login: {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Login error: {error_msg}", exc_info=True)
        
        # Provide user-friendly error messages
        if "password" in error_msg.lower() and "72" in error_msg:
            user_message = "Password cannot exceed 72 characters. Please contact support if you need to reset your password."
        elif "email" in error_msg.lower():
            user_message = "Invalid email address. Please check your email format."
        else:
            user_message = "Login failed. Please check your email and password, then try again."
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST if "password" in error_msg.lower() or "email" in error_msg.lower() else status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=user_message
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user info"""
    return UserResponse(
        id=current_user["id"],
        name=current_user["name"],
        email=current_user["email"]
    )

@router.get("/profile", response_model=UserResponse)
async def get_profile(current_user: dict = Depends(get_current_user)):
    """Get user profile"""
    try:
        db = get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database connection error"
            )
        
        user = await db.users.find_one({"_id": ObjectId(current_user["id"])})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return UserResponse(
            id=str(user["_id"]),
            name=user.get("name", ""),
            email=user.get("email", ""),
            avatarUrl=user.get("avatarUrl"),
            created_at=user.get("created_at")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting profile: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get profile"
        )

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    oldPassword: Optional[str] = None
    newPassword: Optional[str] = None
    avatarUrl: Optional[str] = None

@router.put("/profile", response_model=UserResponse)
async def update_profile(
    profile_data: ProfileUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update user profile"""
    try:
        db = get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database connection error"
            )
        
        user_id = ObjectId(current_user["id"])
        user = await db.users.find_one({"_id": user_id})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        update_data = {}
        
        # Update name
        if profile_data.name is not None:
            if len(profile_data.name) < 2 or len(profile_data.name) > 100:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Name must be between 2 and 100 characters"
                )
            update_data["name"] = profile_data.name
        
        # Update email
        if profile_data.email is not None:
            # Check if email is already taken by another user
            existing = await db.users.find_one({"email": profile_data.email, "_id": {"$ne": user_id}})
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already in use"
                )
            update_data["email"] = profile_data.email
        
        # Update password
        if profile_data.newPassword:
            if not profile_data.oldPassword:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Current password is required to change password"
                )
            
            # Verify old password
            if not verify_password(profile_data.oldPassword, user["password"]):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect current password"
                )
            
            # Validate new password length
            if len(profile_data.newPassword) < 6:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="New password must be at least 6 characters"
                )
            
            # Hash new password
            update_data["password"] = get_password_hash(profile_data.newPassword)
        
        # Update avatar
        if profile_data.avatarUrl is not None:
            update_data["avatarUrl"] = profile_data.avatarUrl
        
        # Update user
        if update_data:
            await db.users.update_one(
                {"_id": user_id},
                {"$set": update_data}
            )
        
        # Get updated user
        updated_user = await db.users.find_one({"_id": user_id})
        
        return UserResponse(
            id=str(updated_user["_id"]),
            name=updated_user.get("name", ""),
            email=updated_user.get("email", ""),
            avatarUrl=updated_user.get("avatarUrl"),
            created_at=updated_user.get("created_at")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating profile: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )

@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(request: ForgotPasswordRequest):
    """Request password reset - sends reset token to email"""
    try:
        db = get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database connection error"
            )
        
        # Find user
        user = await db.users.find_one({"email": request.email})
        if not user:
            # Don't reveal if email exists for security
            logger.info(f"Password reset requested for non-existent email: {request.email}")
            return ForgotPasswordResponse(
                message="If that email exists, we've sent a password reset link.",
                success=True
            )
        
        # Generate reset token
        reset_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
        
        # Store reset token in database (expires in 1 hour)
        reset_expires = datetime.utcnow() + timedelta(hours=1)
        await db.password_resets.insert_one({
            "user_id": user["_id"],
            "token_hash": token_hash,
            "email": request.email,
            "expires_at": reset_expires,
            "created_at": datetime.utcnow(),
            "used": False
        })
        
        # Send email with reset link using email service
        from app.services.email_service import get_email_service
        email_service = get_email_service()
        
        user_name = user.get("name")
        email_sent = await email_service.send_password_reset_email(
            to_email=request.email,
            reset_token=reset_token,
            user_name=user_name
        )
        
        if not email_sent:
            logger.warning(f"Failed to send password reset email to {request.email}, but token was generated. Check email configuration.")
            # Still return success to prevent email enumeration
        
        logger.info(f"Password reset token generated for {request.email}. Email sent: {email_sent}")
        
        return ForgotPasswordResponse(
            message="If that email exists, we've sent a password reset link.",
            success=True
        )
    
    except Exception as e:
        logger.error(f"Forgot password error: {e}", exc_info=True)
        # Don't reveal errors to prevent email enumeration
        return ForgotPasswordResponse(
            message="If that email exists, we've sent a password reset link.",
            success=True
        )

@router.post("/reset-password", response_model=dict)
async def reset_password(request: ResetPasswordRequest):
    """Reset password using reset token"""
    try:
        db = get_database()
        if db is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database connection error"
            )
        
        # Hash the provided token
        token_hash = hashlib.sha256(request.token.encode()).hexdigest()
        
        # Find reset token
        reset_record = await db.password_resets.find_one({
            "token_hash": token_hash,
            "used": False,
            "expires_at": {"$gt": datetime.utcnow()}
        })
        
        if not reset_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )
        
        # Find user
        user = await db.users.find_one({"_id": reset_record["user_id"]})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Hash new password
        try:
            hashed_password = get_password_hash(request.new_password)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Password error: {str(e)}"
            )
        
        # Update user password
        await db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {"password": hashed_password}}
        )
        
        # Mark reset token as used
        await db.password_resets.update_one(
            {"_id": reset_record["_id"]},
            {"$set": {"used": True, "used_at": datetime.utcnow()}}
        )
        
        logger.info(f"Password reset successful for user: {user['email']}")
        
        return {
            "message": "Password reset successfully",
            "success": True
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reset password error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password. Please try again."
        )

@router.post("/profile/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload user avatar"""
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an image"
            )
        
        # Validate file size (max 5MB)
        contents = await file.read()
        if len(contents) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size must be less than 5MB"
            )
        
        # Create avatars directory
        avatars_dir = Path("uploads/avatars")
        avatars_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        user_id = current_user["id"]
        file_ext = Path(file.filename).suffix if file.filename else ".jpg"
        filename = f"{user_id}{file_ext}"
        file_path = avatars_dir / filename
        
        # Save file
        with open(file_path, "wb") as f:
            f.write(contents)
        
        # Generate URL (in production, use S3/CDN URL)
        avatar_url = f"/uploads/avatars/{filename}"
        
        # Update user in database
        db = get_database()
        if db is not None:
            await db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {"avatarUrl": avatar_url}}
            )
        
        return {"avatarUrl": avatar_url}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading avatar: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload avatar"
        )

