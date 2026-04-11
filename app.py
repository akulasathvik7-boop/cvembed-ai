# Coding by Samitha Randika | https://www.linkedin.com/in/samitha-randika-edirisinghe-b3a68a2b6 #
from flask import Flask, render_template, request, redirect, url_for, session
import os
import uuid
import json
import logging

from resume_processor import process_resume, process_jd
from matching_engine import calculate_similarity, get_top_job_matches
from config import MODEL_CONFIG
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logger.warning("python-dotenv not found. Environment variables from .env will not be loaded.")
except Exception as e:
    logger.error(f"Error loading .env file: {e}")

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB limit

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# --- API KEY CONFIGURATION ---
# Note: Currently using Local NLP Engine for 100% reliability
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') 
# -----------------------------


@app.route('/', methods=['GET'])
def index():
    session.clear()
    return render_template('index.html')

@app.route('/process_resume', methods=['POST'])
def process_resume_route():
    try:
        logger.info("Starting resume processing...")
        # Process resume input
        resume_text = ""
        
        if 'resume_file' in request.files:
            resume_file = request.files['resume_file']
            if resume_file.filename != '':
                file_ext = os.path.splitext(resume_file.filename)[1]
                filename = f"resume_{uuid.uuid4().hex}{file_ext}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                logger.info(f"Saving uploaded file to: {file_path}")
                resume_file.save(file_path)
                
                logger.info("Extracting text from resume...")
                resume_text = process_resume(file_path)
                
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info("Cleaned up temporary file.")
        
        if not resume_text and 'resume_text' in request.form:
            logger.info("Using pasted resume text.")
            resume_text = request.form['resume_text']
        
        if resume_text:
            logger.info("Resume text successfully captured. Redirecting to job description upload.")
            session['resume_text'] = resume_text
            return redirect(url_for('upload_jd'))
        
        logger.warning("No resume text found in input.")
        return redirect(url_for('index'))
        
    except Exception as e:
        logger.error(f"Error in process_resume_route: {str(e)}", exc_info=True)
        return render_template('index.html', error=f"An error occurred while processing your resume: {str(e)}")


@app.route('/upload_jd', methods=['GET'])
def upload_jd():
    if 'resume_text' not in session:
        return redirect(url_for('index'))
    return render_template('upload.html')

@app.route('/process_jd', methods=['POST'])
def process_jd_route():
    # Process job description input
    jd_text = ""
    model_type = request.form.get('model_type', MODEL_CONFIG['active_model'])
    
    if 'jd_file' in request.files:
        jd_file = request.files['jd_file']
        if jd_file.filename != '':
            file_ext = os.path.splitext(jd_file.filename)[1]
            filename = f"jd_{uuid.uuid4().hex}{file_ext}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            jd_file.save(file_path)
            jd_text = process_jd(file_path)
            os.remove(file_path)  # Clean up after processing
    
    if not jd_text and 'jd_text' in request.form:
        jd_text = request.form['jd_text']
    
    if jd_text and 'resume_text' in session:
        session['jd_text'] = jd_text
        
        # Calculate similarity
        similarity_score = calculate_similarity(
            session['resume_text'], 
            jd_text,
            model_type
        )
        
        # Get top job matches
        top_matches = get_top_job_matches(
            session['resume_text'],
            model_type
        )
        
        # Generate detailed feedback with Local NLP (Guaranteed to work)
        logger.info("Generating Local NLP feedback for resume...")
        resume_feedback = generate_local_analysis(session['resume_text'], jd_text)
        
        # Store results
        session['similarity_score'] = float(similarity_score)
        session['top_matches'] = [(title, float(score)) for title, score in top_matches]
        session['model_type'] = model_type
        session['resume_feedback'] = resume_feedback
        
        logger.info("Similarity calculation and Local NLP feedback complete.")
        return redirect(url_for('result'))


    
    return redirect(url_for('upload_jd'))

def generate_job_listings(job_title):
    """Fallback job listings for local mode"""
    return [
            {
                "title": job_title,
                "company": "Tech Innovations Inc",
                "location": "Remote",
                "apply_url": "https://example.com/careers"
            },
            {
                "title": f"Senior {job_title}",
                "company": "Global Solutions Ltd",
                "location": "New York, NY",
                "apply_url": "https://example.com/jobs"
            },
            {
                "title": f"{job_title} Specialist",
                "company": "Future Tech",
                "location": "San Francisco, CA",
                "apply_url": "https://example.com/apply"
            }
        ]

def generate_local_analysis(resume_text, jd_text):
    """
    Analyzes the resume against the job description locally using NLP.
    Categorizes results for the modern dashboard.
    """
    try:
        from utils.text_processing import tokenize_text
        from collections import Counter
        
        # Skill taxonomies (simplified for local processing)
        TAXONOMY = {
            "technical": ["python", "java", "javascript", "react", "node", "sql", "mongodb", "aws", "docker", "kubernetes", "api", "rest", "graphql", "backend", "frontend", "fullstack", "devops", "machine", "learning", "data", "science"],
            "soft_skills": ["leadership", "management", "communication", "team", "agile", "scrum", "problem", "solving", "analytical", "creativity", "collaboration", "initiative", "adaptability"],
            "tools": ["git", "jira", "docker", "vscode", "postman", "figma", "jenkins", "terraform", "linux", "windows", "macos"]
        }
        
        # Tokenize both texts
        resume_tokens = set(tokenize_text(resume_text))
        jd_tokens = tokenize_text(jd_text)
        jd_counter = Counter(jd_tokens)
        
        # Get most common keywords in JD (ignoring very short words)
        jd_keywords = [word for word, count in jd_counter.most_common(50) if len(word) > 3]
        
        strengths = []
        drawbacks = []
        missing_keywords = []
        
        # Categorized scores for the radar chart
        alignment = {
            "technical": 0,
            "soft_skills": 0,
            "tools": 0,
            "experience": 0
        }
        
        matches = {cat: [] for cat in TAXONOMY}
        gaps = {cat: [] for cat in TAXONOMY}

        # Analyze against taxonomy
        for category, keywords in TAXONOMY.items():
            cat_matches = 0
            cat_total = 0
            for word in keywords:
                if word in jd_tokens:
                    cat_total += 1
                    if word in resume_tokens:
                        cat_matches += 1
                        matches[category].append(word)
                    else:
                        gaps[category].append(word)
            
            # Simple scoring
            alignment[category] = int((cat_matches / max(1, cat_total)) * 100)

        # Experience placeholder score (based on commonality of JD keywords)
        exp_matches = 0
        for word in jd_keywords:
            if word in resume_tokens:
                exp_matches += 1
            else:
                missing_keywords.append(word)
        
        alignment["experience"] = int((exp_matches / max(1, len(jd_keywords))) * 100)
        
        # Generate summary lists for UI
        for cat in matches:
            if matches[cat]:
                strengths.append(f"Strong match in {cat.replace('_', ' ')}: {', '.join(matches[cat][:3]).title()}")

        # Generate drawbacks with more specific guidance
        for cat in gaps:
            if gaps[cat]:
                gap_items = ', '.join(gaps[cat][:2]).title()
                if cat == "technical":
                    drawbacks.append(f"Missing technical skills: {gap_items}. Consider gaining hands-on experience or certifications.")
                elif cat == "soft_skills":
                    drawbacks.append(f"Untested soft skills: {gap_items}. Highlight these in your achievements or volunteer work.")
                elif cat == "tools":
                    drawbacks.append(f"Missing tools/platforms: {gap_items}. These are valuable additions to your skillset.")
                else:
                    drawbacks.append(f"Gap identified in {cat.replace('_', ' ')}: {gap_items}. Consider adding relevant experience.")

        # Ensure fallback content
        if not strengths:
            strengths = ["Resume structure is readable.", "Text was successfully parsed."]
        if not drawbacks:
            drawbacks = [
                "Consider adding specific use cases or project examples to your resume.",
                "Expand on quantifiable achievements and measurable results.",
                "Include relevant certifications or training related to the role."
            ]
        
        # Calculate overall score for dynamic guidance
        overall_score = sum(alignment.values()) // len(alignment)
        
        # Generate score-based guidance
        guidance = []
        
        if overall_score < 40:
            # Critical gaps
            guidance = [
                "⚠️ CRITICAL: This role requires significantly different expertise. Consider upskilling in core technical areas.",
                f"Priority: Focus on these missing technical skills: {', '.join(gaps.get('technical', [])[:2]).title()}",
                "Action: Pursue relevant certifications or take courses to bridge the major knowledge gaps."
            ]
        elif overall_score < 70:
            # Moderate gaps
            guidance = [
                f"Priority: Strengthen your {gaps.get('technical', ['technical'])[0] if gaps.get('technical') else 'technical'} skills to improve alignment.",
                f"Gap remediation: Work on {', '.join(gaps.get('soft_skills', ['communication'])[:1]).lower()} to enhance candidacy.",
                "Enhancement: Add quantifiable metrics and specific project impact to your resume (e.g., 'improved performance by 30%')."
            ]
        else:
            # Strong alignment
            if missing_keywords:
                guidance = [
                    "✅ Strong alignment! You're well-suited for this role.",
                    f"Polish: Highlight proven experience with {', '.join(missing_keywords[:1]).title() if missing_keywords else 'relevant tools'}.",
                    "Optimization: Emphasize measurable achievements and leadership contributions to stand out."
                ]
            else:
                guidance = [
                    "✅ Excellent match! Your profile aligns well with this opportunity.",
                    "Next step: Prepare case studies showcasing your most relevant projects.",
                    "Recommendation: Emphasize your unique value propositions and achievements in interviews."
                ]
            
        return {
            "strengths": strengths[:3],
            "drawbacks": drawbacks[:3],
            "guidance": guidance[:3],
            "missing_keywords": missing_keywords[:12],
            "alignment": alignment
        }
        
    except Exception as e:
        logger.error(f"Error in local analysis: {e}")
        return {
            "strengths": ["Basic resume analysis complete."],
            "drawbacks": ["Detailed gap analysis failed."],
            "guidance": ["Ensure your resume explicitly mentions the direct keywords from the job description."],
            "missing_keywords": [],
            "alignment": {"technical": 50, "soft_skills": 50, "tools": 50, "experience": 50}
        }






@app.route('/result', methods=['GET'])
def result():
    if 'similarity_score' not in session:
        return redirect(url_for('index'))
    
    # Convert score to integer
    similarity_score = int(round(session['similarity_score']))
    
    # Generate job listings for the top match
    job_listings = []
    if session.get('top_matches'):
        top_job_title = session['top_matches'][0][0]
        job_listings = generate_job_listings(top_job_title)
    
    return render_template('result.html', 
                           similarity_score=similarity_score,
                           top_matches=session['top_matches'],
                           resume_text=session['resume_text'],
                           jd_text=session['jd_text'],
                           job_listings=job_listings,
                           resume_feedback=session.get('resume_feedback'))


if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)