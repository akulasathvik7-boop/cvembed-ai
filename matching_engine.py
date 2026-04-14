import joblib
import os
import logging
import numpy as np
import re
from difflib import SequenceMatcher
from sklearn.metrics.pairwise import cosine_similarity
from config import MODEL_CONFIG
from utils.text_processing import tokenize_text


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Job embeddings cache
JOB_EMBEDDINGS = {}

# Lazy model loading
_LOADED_MODELS = {}


def _simple_tokens(text: str):
    """Tokenizer fallback that does not depend on external NLTK resources."""
    if not isinstance(text, str):
        return set()
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9\+\#\.\-]{1,}", text.lower())
    return {w for w in words if len(w) > 2}


def _fallback_similarity_score(resume_text: str, jd_text: str) -> float:
    """
    Robust lexical fallback (0–100) when embedding models fail or return zero.
    Combines Jaccard overlap and directional containment.
    """
    resume_text = (resume_text or "").strip()
    jd_text = (jd_text or "").strip()
    if not resume_text or not jd_text:
        return 0.0

    a = _simple_tokens(resume_text)
    b = _simple_tokens(jd_text)
    if not a or not b:
        # Character-level safety net when tokenization is sparse/noisy.
        ratio = SequenceMatcher(None, resume_text.lower(), jd_text.lower()).ratio()
        return round(max(5.0, min(100.0, ratio * 100.0)), 2)

    inter = len(a & b)
    union = len(a | b)
    jaccard = inter / max(1, union)
    containment = inter / max(1, len(b))  # how much JD vocabulary is covered by resume
    score = (0.4 * jaccard) + (0.6 * containment)
    pct = score * 100.0
    # Avoid misleading hard-zero for valid non-empty text pairs.
    if pct <= 0.01:
        ratio = SequenceMatcher(None, resume_text.lower(), jd_text.lower()).ratio()
        pct = max(5.0, ratio * 100.0)
    return round(max(0.0, min(100.0, pct)), 2)

def get_model(model_type):
    """Lazy load model on demand"""
    if model_type not in _LOADED_MODELS:
        logger.info(f"Lazy loading {model_type} model...")
        try:
            if model_type == "sbert":
                from model.inference import sbert_inference
                _LOADED_MODELS[model_type] = sbert_inference.load_model(MODEL_CONFIG['sbert_path'])
            elif model_type == "glove":
                from model.inference import glove_inference
                _LOADED_MODELS[model_type] = glove_inference.load_model(MODEL_CONFIG['glove_path'])
            elif model_type == "doc2vec":
                from model.inference import doc2vec_inference
                _LOADED_MODELS[model_type] = doc2vec_inference.load_model(MODEL_CONFIG['doc2vec_path'])
        except Exception as e:
            logger.error(f"Failed to lazy load {model_type}: {e}", exc_info=True)
            _LOADED_MODELS[model_type] = None
            
    return _LOADED_MODELS.get(model_type)



def get_model_embedding(model_type, text):
    """Get embedding based on model type"""
    model = get_model(model_type)
    if model is None:
        return None
    
    try:
        if model_type == "sbert":
            return model.encode([text])[0]
        elif model_type == "glove":
            from model.inference import glove_inference
            tokens = tokenize_text(text)
            return glove_inference.average_embeddings(model, tokens)
        elif model_type == "doc2vec":
            from model.inference import doc2vec_inference
            # CORRECTED: Changed 'steps' to 'epochs'

            return doc2vec_inference.infer_vector(
                model, 
                text,
                epochs=50,  # Fixed parameter name
                alpha=0.025
            )
    except Exception as e:
        logger.error(f"Error getting embedding for {model_type}: {e}")
        return None


def calculate_similarity(resume_text, jd_text, model_type=None):
    """Calculate similarity between resume and JD"""
    if not model_type:
        model_type = MODEL_CONFIG['active_model']
    
    model = get_model(model_type)
    if model is None:
        logger.error(f"Model {model_type} not available, using lexical fallback.")
        return _fallback_similarity_score(resume_text, jd_text)
    
    try:
        score = 0.0
        if model_type == "sbert":
            from model.inference import sbert_inference
            score = sbert_inference.calculate_similarity(model, resume_text, jd_text)
        elif model_type == "glove":
            from model.inference import glove_inference
            score = glove_inference.calculate_text_similarity(model, resume_text, jd_text)
        elif model_type == "doc2vec":
            from model.inference import doc2vec_inference
            # Use the improved Doc2Vec similarity function
            score = doc2vec_inference.calculate_similarity(model, resume_text, jd_text)

        else:
            logger.error(f"Unknown model type: {model_type}")
            score = 0.0

        # Prevent false-zero outcomes for real text.
        if (not score or float(score) <= 0.01) and (resume_text or "").strip() and (jd_text or "").strip():
            fallback = _fallback_similarity_score(resume_text, jd_text)
            logger.info(f"Embedding score near zero; using fallback similarity: {fallback}")
            return fallback
        return round(float(score), 2)
    except Exception as e:
        logger.error(f"Similarity calculation error: {e}. Using fallback.", exc_info=True)
        return _fallback_similarity_score(resume_text, jd_text)

    
def get_top_job_matches(resume_text, model_type=None, top_n=5):
    """Get top job matches for resume"""
    if not model_type:
        model_type = MODEL_CONFIG['active_model']
    
    model = get_model(model_type)
    if model is None:
        logger.error(f"Model {model_type} not available")
        return []
    
    try:
        # Generate resume embedding
        resume_embedding = get_model_embedding(model_type, resume_text)
        if resume_embedding is None:
            return []
        
        # Get job embeddings (cached)
        if model_type not in JOB_EMBEDDINGS:
            if model_type == "sbert":
                from model.inference import sbert_inference
                JOB_EMBEDDINGS[model_type] = sbert_inference.get_job_embeddings(
                    model, MODEL_CONFIG['job_taxonomy'])
            elif model_type == "glove":
                from model.inference import glove_inference
                JOB_EMBEDDINGS[model_type] = glove_inference.get_job_embeddings(
                    model, MODEL_CONFIG['job_taxonomy'])
            elif model_type == "doc2vec":
                from model.inference import doc2vec_inference
                JOB_EMBEDDINGS[model_type] = doc2vec_inference.get_job_embeddings(
                    model, MODEL_CONFIG['job_taxonomy'])


        
        # Calculate similarities
        similarities = cosine_similarity([resume_embedding], JOB_EMBEDDINGS[model_type])[0]
        
        # Get top matches
        top_indices = np.argsort(similarities)[-top_n:][::-1]
        return [(MODEL_CONFIG['job_taxonomy'][i], round(similarities[i] * 100, 2)) 
                for i in top_indices]

    
    except Exception as e:
        logger.error(f"Top job matches error: {e}")
        return []


def skill_embedding_similarity(
    candidate_skills: list,
    required_skills: list,
    model_type=None,
) -> float:
    """
    Skill-based embedding similarity: embeds concatenated skill phrases and returns 0–100
    cosine-style match using the active sentence/vector model (GloVe / SBERT / Doc2Vec).
    """
    a = ", ".join(candidate_skills or [])
    b = ", ".join(required_skills or [])
    if not a.strip() or not b.strip():
        return 0.0
    raw = float(calculate_similarity(a, b, model_type=model_type))
    # Inference layers return 0–100; guard if a raw cosine 0–1 ever appears
    return raw if raw > 1.0 else (raw * 100.0)


def rank_jobs_by_skill_embedding(candidate: dict, jobs: list, model_type=None, top_n=None):
    """
    Rank job dicts by skill embedding similarity only (search / pre-filter use case).
    Returns list of (job_dict, skill_similarity_pct) sorted best-first.
    """
    c_skills = candidate.get("skills") or []
    scored = []
    for job in jobs:
        pct = skill_embedding_similarity(
            c_skills, job.get("required_skills") or [], model_type=model_type
        )
        scored.append((job, round(pct, 2)))
    scored.sort(key=lambda x: x[1], reverse=True)
    if top_n is not None:
        scored = scored[:top_n]
    return scored


def compute_multi_criteria_components(candidate: dict, job: dict, model_type=None):
    """
    Multi-criteria match scoring (all sub-scores normalized to 0–1 internally).

    Final (display %) = 100 * (
        0.4 * skill_embedding + 0.2 * experience + 0.2 * location + 0.2 * preferences
    )
    """
    c_skills = candidate.get("skills") or []
    j_skills = job.get("required_skills") or []

    raw_skill = float(
        calculate_similarity(", ".join(c_skills), ", ".join(j_skills), model_type=model_type)
    )
    skill_score = raw_skill / 100.0 if raw_skill > 1.0 else raw_skill

    cand_exp = float(candidate.get("experience_years", 0) or 0)
    min_exp = float(job.get("min_experience", 0.1) or 0.1)
    exp_score = min(1.0, cand_exp / max(0.1, min_exp))

    cl = str(candidate.get("location") or "").lower()
    jl = str(job.get("location") or "").lower()
    location_score = 1.0 if cl and jl and (cl in jl or jl in cl) else 0.0

    if job.get("preferences"):
        pref_match_count = 0
        for pref in job["preferences"]:
            if any(pref.lower() in skill.lower() for skill in c_skills):
                pref_match_count += 1
        pref_score = pref_match_count / max(1, len(job["preferences"]))
    else:
        pref_score = 1.0

    final_01 = (
        0.4 * skill_score
        + 0.2 * exp_score
        + 0.2 * location_score
        + 0.2 * pref_score
    )
    final_pct = round(final_01 * 100, 2)

    return {
        "skill_embedding_0_1": round(skill_score, 4),
        "skill_embedding_similarity_pct": round(skill_score * 100, 2),
        "experience_0_1": round(exp_score, 4),
        "experience_alignment_pct": round(exp_score * 100, 2),
        "location_0_1": round(location_score, 4),
        "location_match_pct": round(location_score * 100, 2),
        "preferences_0_1": round(pref_score, 4),
        "preferences_alignment_pct": round(pref_score * 100, 2),
        "weights": {"skill": 0.4, "experience": 0.2, "location": 0.2, "preferences": 0.2},
        "final_composite_pct": final_pct,
    }


def multi_criteria_breakdown(candidate: dict, job: dict, model_type=None) -> dict:
    """Human-readable breakdown for API responses and UI."""
    return compute_multi_criteria_components(candidate, job, model_type=model_type)


def calculate_advanced_score(candidate, job, model_type=None):
    """
    Multi-criteria composite score (single number 0–100).

    Skill match uses embedding similarity over skill lists; other criteria are
    experience, location, and preference alignment.
    """
    return compute_multi_criteria_components(candidate, job, model_type=model_type)[
        "final_composite_pct"
    ]

if __name__ == '__main__':
    # Unit Test for Sample Match Recommendation Demo
    candidate = {
        "skills": ["Python", "ML", "SQL"],
        "experience_years": 2,
        "location": "Hyderabad",
        "preferences": ["Remote"]
    }
    
    job = {
        "title": "Data Scientist",
        "required_skills": ["Python", "ML", "SQL", "Deep Learning"],
        "min_experience": 2,
        "location": "Hyderabad",
        "preferences": ["Analytical Thinking"]
    }
    
    score = calculate_advanced_score(candidate, job)
    logger.info(f"Test Score for {job['title']}: {score}%")