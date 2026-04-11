import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from matching_engine import calculate_advanced_score
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_matching_demo():
    print("\n🧪 2. SAMPLE MATCH RECOMMENDATION DEMO VERIFICATION")
    
    # Candidate from requirements
    candidate = {
        "skills": ["Python", "ML", "SQL"],
        "experience_years": 2,
        "location": "Hyderabad",
        "preferences": []
    }
    
    # Jobs from requirements
    jobs = [
        {
            "title": "Data Scientist",
            "required_skills": ["Python", "ML", "SQL"],
            "min_experience": 2,
            "location": "Hyderabad",
            "preferences": []
        },
        {
            "title": "ML Engineer",
            "required_skills": ["Python", "ML"],
            "min_experience": 4, # Experience mismatch
            "location": "Bangalore", # Location mismatch
            "preferences": []
        },
        {
            "title": "Backend Developer",
            "required_skills": ["Java", "Spring"], # Skill mismatch
            "min_experience": 1,
            "location": "Remote",
            "preferences": []
        }
    ]
    
    for job in jobs:
        score = calculate_advanced_score(candidate, job)
        print(f"Job: {job['title']} | Score: {score}%")

if __name__ == "__main__":
    test_matching_demo()
