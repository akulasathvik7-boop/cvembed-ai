# Coding by Samitha Randika | https://www.linkedin.com/in/samitha-randika-edirisinghe-b3a68a2b6 #
import joblib
import os
import logging
import numpy as np
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
        logger.error(f"Model {model_type} not available")
        return 0.0
    
    try:
        if model_type == "sbert":
            from model.inference import sbert_inference
            return sbert_inference.calculate_similarity(model, resume_text, jd_text)
        elif model_type == "glove":
            from model.inference import glove_inference
            return glove_inference.calculate_text_similarity(model, resume_text, jd_text)
        elif model_type == "doc2vec":
            from model.inference import doc2vec_inference
            # Use the improved Doc2Vec similarity function
            return doc2vec_inference.calculate_similarity(model, resume_text, jd_text)

        else:
            logger.error(f"Unknown model type: {model_type}")
            return 0.0
    except Exception as e:
        logger.error(f"Similarity calculation error: {e}")
        return 0.0

    
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