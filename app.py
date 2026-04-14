"""
app.py — CVEmbed AI: Main Flask Application
Features: Resume analysis, job matching, role eligibility, LinkedIn integration,
          optional authentication, and analysis history for logged-in users.
"""

from flask import Flask, render_template, request, redirect, url_for, session
import os
import uuid
import logging
import math

# ------------------------------------------------------------------
# Server-side content store (avoids 4 KB cookie limit)
# ------------------------------------------------------------------
_CONTENT_STORE = {}

DEFAULT_RESUME_FEEDBACK = {
    "strengths": ["Analysis completed using your resume and job description."],
    "drawbacks": ["Add more role-specific keywords from the job posting to improve match detail."],
    "guidance": ["Compare your resume line-by-line with the required skills in the JD."],
    "missing_keywords": [],
    "alignment": {"technical": 50, "soft_skills": 50, "tools": 50, "experience": 50},
}

# ------------------------------------------------------------------
# Auth imports
# ------------------------------------------------------------------
from auth import auth_bp, init_db, get_current_user, save_analysis, get_user_history
from resume_processor import process_resume, process_jd
from matching_engine import calculate_similarity, get_top_job_matches, _fallback_similarity_score
from config import MODEL_CONFIG

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------
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
    logger.warning("python-dotenv not found. .env file will not be loaded.")
except Exception as e:
    logger.error(f"Error loading .env file: {e}")

# ------------------------------------------------------------------
# Flask app setup
# ------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Register auth blueprint & init DB
app.register_blueprint(auth_bp)
with app.app_context():
    init_db()

# Gemini API key (optional)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# ------------------------------------------------------------------
# Template context processor — injects current_user everywhere
# ------------------------------------------------------------------
@app.context_processor
def inject_user():
    return {'current_user': get_current_user(request)}


# ------------------------------------------------------------------
# Role Eligibility Engine
# ------------------------------------------------------------------
ROLE_TAXONOMY_KEYWORDS = {
    "Software Engineer": [
        "python", "java", "javascript", "cpp", "algorithm", "data structures",
        "git", "api", "backend", "software", "development", "coding", "programming", "object oriented"
    ],
    "Data Scientist": [
        "python", "machine learning", "statistics", "pandas", "numpy", "sklearn",
        "scikit", "data analysis", "visualization", "tensorflow", "pytorch",
        "regression", "classification", "deep learning", "neural"
    ],
    "Frontend Developer": [
        "html", "css", "javascript", "react", "vue", "angular", "responsive",
        "ui", "typescript", "webpack", "sass", "tailwind", "bootstrap", "dom"
    ],
    "Backend Developer": [
        "python", "java", "nodejs", "sql", "api", "rest", "database", "server",
        "microservices", "backend", "express", "django", "flask", "spring", "graphql"
    ],
    "Full Stack Developer": [
        "react", "nodejs", "javascript", "html", "css", "backend", "frontend",
        "database", "api", "fullstack", "mern", "mean", "mongodb", "express"
    ],
    "DevOps Engineer": [
        "docker", "kubernetes", "cicd", "jenkins", "aws", "azure", "linux",
        "terraform", "ansible", "monitoring", "deployment", "devops", "pipeline", "automation"
    ],
    "Cloud Engineer": [
        "aws", "azure", "gcp", "cloud", "terraform", "kubernetes", "microservices",
        "serverless", "iam", "vpc", "cloudformation", "lambda", "s3"
    ],
    "Machine Learning Engineer": [
        "machine learning", "deep learning", "python", "tensorflow", "pytorch",
        "model", "training", "deployment", "mlops", "scikit", "neural network", "transformers", "huggingface"
    ],
    "Data Engineer": [
        "sql", "spark", "hadoop", "etl", "pipeline", "bigquery", "airflow",
        "kafka", "data warehouse", "dbt", "database", "data lake", "snowflake"
    ],
    "Security Analyst": [
        "security", "penetration testing", "vulnerability", "siem", "firewall",
        "encryption", "compliance", "cybersecurity", "threat", "incident response", "kali", "nmap"
    ],
    "Mobile Developer": [
        "android", "ios", "react native", "flutter", "kotlin", "swift",
        "mobile", "firebase", "app development", "xcode", "playstore"
    ],
    "UI/UX Designer": [
        "figma", "sketch", "xd", "wireframe", "prototyping", "user research",
        "usability", "typography", "design", "ux", "accessibility", "user interface"
    ],
    "Database Administrator": [
        "sql", "mysql", "postgresql", "oracle", "mongodb", "database", "dba",
        "replication", "backup", "query optimization", "indexing", "normalization"
    ],
    "Network Administrator": [
        "networking", "cisco", "routing", "switching", "tcp", "dns", "dhcp",
        "vpn", "firewall", "lan", "wan", "network protocols"
    ],
    "Product Manager": [
        "product", "roadmap", "agile", "stakeholder", "requirements", "scrum",
        "user stories", "kpi", "strategy", "backlog", "sprint", "prioritization"
    ],
    "QA Engineer": [
        "testing", "qa", "quality assurance", "selenium", "junit", "pytest",
        "automation", "test cases", "bug", "regression", "test plan", "jmeter"
    ],
    "System Administrator": [
        "linux", "windows server", "active directory", "powershell", "bash",
        "system administration", "vmware", "storage", "backup", "patch management"
    ],
    "Blockchain Developer": [
        "blockchain", "ethereum", "solidity", "smart contracts", "web3",
        "nft", "defi", "cryptocurrency", "rust", "go"
    ],
    "Embedded Systems Engineer": [
        "embedded", "firmware", "arduino", "raspberry pi", "iot",
        "hardware", "rtos", "microcontroller", "circuit", "pcb"
    ],
    "Game Developer": [
        "unity", "unreal", "game development", "opengl", "physics",
        "3d", "game engine", "rendering", "gameplay", "csharp"
    ],
}


SOFT_SKILL_KEYWORDS = {
    "leadership", "management", "communication", "team", "agile", "scrum",
    "problem", "solving", "analytical", "creativity", "collaboration",
    "initiative", "adaptability", "mentoring", "critical thinking",
    "stakeholder", "prioritization", "strategy", "user stories", "ownership",
}

TOOL_KEYWORDS = {
    "git", "github", "gitlab", "bitbucket", "jira", "docker", "kubernetes",
    "jenkins", "terraform", "ansible", "linux", "windows", "macos",
    "postman", "figma", "vscode", "airflow", "spark", "hadoop", "dbt",
    "kafka", "bigquery", "snowflake", "mysql", "postgresql", "oracle",
    "mongodb", "selenium", "pytest", "junit", "jmeter", "aws", "azure", "gcp",
    "cloudformation", "lambda", "s3", "xcode", "firebase", "vmware",
}

PROJECT_CONTEXT_TERMS = (
    "project", "built", "developed", "implemented", "designed", "deployed",
    "integrated", "created", "engineered", "delivered", "production"
)


def _mentions_in_project_context(resume_text: str, term: str) -> bool:
    """
    Returns True when a term appears near project/action words.
    Used to award partial credit for tools even if explicit skill tagging is weak.
    """
    text = f" {resume_text.lower()} "
    t = term.lower().strip()
    if not t:
        return False
    if t not in text:
        return False
    for ctx in PROJECT_CONTEXT_TERMS:
        if f"{ctx} {t}" in text or f"{t} {ctx}" in text:
            return True
    return False


def _score_role_against_resume(resume_text: str, resume_tokens: set, role_keywords: list):
    """
    Hard Skills = 80%, Soft Skills = 20%
    - Heavy penalties only when hard skills are missing.
    - Tools in project context count as partial matches (0.5).
    """
    hard_keywords, soft_keywords = [], []
    for kw in role_keywords:
        k = kw.lower().strip()
        if k in SOFT_SKILL_KEYWORDS:
            soft_keywords.append(k)
        else:
            hard_keywords.append(k)

    hard_points = 0.0
    matched_hard, missing_hard, partial_hard = [], [], []
    resume_lower = resume_text.lower()

    for kw in hard_keywords:
        exact = kw in resume_lower or kw in resume_tokens
        if exact:
            hard_points += 1.0
            matched_hard.append(kw)
            continue

        # Partial match rule for tools: if used in project context, give partial credit.
        if kw in TOOL_KEYWORDS and _mentions_in_project_context(resume_text, kw):
            hard_points += 0.5
            partial_hard.append(kw)
        else:
            missing_hard.append(kw)

    soft_points = 0.0
    matched_soft, missing_soft = [], []
    for kw in soft_keywords:
        if kw in resume_lower or kw in resume_tokens:
            soft_points += 1.0
            matched_soft.append(kw)
        else:
            missing_soft.append(kw)

    hard_score = hard_points / max(1, len(hard_keywords))
    soft_score = soft_points / max(1, len(soft_keywords))
    weighted = (0.8 * hard_score) + (0.2 * soft_score)

    # Heavy penalty ONLY for hard-skill gaps.
    missing_hard_ratio = len(missing_hard) / max(1, len(hard_keywords))
    penalty_multiplier = max(0.35, 1 - (0.7 * missing_hard_ratio))
    final_pct = int(round(weighted * penalty_multiplier * 100))

    return {
        "match_pct": min(final_pct, 95),
        "matched_skills": matched_hard + matched_soft,
        "missing_skills": missing_hard + missing_soft,
        "partial_matches": partial_hard,
    }


def get_eligible_roles(resume_text, top_n=3):
    """
    Determine top N job roles the resume is eligible for.
    Returns list of dicts: {role, match_pct, linkedin_url, indeed_url}
    """
    if not resume_text or not resume_text.strip():
        return []
    try:
        from utils.text_processing import tokenize_text
        resume_lower = resume_text.lower()
        resume_tokens = set(tokenize_text(resume_lower))

        scores = {}
        for role, keywords in ROLE_TAXONOMY_KEYWORDS.items():
            scored = _score_role_against_resume(resume_text, resume_tokens, keywords)
            scores[role] = scored

        sorted_roles = sorted(
            scores.items(),
            key=lambda x: x[1]["match_pct"],
            reverse=True
        )

        result = []
        for role, details in sorted_roles[:top_n]:
            encoded_role = role.replace(' ', '+')
            result.append({
                "role": role,
                # Keep small floor so UI always has interpretable values.
                "match_pct": max(details["match_pct"], 12),
                "matched_skills": details["matched_skills"][:8],
                "missing_skills": details["missing_skills"][:8],
                "partial_matches": details["partial_matches"][:6],
                "linkedin_url": f"https://www.linkedin.com/jobs/search/?keywords={encoded_role}&location=Worldwide",
                "indeed_url": f"https://www.indeed.com/jobs?q={encoded_role}",
                "naukri_url": f"https://www.naukri.com/{role.lower().replace(' ', '-')}-jobs",
            })
        return result
    except Exception as e:
        logger.error(f"Role eligibility error: {e}", exc_info=True)
        return []


# ------------------------------------------------------------------
# Job Listings (LinkedIn + Indeed + Naukri)
# ------------------------------------------------------------------
def generate_job_listings(job_title):
    """Generate job listing cards with real LinkedIn/Indeed/Naukri search links."""
    safe_title = (job_title or "Software Engineer").strip()
    encoded = safe_title.replace(' ', '+')
    slug = safe_title.lower().replace(' ', '-')
    return [
        {
            "title": safe_title,
            "company": "LinkedIn Jobs",
            "location": "Worldwide · Remote / On-site",
            "apply_url": f"https://www.linkedin.com/jobs/search/?keywords={encoded}&location=Worldwide",
            "platform": "linkedin",
            "badge": "LinkedIn",
        },
        {
            "title": f"Senior {safe_title}",
            "company": "Indeed",
            "location": "Multiple Locations",
            "apply_url": f"https://www.indeed.com/jobs?q={encoded}",
            "platform": "indeed",
            "badge": "Indeed",
        },
        {
            "title": f"{safe_title} Specialist",
            "company": "Naukri",
            "location": "India · Pan-India",
            "apply_url": f"https://www.naukri.com/{slug}-jobs",
            "platform": "naukri",
            "badge": "Naukri",
        },
    ]


# ------------------------------------------------------------------
# Content Store helpers
# ------------------------------------------------------------------
def _purge_content_store(sid):
    if sid and sid in _CONTENT_STORE:
        try:
            del _CONTENT_STORE[sid]
        except KeyError:
            pass


def _resume_from_store():
    sid = session.get("content_sid")
    if not sid:
        return None, None
    blob = _CONTENT_STORE.get(sid) or {}
    return sid, blob.get("resume_text") or ""


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@app.route('/', methods=['GET'])
def index():
    _purge_content_store(session.get("content_sid"))
    session.clear()
    return render_template('index.html')


@app.route('/process_resume', methods=['POST'])
def process_resume_route():
    try:
        logger.info("Starting resume processing...")
        resume_text = ""

        if 'resume_file' in request.files:
            resume_file = request.files['resume_file']
            if resume_file.filename != '':
                file_ext = os.path.splitext(resume_file.filename)[1]
                filename = f"resume_{uuid.uuid4().hex}{file_ext}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                logger.info(f"Saving uploaded file: {file_path}")
                resume_file.save(file_path)
                try:
                    resume_result = process_resume(file_path)
                    resume_text = (
                        resume_result.get("text", "")
                        if isinstance(resume_result, dict)
                        else (resume_result or "")
                    )
                finally:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.info("Cleaned up temporary resume file.")

        if not resume_text and 'resume_text' in request.form:
            logger.info("Using pasted resume text.")
            resume_text = request.form['resume_text']

        if resume_text and resume_text.strip():
            logger.info("Resume captured. Redirecting to JD upload.")
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
        logger.error(f"Error in process_resume_route: {e}", exc_info=True)
        return render_template('index.html', error=f"An error occurred while processing your resume: {e}")


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
                error="No job description was read. Paste the JD or upload a PDF / DOCX / TXT with selectable text.",
                active_model=MODEL_CONFIG.get("active_model", "glove"),
            ),
            400,
        )

    _CONTENT_STORE[sid]["jd_text"] = jd_text

    # --- Similarity Score ---
    try:
        similarity_score = float(calculate_similarity(resume_text, jd_text, model_type))
        if similarity_score <= 0.01 and resume_text.strip() and jd_text.strip():
            similarity_score = float(_fallback_similarity_score(resume_text, jd_text))
    except Exception as e:
        logger.error(f"Similarity calculation failed: {e}", exc_info=True)
        similarity_score = 0.0
    if math.isnan(similarity_score) or math.isinf(similarity_score):
        similarity_score = 0.0

    # --- Top Job Matches ---
    try:
        top_matches = get_top_job_matches(resume_text, model_type)
    except Exception as e:
        logger.error(f"Top matches failed: {e}", exc_info=True)
        top_matches = []

    # --- Local NLP Feedback ---
    logger.info("Generating local NLP feedback...")
    resume_feedback = generate_local_analysis(resume_text, jd_text)

    # --- Role Eligibility ---
    logger.info("Computing role eligibility...")
    eligible_roles = get_eligible_roles(resume_text, top_n=3)

    # --- Save to History (logged-in users only) ---
    user = get_current_user(request)
    if user:
        top_role_name = eligible_roles[0]["role"] if eligible_roles else (
            top_matches[0][0] if top_matches else "Unknown"
        )
        save_analysis(user["user_id"], similarity_score, top_role_name, model_type)

    # --- Store in session ---
    session["similarity_score"] = similarity_score
    session["top_matches"] = [[title, float(score)] for title, score in top_matches]
    session["model_type"] = model_type
    session["resume_feedback"] = resume_feedback
    session["eligible_roles"] = eligible_roles

    logger.info("Analysis complete. Redirecting to results.")
    return redirect(url_for("result"))


# ------------------------------------------------------------------
# Local NLP Analysis
# ------------------------------------------------------------------
def generate_local_analysis(resume_text, jd_text):
    """
    Analyses the resume against the job description locally.
    Returns categorized strengths, drawbacks, guidance, keywords, and alignment scores.
    """
    try:
        from utils.text_processing import tokenize_text
        from collections import Counter

        TAXONOMY = {
            "technical": [
                "python", "java", "javascript", "react", "node", "sql", "mongodb", "aws",
                "docker", "kubernetes", "api", "rest", "graphql", "backend", "frontend",
                "fullstack", "devops", "machine", "learning", "data", "science", "typescript",
                "angular", "vue", "redis", "kafka", "spark", "hadoop",
            ],
            "soft_skills": [
                "leadership", "management", "communication", "team", "agile", "scrum",
                "problem", "solving", "analytical", "creativity", "collaboration",
                "initiative", "adaptability", "mentoring", "critical thinking",
            ],
            "tools": [
                "git", "jira", "docker", "vscode", "postman", "figma", "jenkins",
                "terraform", "linux", "windows", "macos", "github", "gitlab", "bitbucket",
            ],
        }

        resume_tokens = set(tokenize_text(resume_text))
        jd_tokens = tokenize_text(jd_text)
        jd_counter = Counter(jd_tokens)
        jd_keywords = [w for w, _ in jd_counter.most_common(50) if len(w) > 3]

        strengths, drawbacks, missing_keywords = [], [], []
        alignment = {"technical": 0, "soft_skills": 0, "tools": 0, "experience": 0}

        matches = {cat: [] for cat in TAXONOMY}
        gaps = {cat: [] for cat in TAXONOMY}

        for category, keywords in TAXONOMY.items():
            cat_matches, cat_total = 0, 0
            for word in keywords:
                if word in jd_tokens:
                    cat_total += 1
                    if word in resume_tokens:
                        cat_matches += 1
                        matches[category].append(word)
                    else:
                        gaps[category].append(word)
            alignment[category] = int((cat_matches / max(1, cat_total)) * 100)

        exp_matches = 0
        for word in jd_keywords:
            if word in resume_tokens:
                exp_matches += 1
            else:
                missing_keywords.append(word)
        alignment["experience"] = int((exp_matches / max(1, len(jd_keywords))) * 100)

        for cat in matches:
            if matches[cat]:
                strengths.append(
                    f"Strong {cat.replace('_', ' ')} match: {', '.join(matches[cat][:3]).title()}"
                )

        severity_map = {"technical": "Critical", "soft_skills": "Moderate", "tools": "Minor"}
        for cat in gaps:
            if gaps[cat]:
                sev = severity_map.get(cat, "Moderate")
                gap_items = ', '.join(gaps[cat][:2]).title()
                if cat == "technical":
                    drawbacks.append(
                        f"[{sev}] Missing technical skills: {gap_items}. Gain hands-on experience or pursue certifications."
                    )
                elif cat == "soft_skills":
                    drawbacks.append(
                        f"[{sev}] Untested soft skills: {gap_items}. Highlight these in achievements or volunteer work."
                    )
                elif cat == "tools":
                    drawbacks.append(
                        f"[{sev}] Missing tools: {gap_items}. Add these to your project stack."
                    )

        if not strengths:
            strengths = ["Resume structure is readable and parseable.", "Text content was successfully analysed."]
        if not drawbacks:
            drawbacks = [
                "[Minor] Add specific project examples with measurable outcomes.",
                "[Minor] Expand on quantifiable achievements and results.",
                "[Minor] Include relevant certifications tied to the role.",
            ]

        overall_score = sum(alignment.values()) // len(alignment)

        if overall_score < 40:
            guidance = [
                "⚠️ CRITICAL: This role requires significantly different expertise. Consider focused upskilling.",
                f"Priority: Bridge the gap in {', '.join(gaps.get('technical', ['core technical'])[:2]).title() or 'technical areas'}.",
                "Action: Pursue relevant certifications or structured courses to address major knowledge gaps.",
            ]
        elif overall_score < 70:
            guidance = [
                f"Priority: Strengthen {gaps['technical'][0].title() if gaps.get('technical') else 'core technical'} skills.",
                f"Gap remediation: Highlight {', '.join(gaps.get('soft_skills', ['communication'])[:1]).lower()} with concrete examples.",
                "Enhancement: Add measurable metrics (e.g., 'reduced latency by 40%') to each achievement.",
            ]
        else:
            guidance = [
                "✅ Strong alignment! You are a competitive candidate for this role.",
                f"Polish: Highlight expertise with {', '.join(missing_keywords[:2]).title() or 'advanced tools'}.",
                "Optimization: Emphasise leadership impact and cross-team collaboration in your summary.",
            ]

        return {
            "strengths": strengths[:3],
            "drawbacks": drawbacks[:3],
            "guidance": guidance[:3],
            "missing_keywords": missing_keywords[:12],
            "alignment": alignment,
        }

    except Exception as e:
        logger.error(f"Error in local analysis: {e}", exc_info=True)
        return {
            "strengths": ["Basic resume analysis complete."],
            "drawbacks": ["Detailed gap analysis encountered an error."],
            "guidance": ["Ensure your resume explicitly mentions direct keywords from the job description."],
            "missing_keywords": [],
            "alignment": {"technical": 50, "soft_skills": 50, "tools": 50, "experience": 50},
        }


# ------------------------------------------------------------------
# Feedback normaliser
# ------------------------------------------------------------------
def _normalize_feedback(raw):
    out = dict(DEFAULT_RESUME_FEEDBACK)
    if not raw or not isinstance(raw, dict):
        return out
    for key in ("strengths", "drawbacks", "guidance", "missing_keywords", "alignment"):
        if key in raw and raw[key] is not None:
            out[key] = raw[key]
    al = out.get("alignment") or {}
    for k, default_v in DEFAULT_RESUME_FEEDBACK["alignment"].items():
        if k not in al:
            al[k] = default_v
    out["alignment"] = al
    return out


# ------------------------------------------------------------------
# Result Route
# ------------------------------------------------------------------
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
    eligible_roles = session.get("eligible_roles") or []

    return render_template(
        "result.html",
        similarity_score=similarity_score,
        top_matches=tm,
        resume_text=resume_text,
        jd_text=jd_text,
        job_listings=job_listings,
        resume_feedback=resume_feedback,
        eligible_roles=eligible_roles,
        model_type=session.get("model_type", "glove"),
    )


# ------------------------------------------------------------------
# History Route (login required)
# ------------------------------------------------------------------
@app.route('/history')
def history():
    user = get_current_user(request)
    if not user:
        return redirect(url_for('auth.login'))
    items = get_user_history(user['user_id'])
    return render_template('history.html', history=items, username=user.get('username', 'User'))


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------
if __name__ == "__main__":
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes")
    app.run(host="0.0.0.0", port=port, debug=debug)