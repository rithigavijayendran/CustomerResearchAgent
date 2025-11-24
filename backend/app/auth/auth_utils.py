"""
Authentication utilities: JWT, password hashing, token management
"""

import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import logging
import bcrypt

logger = logging.getLogger(__name__)

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash using bcrypt directly"""
    try:
        # Use bcrypt directly - bypasses passlib completely
        return bcrypt.checkpw(
            plain_password.encode('utf-8'), 
            hashed_password.encode('utf-8')
        )
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False

def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt directly (bypasses passlib to avoid compatibility issues)"""
    # Strip any whitespace
    password = password.strip()
    
    # Bcrypt has a 72-byte limit - check before hashing
    password_bytes = password.encode('utf-8')
    byte_length = len(password_bytes)
    
    # Log for debugging
    logger.debug(f"Hashing password of {byte_length} bytes")
    
    # Only raise length error if password is ACTUALLY > 72 bytes
    if byte_length > 72:
        logger.error(f"Password validation failed: {byte_length} bytes (should have been caught by validator)")
        raise ValueError(
            f"Password exceeds 72 bytes (current: {byte_length} bytes). "
            "Maximum length is 72 bytes. Please use a shorter password."
        )
    
    # Hash using bcrypt directly - completely bypasses passlib
    try:
        # Generate salt and hash
        salt = bcrypt.gensalt(rounds=12)
        hashed_bytes = bcrypt.hashpw(password_bytes, salt)
        hashed_str = hashed_bytes.decode('utf-8')
        
        logger.debug(f"Password hashed successfully")
        return hashed_str
        
    except ValueError as ve:
        # Re-raise ValueError as-is (these are our validation errors)
        raise
    except Exception as e:
        # Catch any unexpected errors
        error_msg = str(e)
        error_type = type(e).__name__
        logger.error(f"Error hashing password: {error_type}: {error_msg}, password length: {byte_length} bytes")
        
        # For passwords <= 72 bytes, this is NOT a length issue
        if byte_length <= 72:
            raise ValueError(
                "Password hashing failed due to a technical issue. "
                "Please try a different password or contact support if the problem persists."
            )
        
        # Password is actually too long
        raise ValueError(
            f"Password is too long ({byte_length} bytes). "
            "Maximum length is 72 bytes (approximately 72 characters for most text). "
            "Please use a shorter password."
        )

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning(f"JWT decode error: {e}")
        return None

def verify_token(token: str) -> Optional[dict]:
    """Verify a JWT token (alias for decode_access_token for consistency)"""
    return decode_access_token(token)