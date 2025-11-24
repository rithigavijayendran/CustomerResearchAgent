"""
MongoDB database connection and configuration
"""

import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
import logging

logger = logging.getLogger(__name__)

class Database:
    """MongoDB database connection manager"""
    
    client: AsyncIOMotorClient = None
    database = None

db = Database()

async def connect_to_mongo():
    """Create database connection (supports both local MongoDB and MongoDB Atlas)"""
    try:
        # Get connection string from environment
        # For MongoDB Atlas: mongodb+srv://username:password@cluster.mongodb.net/database?retryWrites=true&w=majority
        # For local MongoDB: mongodb://localhost:27017
        mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
        db_name = os.getenv("MONGODB_DB_NAME", "eightfold_research")
        
        # Check if using Atlas (connection string contains mongodb+srv://)
        is_atlas = "mongodb+srv://" in mongo_url or "mongodb.net" in mongo_url
        
        if is_atlas:
            logger.info("Connecting to MongoDB Atlas...")
        else:
            logger.info(f"Connecting to local MongoDB at {mongo_url}...")
        
        # Create client with appropriate timeout
        # Atlas connections may need longer timeout
        timeout = 10000 if is_atlas else 5000
        
        db.client = AsyncIOMotorClient(
            mongo_url,
            serverSelectionTimeoutMS=timeout,
            tlsAllowInvalidCertificates=False  # Set to True only for testing with self-signed certs
        )
        
        # Test connection
        await db.client.admin.command('ping')
        db.database = db.client[db_name]
        
        if is_atlas:
            logger.info(f"✅ Connected to MongoDB Atlas database: {db_name}")
        else:
            logger.info(f"✅ Connected to MongoDB database: {db_name}")
        return True
    except ConnectionFailure as e:
        logger.error(f"❌ Failed to connect to MongoDB: {e}")
        if "mongodb+srv://" in os.getenv("MONGODB_URL", ""):
            logger.error("Please check your MongoDB Atlas connection string in .env")
            logger.error("Format: mongodb+srv://username:password@cluster.mongodb.net/database?retryWrites=true&w=majority")
        else:
            logger.error("Please ensure MongoDB is running and MONGODB_URL is correct in .env")
        return False
    except Exception as e:
        logger.error(f"❌ MongoDB connection error: {e}")
        if "authentication" in str(e).lower():
            logger.error("Authentication failed. Please check your MongoDB Atlas username and password.")
        elif "network" in str(e).lower() or "timeout" in str(e).lower():
            logger.error("Network error. Please check your internet connection and MongoDB Atlas IP whitelist.")
        return False

async def close_mongo_connection():
    """Close database connection"""
    if db.client:
        db.client.close()
        logger.info("MongoDB connection closed")

def get_database():
    """Get database instance"""
    return db.database

