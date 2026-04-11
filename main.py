import os
import uuid
import logging
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from database import db, JobSeekerProfile, JobRequirement, EmployerProfile
from resume_processor import process_resume, process_jd
from matching_engine import multi_criteria_breakdown, rank_jobs_by_skill_embedding

from contextlib import asynccontextmanager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Connect to DB
    await db.connect_to_storage()
    yield
    # Shutdown: Close connection
    await db.close_storage_connection()

app = FastAPI(
    title="CV Embed: AI-Powered Job Matching Engine",
    lifespan=lifespan
)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API ENDPOINTS ---


def _payload(model):
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


@app.post("/employer", response_model=EmployerProfile)
async def create_employer(
    company_name: str = Form(...),
    contact_email: Optional[str] = Form(None),
    industry: Optional[str] = Form(None),
    headquarters: Optional[str] = Form(None),
):
    """
    Employer profile ingestion: register a hiring organization before (or while) posting roles.
    """
    try:
        profile = EmployerProfile(
            id=str(uuid.uuid4()),
            company_name=company_name.strip(),
            contact_email=(contact_email or "").strip() or None,
            industry=(industry or "").strip() or None,
            headquarters=(headquarters or "").strip() or None,
        )
        if db.db:
            await db.db.employers.insert_one(_payload(profile))
        return profile
    except Exception as e:
        logger.error(f"Error creating employer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/jobseeker", response_model=JobSeekerProfile)
async def create_jobseeker(
    name: str = Form(...),
    resume_file: UploadFile = File(...)
):
    """
    Registers a candidate by parsing their resume.
    (Workflow Step 2: Resume Parsing)
    """
    try:
        # Save temp file
        temp_path = f"temp_resume_{uuid.uuid4().hex}.pdf"
        with open(temp_path, "wb") as buffer:
            buffer.write(await resume_file.read())
            
        # Process and extract
        processed = process_resume(temp_path)
        os.remove(temp_path)
        
        entities = processed.get("entities") or {}
        
        profile = JobSeekerProfile(
            id=str(uuid.uuid4()),
            name=name,
            skills=entities.get("skills", ["General Tech"]),
            experience_years=float(entities.get("experience_years", 0.0)),
            location=entities.get("location", "Remote"),
            preferences=entities.get("preferences", ["Flexible"]),
        )
        
        # Store in DB if available
        if db.db:
            await db.db.candidates.insert_one(_payload(profile))
            
        return profile
    except Exception as e:
        logger.error(f"Error creating jobseeker: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/job", response_model=JobRequirement)
async def create_job(
    title: str = Form(...),
    jd_file: UploadFile = File(...),
    employer_id: Optional[str] = Form(None),
    company_name: Optional[str] = Form(None),
):
    """
    Employer-side job ingestion: decompose JD into structured requirements and optionally link an employer profile.
    """
    try:
        temp_path = f"temp_jd_{uuid.uuid4().hex}.pdf"
        with open(temp_path, "wb") as buffer:
            buffer.write(await jd_file.read())
            
        processed = process_jd(temp_path)
        os.remove(temp_path)

        emp_id = (employer_id or "").strip() or None
        co_name = (company_name or "").strip() or None
        if db.db and emp_id:
            emp = await db.db.employers.find_one({"id": emp_id})
            if not emp:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown employer_id: {emp_id}. POST /employer first.",
                )
            if not co_name and emp.get("company_name"):
                co_name = emp["company_name"]
        
        job = JobRequirement(
            id=str(uuid.uuid4()),
            title=title,
            required_skills=processed.get("required_skills", ["General Tech"]),
            min_experience=float(processed.get("min_experience", 0.0)),
            location=processed.get("location", "Remote"),
            preferences=processed.get("preferences", ["Flexible"]),
            employer_id=emp_id,
            company_name=co_name,
        )
        
        if db.db:
            await db.db.jobs.insert_one(_payload(job))
            
        return job
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def _job_title(job: dict) -> str:
    return job.get("title") or "Untitled role"


@app.get("/match/{candidate_id}")
async def get_matches(candidate_id: str):
    """
    Ranked recommendations: multi-criteria composite score plus skill-embedding signal and per-criterion breakdown.
    """
    try:
        candidate_data = None
        if db.db:
            candidate_data = await db.db.candidates.find_one({"id": candidate_id})
        
        if not candidate_data:
            candidate_data = {
                "skills": ["Python", "ML", "SQL"],
                "experience_years": 2.0,
                "location": "Hyderabad",
                "preferences": ["Remote"],
            }
            
        jobs = []
        if db.db:
            cursor = db.db.jobs.find()
            async for document in cursor:
                jobs.append(document)
        
        if not jobs:
            jobs = [
                {
                    "title": "Data Scientist",
                    "required_skills": ["Python", "ML", "SQL"],
                    "min_experience": 2,
                    "location": "Hyderabad",
                    "preferences": [],
                    "company_name": "Demo Corp",
                },
                {
                    "title": "ML Engineer",
                    "required_skills": ["Python", "ML"],
                    "min_experience": 4,
                    "location": "Bangalore",
                    "preferences": [],
                },
                {
                    "title": "Backend Developer",
                    "required_skills": ["Java", "Spring"],
                    "min_experience": 1,
                    "location": "Remote",
                    "preferences": [],
                },
            ]
            
        recommendations = []
        for job in jobs:
            breakdown = multi_criteria_breakdown(candidate_data, job)
            score = breakdown["final_composite_pct"]
            skill_pct = breakdown["skill_embedding_similarity_pct"]
            recommendations.append({
                "rank": 0,
                "job_title": _job_title(job),
                "job": _job_title(job),
                "company_name": job.get("company_name"),
                "job_id": job.get("id"),
                "composite_score": score,
                "score": score,
                "compatibility": f"{score}%",
                "skill_embedding_similarity_pct": skill_pct,
                "criteria_breakdown": {
                    "skill_embedding_similarity_pct": skill_pct,
                    "experience_alignment_pct": breakdown["experience_alignment_pct"],
                    "location_match_pct": breakdown["location_match_pct"],
                    "preferences_alignment_pct": breakdown["preferences_alignment_pct"],
                    "weights": breakdown["weights"],
                },
                "match_status": (
                    "Highly Recommended"
                    if score > 85
                    else "Recommended"
                    if score > 60
                    else "Low Match"
                ),
            })
            
        recommendations.sort(key=lambda x: x["composite_score"], reverse=True)
        for i, rec in enumerate(recommendations, start=1):
            rec["rank"] = i
        
        return {
            "candidate_id": candidate_id,
            "scoring_method": "multi_criteria_weighted",
            "recommendations": recommendations,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting matches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/match/{candidate_id}/skill-similarity")
async def get_matches_by_skill_embedding_only(candidate_id: str, top_n: int = 20):
    """
    Skill-based embedding similarity search: rank jobs using only vector similarity of skill sets (no experience/location weights).
    """
    try:
        candidate_data = None
        if db.db:
            candidate_data = await db.db.candidates.find_one({"id": candidate_id})
        if not candidate_data:
            candidate_data = {
                "skills": ["Python", "ML", "SQL"],
                "experience_years": 2.0,
                "location": "Hyderabad",
                "preferences": ["Remote"],
            }

        jobs = []
        if db.db:
            cursor = db.db.jobs.find()
            async for document in cursor:
                jobs.append(document)
        if not jobs:
            jobs = [
                {
                    "title": "Data Scientist",
                    "required_skills": ["Python", "ML", "SQL"],
                    "min_experience": 2,
                    "location": "Hyderabad",
                    "preferences": [],
                },
                {
                    "title": "ML Engineer",
                    "required_skills": ["Python", "ML"],
                    "min_experience": 4,
                    "location": "Bangalore",
                    "preferences": [],
                },
            ]

        ranked = rank_jobs_by_skill_embedding(
            candidate_data, jobs, top_n=top_n if top_n > 0 else None
        )
        out = []
        for rank, (job, sim_pct) in enumerate(ranked, start=1):
            out.append({
                "rank": rank,
                "job_title": _job_title(job),
                "company_name": job.get("company_name"),
                "job_id": job.get("id"),
                "skill_embedding_similarity_pct": sim_pct,
            })
        return {
            "candidate_id": candidate_id,
            "method": "skill_embedding_similarity_only",
            "results": out,
        }
    except Exception as e:
        logger.error(f"Error in skill similarity search: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
