import sys
import os
sys.path.append(os.getcwd())

print("Loading matching_engine...")
try:
    import matching_engine
    print("matching_engine loaded successfully.")
    print("Models loaded:", matching_engine.MODELS.keys())
except Exception as e:
    print(f"Error loading matching_engine: {e}")
    import traceback
    traceback.print_exc()
