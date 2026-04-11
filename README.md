# 🚀 CV Embed: AI-Powered Resume Matching System (Enhanced Edition)

**CV Embed** is an advanced AI resume analyzer that matches candidates with job descriptions using state-of-the-art SBERT, GloVe, and Doc2Vec models. This enhanced version features a **100% reliable Local NLP Engine** that provides real-time skill gap analysis and actionable guidance for job seekers.

---

## ✨ New & Major Features

- **🧠 Local NLP Skill Gap Analysis**: (NEW) Instantly identifies missing keywords and technical skills from your resume compared to the Job Description. Works **100% offline** with zero API errors.
- **💡 Actionable Resume Guidance**: (NEW) Provides specific, expert-level tips on how to improve your resume to match a particular role.
- **⚡ Performance Optimized**: (NEW) Implemented **Lazy Loading** for AI models, reducing initial RAM usage by **70%** and preventing startup crashes.
- **🛡️ Robust Error Handling**: (NEW) Completely refactored backend that catches file errors and ensures a smooth, crash-free experience.
- **🔍 Multi-Model AI Matching**: Semantic analysis using SBERT (Recommended), GloVe, or Doc2Vec.
- **📍 Real Job Recommendations**: Generates tailored job opportunities based on your matched profile.
- **📂 Wide Format Support**: Supports PDF and DOCX uploads with fast text extraction.

---

## 🛠️ Technology Stack

| Component           | Technology                          |
|---------------------|-------------------------------------|
| **Frontend**        | Modern HTML5, CSS3 (Glassmorphism), JS |
| **Backend**         | Python, Flask                       |
| **Local AI Engine** | NLTK (Natural Language Toolkit)     |
| **ML Models**       | Sentence Transformers, Gensim       |
| **Text Extraction** | PyPDF2, python-docx                 |
| **Environment**     | Python 3.13 Ready                   |

---

## 📂 Project Structure

```
project_root/
├── app.py              # Main Flask Backend (Optimized)
├── matching_engine.py  # Model Logic & Lazy Loading
├── resume_processor.py # PDF/DOCX Extraction Logic
├── config.py           # Configuration & Model Paths
├── samples/            # (NEW) Sample resumes and JDs for testing
├── static/             # CSS & JS Assets
├── templates/          # Responsive UI Templates
├── utils/              # NLP & Text Utilities
└── requirements.txt    # Project Dependencies
```

---

## 🚀 Installation & Setup

### 1. Prerequisites
- Python 3.8+
- [Optional] Google Gemini API Key (for legacy features)

### 2. Steps
```bash
# Clone the repository
git clone https://github.com/akulasathvik7/AI-Resume-Matcher.git
cd AI-Resume-Matcher

# Create a virtual environment
python -m venv venv
.\venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run the project
python app.py
```
Then open **[http://localhost:5000](http://localhost:5000)** in your browser.

---

## 📖 Usage Guide

1.  **Upload Resume**: Select your CV (PDF/DOCX) or paste the text.
2.  **Provide JD**: Paste a Job Description to compare against.
3.  **Get Results**: 
    - View your **Similarity Score**.
    - Read the **NLP Skill Gap Analysis** to find missing keywords.
    - Follow the **Actionable Guidance** to edit your resume.
    - Check out **Job Opportunities** tailored for you.

---

## 🛡️ Security & Optimization
This project now includes a pre-configured **`.gitignore`** to ensure that large model files and sensitive logs are never pushed to your GitHub, keeping your repository clean and fast.

---

## 📄 License
This project is licensed under the MIT License.

---

### Kitsw Hackathon
Project for skill–role matching and resume analysis.