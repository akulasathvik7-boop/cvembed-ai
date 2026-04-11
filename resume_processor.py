import re
import os
import logging
from PyPDF2 import PdfReader
from docx import Document
from utils.text_processing import clean_text

logger = logging.getLogger(__name__)

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        logger.info(f"Extracting text from PDF: {pdf_path}")
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file)
            num_pages = len(reader.pages)
            logger.info(f"PDF has {num_pages} pages.")
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        logger.info(f"Successfully extracted {len(text)} characters from PDF.")
    except Exception as e:
        logger.error(f"Error processing PDF {pdf_path}: {e}", exc_info=True)
    return text

def extract_text_from_docx(docx_path):
    text = ""
    try:
        logger.info(f"Extracting text from DOCX: {docx_path}")
        doc = Document(docx_path)
        for para in doc.paragraphs:
            if para.text.strip():
                text += para.text + "\n"
        logger.info(f"Successfully extracted {len(text)} characters from DOCX.")
    except Exception as e:
        logger.error(f"Error processing DOCX {docx_path}: {e}", exc_info=True)
    return text

def extract_entities(text):
    """
    Heuristic-based entity extraction for Skills, Experience, and Location.
    (Step 2 & 3 of the workflow)
    """
    # 1. Extract Experience
    exp_pattern = r'(\d+\.?\d*)\s*(years?|yrs?|yr)\b'
    exp_matches = re.findall(exp_pattern, text.lower())
    experience = float(exp_matches[0][0]) if exp_matches else 0.0
    
    # 2. Extract Location
    # Look for common patterns: "Location: City" or "Hyderabad, India"
    location_pattern = r'(?:Location|Living in|Based in):\s*([A-Za-z\s,]+)'
    location_match = re.search(location_pattern, text)
    location = location_match.group(1).strip() if location_match else "Remote"
    
    # 3. Extract Skills (Keyword matching from text)
    # This uses the taxonomies from app.py or common tech keywords
    TECHNICAL_SKILLS = ["python", "java", "javascript", "react", "node", "sql", "mongodb", "aws", "docker", "kubernetes", "ml", "machine learning", "data science"]
    found_skills = []
    for skill in TECHNICAL_SKILLS:
        if re.search(rf'\b{re.escape(skill)}\b', text.lower()):
            found_skills.append(skill.title())
            
    return {
        "skills": found_skills if found_skills else ["General Tech"],
        "experience_years": experience,
        "location": location,
        "preferences": ["Flexible"] # Default preference
    }

def process_resume(file_path):
    logger.info(f"Processing resume file: {file_path}")
    text = ""
    try:
        if file_path.endswith('.pdf'):
            text = extract_text_from_pdf(file_path)
        elif file_path.endswith('.docx'):
            text = extract_text_from_docx(file_path)
        else:
            logger.info("Processing as plain text file.")
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                text = file.read()
        
        cleaned_text = clean_text(text)
        entities = extract_entities(text) # Extract from raw text for better regex matches
        
        return {
            "text": cleaned_text,
            "entities": entities
        }
    except Exception as e:
        logger.error(f"General error in process_resume for {file_path}: {e}", exc_info=True)
        return {
            "text": "",
            "entities": {
                "skills": ["General Tech"],
                "experience_years": 0.0,
                "location": "Remote",
                "preferences": ["Flexible"],
            },
        }

def process_jd(file_path):
    result = process_resume(file_path)
    entities = result.get("entities") or {}
    return {
        "title": "Extracted Role",
        "required_skills": entities.get("skills", ["General Tech"]),
        "min_experience": float(entities.get("experience_years", 0.0)),
        "location": entities.get("location", "Remote"),
        "preferences": entities.get("preferences", ["Flexible"]),
        "text": result.get("text", ""),
    }
