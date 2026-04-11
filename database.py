import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure

logger = logging.getLogger(__name__)

class Database:
    client: AsyncIOMotorClient = None
    db = None

    async def connect_to_storage(self):
        mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
        try:
            self.client = AsyncIOMotorClient(mongodb_url)
            # Check connection
            await self.client.admin.command('ping')
            self.db = self.client.resume_matcher
            logger.info("Connected to MongoDB successfully.")
        except ConnectionFailure:
            logger.error("Could not connect to MongoDB. Using local fallback mode.")
            self.db = None
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            self.db = None

    async def close_storage_connection(self):
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed.")

db = Database()

# Pydantic models for structured data
from pydantic import BaseModel, Field
from typing import List, Optional

class JobSeekerProfile(BaseModel):
    id: str = Field(default_factory=lambda: "user_123")
    name: str
    skills: List[str]
    experience_years: float
    location: str
    preferences: List[str] = []


class EmployerProfile(BaseModel):
    """Employer / hiring organization profile (ingestion separate from job postings)."""
    id: str = Field(default_factory=lambda: "emp_123")
    company_name: str
    contact_email: Optional[str] = None
    industry: Optional[str] = None
    headquarters: Optional[str] = None


class JobRequirement(BaseModel):
    id: str = Field(default_factory=lambda: "job_123")
    title: str
    required_skills: List[str]
    min_experience: float
    location: str
    preferences: List[str] = []
    employer_id: Optional[str] = None
    company_name: Optional[str] = None
