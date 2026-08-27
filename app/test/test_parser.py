import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.resume_parser import extract_resume_text

file_path = PROJECT_ROOT / "uploads" / "Shankar_Ghimire_CV.pdf"

text = extract_resume_text(file_path)

print("\n========== RESUME TEXT ==========\n")
print(text)
print("\n=================================\n")
