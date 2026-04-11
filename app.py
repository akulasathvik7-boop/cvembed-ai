from flask import Flask, render_template, request, redirect, url_for, session
import os
import uuid
import logging
import math

# Server-side store for resume/JD text (avoids 4KB cookie limit silently dropping session data)
_CONTENT_STORE = {}

DEFAULT_RESUME_FEEDBACK = {
    "strengths": ["Analysis completed using your resume and job description."],
    "drawbacks": ["Add more role-specific keywords from the job posting to improve match detail."],
    "guidance": ["Compare your resume line-by-line with the required skills in the JD."],
    "missing_keywords": [],
    "alignment": {"technical": 50, "soft_skills": 50, "tools": 50, "experience": 50},
}

from resume_processor import process_resume, process_jd
from matching_engine import calculate_similarity, get_top_job_matches
from config import MODEL_CONFIG

# Set up logging before optional dotenv (logger used in except handlers)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logger.warning("python-dotenv not found. Environment variables from .env will not be loaded.")
except Exception as e:
    logger.error(f"Error loading .env file: {e}")

app = Flask(__name__)
# Production: set SECRET_KEY in the environment so sessions survive restarts.
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB limit

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# --- API KEY CONFIGURATION ---
# Note: Currently using Local NLP Engine for 100% reliability
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') 
# -----------------------------


def _purge_content_store(sid):
    if sid and sid in _CONTENT_STORE:
        try:
            del _CONTENT_STORE[sid]
        except KeyError:
            pass


@app.route('/', methods=['GET'])
def index():
    _purge_content_store(session.get("content_sid"))
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
                resume_result = process_resume(file_path)
                resume_text = resume_result.get("text", "") if isinstance(resume_result, dict) else (resume_result or "")
                
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info("Cleaned up temporary file.")
        
        if not resume_text and 'resume_text' in request.form:
            logger.info("Using pasted resume text.")
            resume_text = request.form['resume_text']
        
        if resume_text:
            logger.info("Resume text successfully captured. Redirecting to job description upload.")
            sid = str(uuid.uuid4())
            session["content_sid"] = sid
            _CONTENT_STORE[sid] = {"resume_text": resume_text}
            return redirect(url_for('upload_jd'))
        
        logger.warning("No resume text found in input.")
        return render_template(
            "index.html",
            error="No resume text was found. Upload a PDF/DOCX file or paste your resume.",
        )
        
    except Exception as e:
        logger.error(f"Error in process_resume_route: {str(e)}", exc_info=True)
        return render_template('index.html', error=f"An error occurred while processing your resume: {str(e)}")


def _resume_from_store():
    sid = session.get("content_sid")
    if not sid:
        return None, None
    blob = _CONTENT_STORE.get(sid) or {}
    return sid, blob.get("resume_text") or ""


@app.route('/upload_jd', methods=['GET'])
def upload_jd():
    sid, resume_text = _resume_from_store()
    if not sid or not (resume_text or "").strip():
        return redirect(url_for("index"))
    return render_template(
        "upload.html",
        active_model=MODEL_CONFIG.get("active_model", "glove"),
    )

@app.route('/process_jd', methods=['POST'])
def process_jd_route():
    jd_text = ""
    model_type = request.form.get("model_type", MODEL_CONFIG["active_model"])

    sid, resume_text = _resume_from_store()
    if not sid or not (resume_text or "").strip():
        return render_template(
            "index.html",
            error="Your session expired or the resume was not found. Please upload your resume again.",
        )

    if "jd_file" in request.files:
        jd_file = request.files["jd_file"]
        if jd_file.filename != "":
            file_ext = os.path.splitext(jd_file.filename)[1].lower()
            filename = f"jd_{uuid.uuid4().hex}{file_ext}"
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            jd_file.save(file_path)
            try:
                jd_result = process_jd(file_path)
                jd_text = (
                    jd_result.get("text", "")
                    if isinstance(jd_result, dict)
                    else (jd_result or "")
                )
            finally:
                if os.path.exists(file_path):
                    os.remove(file_path)

    if not jd_text and "jd_text" in request.form:
        jd_text = request.form.get("jd_text") or ""

    jd_text = (jd_text or "").strip()
    if not jd_text:
        return (
            render_template(
                "upload.html",
                error="No job description was read. Paste the JD into the text box or upload a PDF, DOCX, or TXT file with selectable text.",
                active_model=MODEL_CONFIG.get("active_model", "glove"),
            ),
            400,
        )

    _CONTENT_STORE[sid]["jd_text"] = jd_text

    try:
        similarity_score = float(calculate_similarity(resume_text, jd_text, model_type))
    except Exception as e:
        logger.error(f"Similarity failed: {e}", exc_info=True)
        similarity_score = 0.0
    if math.isnan(similarity_score) or math.isinf(similarity_score):
        similarity_score = 0.0

    try:
        top_matches = get_top_job_matches(resume_text, model_type)
    except Exception as e:
        logger.error(f"Top matches failed: {e}", exc_info=True)
        top_matches = []

    logger.info("Generating Local NLP feedback for resume...")
    resume_feedback = generate_local_analysis(resume_text, jd_text)

    session["similarity_score"] = similarity_score
    session["top_matches"] = [[title, float(score)] for title, score in top_matches]
    session["model_type"] = model_type
    session["resume_feedback"] = resume_feedback

    logger.info("Similarity calculation and Local NLP feedback complete.")
    return redirect(url_for("result"))

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






def _normalize_feedback(raw):
    out = dict(DEFAULT_RESUME_FEEDBACK)
    if not raw or not isinstance(raw, dict):
        return out
    for key in (
        "strengths",
        "drawbacks",
        "guidance",
        "missing_keywords",
        "alignment",
    ):
        if key in raw and raw[key] is not None:
            out[key] = raw[key]
    al = out.get("alignment") or {}
    for k, default_v in DEFAULT_RESUME_FEEDBACK["alignment"].items():
        if k not in al:
            al[k] = default_v
    out["alignment"] = al
    return out


@app.route('/result', methods=['GET'])
def result():
    if "similarity_score" not in session:
        return redirect(url_for("index"))

    sid = session.get("content_sid")
    store = _CONTENT_STORE.get(sid) or {}
    resume_text = store.get("resume_text") or ""
    jd_text = store.get("jd_text") or ""

    raw_score = float(session["similarity_score"])
    if math.isnan(raw_score) or math.isinf(raw_score):
        raw_score = 0.0
    similarity_score = int(round(max(0.0, min(100.0, raw_score))))

    job_listings = []
    tm = session.get("top_matches") or []
    if tm:
        first = tm[0]
        top_job_title = first[0] if isinstance(first, (list, tuple)) else first
        job_listings = generate_job_listings(top_job_title)

    resume_feedback = _normalize_feedback(session.get("resume_feedback"))

    return render_template(
        "result.html",
        similarity_score=similarity_score,
        top_matches=tm,
        resume_text=resume_text,
        jd_text=jd_text,
        job_listings=job_listings,
        resume_feedback=resume_feedback,
    )


if __name__ == "__main__":
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes")
    app.run(host="0.0.0.0", port=port, debug=debug)