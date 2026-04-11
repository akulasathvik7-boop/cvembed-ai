import sys
import os

# Add current working directory to sys.path
sys.path.append(os.getcwd())

print(f"Python version: {sys.version}")
print(f"Working directory: {os.getcwd()}")


modules = [
    'flask',
    'sentence_transformers',
    'nltk',
    'numpy',
    'pandas',
    'docx',
    'PyPDF2',
    'sklearn',
    'joblib',
    'huggingface_hub',
    'datasets',
    'transformers',
    'torch',
    'gensim',
    'scipy',
    'google.generativeai'
]

print("\nChecking dependencies:")
for module in modules:
    try:
        __import__(module)
        print(f"[OK] {module}")
    except ImportError as e:
        print(f"[ERROR] {module}: {e}")
    except Exception as e:
        print(f"[FATAL] {module}: {e}")

print("\nChecking matching_engine...")
try:
    import matching_engine
    print("[OK] matching_engine imported")
except Exception as e:
    print(f"[ERROR] matching_engine: {e}")
    import traceback
    traceback.print_exc()

print("\nChecking resume_processor...")
try:
    import resume_processor
    print("[OK] resume_processor imported")
except Exception as e:
    print(f"[ERROR] resume_processor: {e}")
    import traceback
    traceback.print_exc()
