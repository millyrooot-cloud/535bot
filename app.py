"""
Kelley Compass AI - Simplified Flask Chatbot for Course Advising
Uses Groq LLM with fallback to rule-based recommendations
"""

import io
import json
import os
import re
import threading
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, render_template, session
from pypdf import PdfReader

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
    print("[INIT] google.generativeai module imported successfully")
except ImportError:
    GEMINI_AVAILABLE = False
    print("[INIT] WARNING: google.generativeai not installed (pip install google-generativeai)")

# Load environment
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env.local")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_API_KEY_2 = os.getenv("GROQ_API_KEY_2", "").strip()  # Fallback Groq key
GROQ_API_KEY_3 = os.getenv("GROQ_API_KEY3", "").strip()   # Second fallback Groq key
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")

# Load RAG context documents - SYSTEM.MD as primary (~1,800 tokens, optimized)
RAG_SYSTEM_PATH = BASE_DIR / "RAG" / "system.md"
RAG_CONTEXT_PATH = BASE_DIR / "RAG" / "context.md"
RAG_CONTEXT = ""

if RAG_SYSTEM_PATH.exists():
    try:
        with open(RAG_SYSTEM_PATH, "r", encoding="utf-8") as f:
            RAG_CONTEXT = f.read()
        print(f"[INIT] Loaded optimized system.md: {len(RAG_CONTEXT)} chars (approx 1,800 tokens)")
    except Exception as e:
        print(f"[INIT] Failed to load system.md: {e}")

# Keep context.md available as reference (not injected into prompts)
CONTEXT_REFERENCE = ""
if RAG_CONTEXT_PATH.exists():
    try:
        with open(RAG_CONTEXT_PATH, "r", encoding="utf-8") as f:
            CONTEXT_REFERENCE = f.read()
        print(f"[INIT] Loaded context.md (reference only): {len(CONTEXT_REFERENCE)} chars")
    except Exception as e:
        print(f"[INIT] Note: context.md not available: {e}")

if RAG_CONTEXT:
    print(f"[INIT] RAG is ready: optimized prompts will use system.md")

print(f"[INIT] API Configuration:")
print(f"      GEMINI_API_KEY present: {bool(GEMINI_API_KEY)}")
print(f"      GROQ_API_KEY present: {bool(GROQ_API_KEY)}")
print(f"      GROQ_MODEL: {GROQ_MODEL}")
print(f"[INIT] Starting Flask app...")

# Flask app setup
app = Flask(__name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(BASE_DIR / "static"))
app.secret_key = FLASK_SECRET_KEY

# ============================================================================
# COURSE DATA & CURRICULUM DEFINITIONS
# ============================================================================

ICORE_REQUIREMENTS = {
    "ENG-W 131": {"title": "English Composition", "credits": 3, "min_grade": "C"},
    "BUS-C 104": {"title": "Business Presentations", "credits": 3, "min_grade": "C"},
    "BUS-T 175": {"title": "Kelley Compass 1", "credits": 1.5, "min_grade": "C"},
    "MATH-B 110": {"title": "Math for Business", "credits": 3, "min_grade": "C"},
    "MATH-M 119": {"title": "Calculus for Business", "credits": 3, "min_grade": "C"},
    "BUS-K 201": {"title": "Business Info Systems", "credits": 3, "min_grade": "C"},
    "BUS-A 100": {"title": "Intro Accounting", "credits": 1, "min_grade": "C"},
    "ECON-B 251": {"title": "Economics for Business I", "credits": 3, "min_grade": "C"},
    "BUS-C 204": {"title": "Business Writing", "credits": 3, "min_grade": "C"},
    "BUS-T 275": {"title": "Kelley Compass 2", "credits": 1.5, "min_grade": "C"},
    "BUS-K 303": {"title": "Technology & Business Analysis", "credits": 3, "min_grade": "C"},
    "BUS-L 201": {"title": "Legal Environment of Business", "credits": 3, "min_grade": "C"},
    "BUS-A 304": {"title": "Financial Reporting & Analysis", "credits": 3, "min_grade": "C"},
    "BUS-A 306": {"title": "Management Accounting & Analysis", "credits": 3, "min_grade": "C"},
    "ECON-E 370": {"title": "Statistics for Business", "credits": 3, "min_grade": "C"},
    "STAT-S 301": {"title": "Statistics for Business", "credits": 3, "min_grade": "C"},
    "BUS-G 202": {"title": "Business, Government and Society", "credits": 3, "min_grade": "C"},
    "BUS-D 270": {"title": "Global Business Environments", "credits": 1.5, "min_grade": "C"},
    "BUS-D 271": {"title": "Global Business Analysis", "credits": 1.5, "min_grade": "C"},
}

COURSE_CATALOG = {
    # I-Core
    "BUS-F 370": {"title": "I-Core Finance Component", "credits": 3},
    "BUS-M 370": {"title": "I-Core Marketing Component", "credits": 3},
    "BUS-P 370": {"title": "I-Core Operations Component", "credits": 3},
    "BUS-Z 370": {"title": "I-Core Leadership Component", "credits": 3},

    # Post I-Core Required
    "BUS-Z 302": {"title": "Leadership & Management", "credits": 3},
    "BUS-L 375": {"title": "Business Ethics", "credits": 3},

    # Accounting
    "BUS-A 311": {"title": "Intermediate Accounting", "credits": 3},
    "BUS-A 312": {"title": "Intermediate Accounting II", "credits": 3},
    "BUS-A 314": {"title": "Cost Accounting", "credits": 3},
    "BUS-A 325": {"title": "Managing Organizational Innovations", "credits": 3},
    "BUS-A 329": {"title": "Federal Income Taxation", "credits": 3},
    "BUS-A 420": {"title": "Advanced Accounting", "credits": 3},
    "BUS-A 422": {"title": "Auditing", "credits": 3},
    "BUS-A 437": {"title": "Advanced Accounting II", "credits": 3},
    "BUS-A 440": {"title": "Strategic Topics in Accounting", "credits": 3},

    # Finance
    "BUS-F 303": {"title": "Corporate Finance", "credits": 3},
    "BUS-F 305": {"title": "Investments", "credits": 3},
    "BUS-F 307": {"title": "Real Estate Finance", "credits": 3},
    "BUS-F 317": {"title": "Entrepreneurial Finance", "credits": 3},
    "BUS-F 325": {"title": "International Finance", "credits": 3},
    "BUS-F 334": {"title": "Fixed Income Securities", "credits": 3},
    "BUS-F 335": {"title": "Equity Analysis", "credits": 3},
    "BUS-F 402": {"title": "Advanced Financial Management", "credits": 3},
    "BUS-F 420": {"title": "Financial Strategy", "credits": 3},
    "BUS-F 421": {"title": "Portfolio Management", "credits": 3},

    # Marketing
    "BUS-M 303": {"title": "Marketing Research", "credits": 3},
    "BUS-M 330": {"title": "Professional Sales", "credits": 3},
    "BUS-M 344": {"title": "Consumer Behavior", "credits": 3},
    "BUS-M 346": {"title": "Marketing Strategy", "credits": 3},
    "BUS-M 405": {"title": "Marketing Analytics", "credits": 3},
    "BUS-M 415": {"title": "Digital Marketing", "credits": 3},
    "BUS-M 419": {"title": "Social Media Marketing", "credits": 3},
    "BUS-M 422": {"title": "Brand Management", "credits": 3},
    "BUS-M 428": {"title": "Digital & Social Media Marketing", "credits": 3},
    "BUS-M 429": {"title": "Services Marketing", "credits": 3},
    "BUS-M 431": {"title": "International Marketing", "credits": 3},
    "BUS-M 432": {"title": "Advanced Digital Marketing", "credits": 3},
    "BUS-M 450": {"title": "Marketing Capstone", "credits": 3},

    # Management
    "BUS-J 285": {"title": "Organizational Behavior (Kelley)", "credits": 3},
    "BUS-Z 340": {"title": "Management of Organizations", "credits": 3},
    "BUS-Z 404": {"title": "International Business Strategy", "credits": 3},
    "BUS-Z 447": {"title": "Strategic Management", "credits": 3},
    "BUS-W 212": {"title": "Entrepreneurial Pathways", "credits": 3},
    "BUS-W 235": {"title": "Opportunity Evaluation", "credits": 3},
    "BUS-W 313": {"title": "Sustaining Entrepreneurial Ventures", "credits": 3},
    "BUS-W 406": {"title": "Strategy for Innovators", "credits": 3},
    "BUS-W 430": {"title": "Strategic Issues in Management", "credits": 3},

    # Supply Chain/Operations
    "BUS-P 319": {"title": "Supply Chain Management", "credits": 3},
    "BUS-P 320": {"title": "Operations Management", "credits": 3},
    "BUS-P 429": {"title": "Advanced Supply Chain Management", "credits": 3},
    "BUS-P 431": {"title": "Logistics Management", "credits": 3},
    "BUS-S 400": {"title": "Service Operations", "credits": 3},

    # Information Systems
    "BUS-S 302": {"title": "Information Systems for Business", "credits": 3},
    "BUS-S 305": {"title": "Database Management", "credits": 3},
    "BUS-S 307": {"title": "Business Intelligence & Analytics", "credits": 3},
    "BUS-S 308": {"title": "Enterprise Systems", "credits": 3},
    "BUS-S 310": {"title": "Systems Analysis & Design", "credits": 3},
    "BUS-S 326": {"title": "Social Media & Digital Strategy", "credits": 3},
    "BUS-K 353": {"title": "Systems Analysis for Business", "credits": 3},

    # Economics/Analytics
    "BUS-G 202": {"title": "Business, Government & Society", "credits": 3},
    "BUS-G 303": {"title": "Microeconomic Analysis", "credits": 3},
    "BUS-G 345": {"title": "Industrial Organization", "credits": 3},
    "BUS-G 350": {"title": "Business Analytics", "credits": 3},
    "BUS-G 492": {"title": "Analytics Capstone", "credits": 3},
    "BUS-G 494": {"title": "Economic Consulting Capstone", "credits": 3},

    # Global/International
    "BUS-D 311": {"title": "Global Business Strategy", "credits": 3},
    "BUS-D 312": {"title": "International Business Operations", "credits": 3},
}

MAJOR_REQUIREMENTS = {
    "Finance": ["BUS-A 310", "BUS-F 303", "BUS-F 305"],
    "Marketing": ["BUS-M 300", "BUS-M 303"],
    "Management": ["BUS-Z 302", "BUS-Z 340"],
    "Operations": ["BUS-P 301", "BUS-P 404"],
    "Accounting": ["BUS-A 311", "BUS-A 312"],
    "Information Systems": ["BUS-K 303", "BUS-K 353"],
    "Entrepreneurship": ["BUS-W 311", "BUS-W 340"],
    "Economic Consulting": ["ECON-B 252", "ECON-E 321", "BUS-G 303"],
}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_course_title(course_code: str) -> str:
    """Get full course title from catalog, or return code if not found."""
    normalized = normalize_course_code(course_code)
    course_info = COURSE_CATALOG.get(normalized)
    if course_info:
        return f"{normalized} — {course_info['title']}"
    # Fallback: check I-CORE requirements
    icore_info = ICORE_REQUIREMENTS.get(normalized)
    if icore_info:
        return f"{normalized} — {icore_info['title']}"
    # If not found, return code with generic message
    return normalized


def sanitize_input(text: str, max_length: int = 1000) -> str:
    """Sanitize user input to prevent XSS and injection attacks."""
    if not isinstance(text, str):
        return ""

    # Limit length
    text = text[:max_length]

    # Remove dangerous characters and patterns
    text = re.sub(r'[<>{}]', '', text)  # Remove brackets
    text = re.sub(r'javascript:', '', text, flags=re.IGNORECASE)  # Remove javascript:
    text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)  # Remove event handlers

    return text.strip()


def grade_rank(grade: str) -> int:
    """Convert letter grade to numeric rank for comparison."""
    order = ["F", "D", "D+", "C-", "C", "C+", "B-", "B", "B+", "A-", "A", "A+"]
    normalized = grade.strip().upper()
    try:
        return order.index(normalized)
    except ValueError:
        return -1


def grade_at_least(actual: str, minimum: str) -> bool:
    """Check if actual grade meets minimum requirement."""
    return grade_rank(actual) >= grade_rank(minimum)


def normalize_course_code(raw_code: str) -> str:
    """Normalize course code to standard format (e.g., BUS-A 304)."""
    text = re.sub(r"\s+", " ", raw_code.strip().upper())
    match = re.match(r"^([A-Z]{2,4})\s*-?\s*([A-Z]?)\s*(\d{3})$", text)
    if not match:
        return text
    dept, section, number = match.groups()
    return f"{dept}-{section + ' ' if section else ''}{number}".replace("- ", "-")


def parse_transcript_text(text: str) -> dict[str, Any]:
    """Extract course codes, grades, and student metadata from transcript text."""
    courses: list[dict[str, str]] = []
    notes: list[str] = []
    seen: set[str] = set()

    # Extract student metadata
    student_name = None
    matriculation_year = None
    expected_graduation = None
    gpa = None
    total_credits = 0
    declared_majors = []
    career_interest = None
    program = None
    advisor = None
    honors_program = None
    cpa_note = None
    current_semester = None

    # Lines to skip (headers, footers, separators)
    skip_patterns = [
        "REGISTRAR", "ACADEMIC", "INDIANA UNIVERSITY", "========",
        "---", "Semester Credits", "Cumulative Credits", "DEGREE", "PROGRESS",
        "INTERESTS", "NOTES", "END OF", "Date of Birth:", "Student ID:"
    ]

    lines = text.splitlines()
    print(f"[PARSE] Total lines in transcript: {len(lines)}")

    for i, line in enumerate(lines):
        line_stripped = line.strip()

        # Extract student name (usually near top, after "Student Name:")
        if "Student Name:" in line and not student_name:
            name_match = re.search(r"Student Name:\s*(.+?)(?:\s{2,}|$)", line)
            if name_match:
                student_name = name_match.group(1).strip()
                print(f"[PARSE] Found student name: {student_name}")

        # Extract matriculation year
        if "Matriculation Term:" in line and not matriculation_year:
            term_match = re.search(r"(\d{4})", line)
            if term_match:
                matriculation_year = int(term_match.group(1))
                print(f"[PARSE] Found matriculation year: {matriculation_year}")

        # Extract expected graduation
        if "Expected Graduation:" in line and not expected_graduation:
            grad_match = re.search(r"Expected Graduation:\s*(.+?)(?:\s{2,}|$)", line)
            if grad_match:
                expected_graduation = grad_match.group(1).strip()
                print(f"[PARSE] Found expected graduation: {expected_graduation}")

        # Extract program
        if "Program:" in line and not program:
            prog_match = re.search(r"Program:\s*(.+?)(?:\s{2,}|$)", line)
            if prog_match:
                program = prog_match.group(1).strip()
                print(f"[PARSE] Found program: {program}")

        # Extract advisor
        if "Advisor:" in line and not advisor:
            adv_match = re.search(r"Advisor:\s*(.+?)(?:\s{2,}|$)", line)
            if adv_match:
                advisor = adv_match.group(1).strip()
                print(f"[PARSE] Found advisor: {advisor}")

        # Extract declared majors from notes section
        if "Declared Major:" in line and not declared_majors:
            major_match = re.search(r"Declared Major:\s*(.+?)(?:\n|$)", line)
            if major_match:
                major_text = major_match.group(1).strip()
                # Split by comma or "and"
                majors = re.split(r',|\s+and\s+', major_text, flags=re.IGNORECASE)
                # Clean up each major - remove parentheses and extra text
                declared_majors = []
                for m in majors:
                    m = m.strip()
                    # Remove anything in parentheses (like "double major")
                    m = re.sub(r'\s*\([^)]*\)', '', m).strip()
                    if m:
                        declared_majors.append(m)
                print(f"[PARSE] Found declared majors: {declared_majors}")

        # Extract intended major (for pre-business students)
        if "Intended Major:" in line and not declared_majors:
            major_match = re.search(r"Intended Major:\s*(.+?)(?:\n|$)", line)
            if major_match:
                major_text = major_match.group(1).strip()
                majors = re.split(r',|\s+and\s+|\s+or\s+', major_text, flags=re.IGNORECASE)
                declared_majors = []
                for m in majors:
                    m = m.strip()
                    m = re.sub(r'\s*\([^)]*\)', '', m).strip()
                    if m and m.lower() not in ["none", "not declared"]:
                        declared_majors.append(m)
                print(f"[PARSE] Found intended majors: {declared_majors}")

        # Extract possible co-major/minor
        if "Possible Co-Major:" in line or "Co-Major:" in line:
            co_major_match = re.search(r"(?:Possible )?Co-Major:\s*(.+?)(?:\n|$)", line)
            if co_major_match:
                co_major_text = co_major_match.group(1).strip()
                if co_major_text.lower() not in ["none", "none declared yet", "not declared"]:
                    co_majors = re.split(r',|\s+and\s+', co_major_text, flags=re.IGNORECASE)
                    for cm in co_majors:
                        cm = cm.strip()
                        cm = re.sub(r'\s*\([^)]*\)', '', cm).strip()
                        if cm and cm not in declared_majors:
                            declared_majors.append(cm)
                    print(f"[PARSE] Found co-majors, updated majors: {declared_majors}")

        # Extract career interest
        if "Career Interest:" in line and not career_interest:
            interest_match = re.search(r"Career Interest:\s*(.+?)(?:\n|$)", line)
            if interest_match:
                career_interest = interest_match.group(1).strip()
                print(f"[PARSE] Found career interest: {career_interest}")

        # Extract honors program status
        if "Honors Program:" in line and honors_program is None:
            honors_match = re.search(r"Honors Program:\s*(.+?)(?:\n|$)", line)
            if honors_match:
                honors_program = honors_match.group(1).strip()
                print(f"[PARSE] Found honors program: {honors_program}")

        # Extract CPA note
        if "CPA Note:" in line and not cpa_note:
            cpa_match = re.search(r"CPA Note:\s*(.+?)(?:\n|$)", line)
            if cpa_match:
                cpa_note = cpa_match.group(1).strip()
                print(f"[PARSE] Found CPA note: {cpa_note}")

        # Extract GPA (take the latest cumulative GPA)
        if "Cumulative GPA:" in line:
            gpa_match = re.search(r"GPA:\s*([\d.]+)", line)
            if gpa_match:
                try:
                    gpa = float(gpa_match.group(1))
                    print(f"[PARSE] Found GPA: {gpa}")
                except ValueError:
                    pass

        # Skip empty or short lines
        if not line_stripped or len(line_stripped) < 5:
            continue

        # Skip header/footer lines
        if any(skip.upper() in line_stripped.upper() for skip in skip_patterns):
            continue

        # Detect semester headers (e.g., "--- FALL 2021 ---")
        semester_match = re.match(r'^-+\s*(FALL|SPRING|SUMMER)\s+(\d{4})\s*-*$', line_stripped, re.IGNORECASE)
        if semester_match:
            current_semester = f"{semester_match.group(1).title()} {semester_match.group(2)}"
            print(f"[PARSE] Detected semester: {current_semester}")
            continue

        # Find course codes - handle multiple formats
        # Matches: ENG-W 131, ENG W 131, ENGW131, ENG-W131
        course_match = re.search(
            r"\b((?:BUS|ECON|ENG|MATH|STAT|PSY|HIST|MUS|CLAS|BIO)[-\s]?[A-Z]?\s*\d{3})\b",
            line_stripped,
            re.IGNORECASE
        )

        if not course_match:
            continue

        code = normalize_course_code(course_match.group(1))

        # Skip "NOT YET TAKEN" courses from degree progress notes
        if "NOT YET TAKEN" in line_stripped or "NOT TAKEN" in line_stripped:
            continue

        # Skip if we already have this course
        if code in seen:
            continue

        # Extract credits (must be present for a real course entry)
        credits = 0
        credits_match = re.search(r"(\d+(?:\.\d)?)\s*cr", line_stripped, re.IGNORECASE)
        if not credits_match:
            continue  # Skip if no credits found - not a real course entry

        try:
            credits = float(credits_match.group(1))
            total_credits += credits
        except ValueError:
            continue

        # Extract grade - MUST come after credits for real course entries
        # Pattern: look in the text AFTER "cr" marker for a grade letter
        grade = ""
        text_after_credits = line_stripped[credits_match.end():].strip()

        if text_after_credits:  # There should be something after credits (the grade)
            grade_match = re.match(r"([A-DF][\+\-]?)", text_after_credits.upper())
            if grade_match:
                grade = grade_match.group(1).upper()

        # Only add course if it has a grade (completed courses)
        if not grade:
            print(f"[PARSE] Skipping {code} - no grade found (incomplete entry)")
            continue

        # Extract course title (text between code and credits)
        title = ""
        code_end = course_match.end()
        credits_start = credits_match.start()
        if credits_start > code_end:
            title = line_stripped[code_end:credits_start].strip()
            # Clean up multiple spaces
            title = re.sub(r"\s+", " ", title)

        # Find semester/term if present (usually in header, not details)
        term = ""

        # Add course
        courses.append({
            "code": code,
            "title": title,
            "grade": grade,
            "term": term,
            "credits": credits
        })
        seen.add(code)
        print(f"[PARSE] Found course: {code} ({grade}) {credits}cr - {title}")

    if not courses:
        notes.append("No course codes found in transcript. Please check the format.")
        print("[PARSE] WARNING: No courses found!")
    else:
        print(f"[PARSE] Total courses extracted: {len(courses)}")
        print(f"[PARSE] Total credits: {total_credits}")

    return {
        "courses": courses,
        "notes": notes,
        "metadata": {
            "student_name": student_name or "Student",
            "matriculation_year": matriculation_year,
            "expected_graduation": expected_graduation,
            "gpa": gpa,
            "total_credits": total_credits,
            "declared_majors": declared_majors,
            "career_interest": career_interest,
            "program": program,
            "advisor": advisor,
            "honors_program": honors_program,
            "cpa_note": cpa_note
        }
    }


def extract_text_from_upload(uploaded_file) -> str:
    """Extract text from PDF or text file upload."""
    filename = (uploaded_file.filename or "").lower()
    data = uploaded_file.read()
    uploaded_file.stream.seek(0)

    if filename.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    return data.decode("utf-8", errors="ignore")


def transcript_courses_map(parsed_transcript: dict[str, Any]) -> dict[str, str]:
    """Convert parsed transcript to code -> grade mapping."""
    course_map: dict[str, str] = {}
    for course in parsed_transcript.get("courses", []):
        code = course.get("code", "").strip()
        grade = course.get("grade", "").strip().upper()
        if code:
            course_map[code] = grade or course_map.get(code, "")
    return course_map


def icore_prereq_completion(course_map: dict[str, str]) -> tuple[float, list[str]]:
    """Calculate I-Core prerequisite completion percentage and missing courses."""
    completed = 0
    missing: list[str] = []

    for code, meta in ICORE_REQUIREMENTS.items():
        grade = course_map.get(code)
        if grade and grade_at_least(grade, meta["min_grade"]):
            completed += 1
        else:
            missing.append(code)

    total = len(ICORE_REQUIREMENTS)
    percent = (completed / total * 100) if total > 0 else 0
    return percent, missing


def icore_complete(course_map: dict[str, str]) -> bool:
    """Check if all I-Core prerequisites are complete."""
    percent, _ = icore_prereq_completion(course_map)
    return percent == 100


def call_ai(system_prompt: str, user_prompt: str, max_tokens: int = 800) -> dict:
    """Call AI API - tries Gemini first (6s timeout), falls back to Groq."""
    result = {
        "reply": "",
        "model": "unknown",
        "error": None
    }

    print("\n" + "="*80)
    print(f"[AI] call_ai() invoked")
    print(f"[AI] GROQ_API_KEY_1 present: {bool(GROQ_API_KEY)}")
    print(f"[AI] GROQ_API_KEY_2 present: {bool(GROQ_API_KEY_2)}")
    print(f"[AI] GROQ_API_KEY_3 present: {bool(GROQ_API_KEY_3)}")
    print(f"[AI] GEMINI_AVAILABLE: {GEMINI_AVAILABLE} (primary)")
    print(f"[AI] RAG_CONTEXT loaded: {bool(RAG_CONTEXT)} ({len(RAG_CONTEXT)} chars)")
    print("="*80 + "\n")

    # Enhance system prompt with RAG context if available
    enhanced_system = system_prompt
    if RAG_CONTEXT:
        # Use first 8KB to provide more curriculum context (8KB ~2000 tokens)
        # Gemini is unlimited so we can be more generous here
        rag_core = RAG_CONTEXT[:8000]
        enhanced_system = f"{system_prompt}\n\n---\nKELLEY CURRICULUM:\n{rag_core}"
        print(f"[AI] RAG context attached: {len(rag_core)} chars (from {len(RAG_CONTEXT)} total)")
    else:
        print(f"[AI] WARNING: No RAG context available")

    # Try Groq FIRST (more reliable) with fallback to Gemini if needed
    groq_keys = [
        ("Key 1", GROQ_API_KEY),
        ("Key 2", GROQ_API_KEY_2),
        ("Key 3", GROQ_API_KEY_3)
    ]

    for key_name, groq_key in groq_keys:
        if not groq_key:
            continue

        try:
            print(f"[AI] Attempting Groq ({key_name})...")
            groq_payload = {
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": enhanced_system},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.5,
                "max_tokens": max_tokens,
            }

            print(f"[AI] Sending to Groq {key_name} (payload: {len(str(groq_payload))} chars)...")
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {groq_key}",
                    "Content-Type": "application/json",
                },
                json=groq_payload,
                timeout=10,
            )

            print(f"[AI] Groq {key_name} response status: {response.status_code}")

            if response.status_code != 200:
                print(f"[AI] Groq {key_name} error response: {response.text[:500]}")
                if response.status_code == 429:
                    print(f"[AI] {key_name} rate limited - trying next key...")
                    continue

            response.raise_for_status()

            data = response.json()
            result["reply"] = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            if result["reply"]:
                result["model"] = f"Groq {GROQ_MODEL}"
                print(f"[AI] SUCCESS: Groq {key_name} returned {len(result['reply'])} chars")
                print("="*80 + "\n")
                return result
            else:
                print(f"[AI] Groq {key_name} returned empty response")

        except requests.exceptions.Timeout:
            print(f"[AI] Groq {key_name}: TIMEOUT (>10s)")
        except requests.exceptions.RequestException as e:
            error_text = str(e)
            print(f"[AI] Groq {key_name}: REQUEST ERROR: {error_text[:200]}")
            if "429" in error_text or "rate" in error_text.lower():
                print(f"[AI] {key_name} rate limited - trying next key...")
                continue
        except Exception as e:
            print(f"[AI] Groq {key_name}: EXCEPTION: {type(e).__name__}: {e}")

    print(f"[AI] All Groq keys exhausted - falling back to Gemini")

    # Fallback to Gemini if all Groq keys fail
    gemini_models = [
        "gemini-2.5-flash",        # Try this first (free tier)
        "gemini-2.5-flash-lite",   # Then this (free tier)
        "gemini-1.5-flash",        # Then this (free tier)
    ]

    for model_name in gemini_models:
        try:
            print(f"[AI] Attempting Gemini ({model_name}, 4s timeout)...")
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel(model_name)

            full_prompt = f"{enhanced_system}\n\n{user_prompt}"

            gemini_result = {"response": None, "error": None}

            def call_gemini():
                try:
                    print(f"[AI] Gemini thread: calling generate_content...")
                    response = model.generate_content(
                        full_prompt,
                        generation_config=genai.types.GenerationConfig(
                            max_output_tokens=max_tokens,
                            temperature=0.5,
                        )
                    )
                    if response and response.text:
                        gemini_result["response"] = response.text
                        print(f"[AI] Gemini thread: got {len(response.text)} chars")
                    else:
                        gemini_result["error"] = "Empty response"
                except Exception as e:
                    gemini_result["error"] = str(e)
                    print(f"[AI] Gemini thread error: {e}")

            thread = threading.Thread(target=call_gemini, daemon=False)
            thread.start()
            thread.join(timeout=4.0)  # Short timeout: 4 seconds

            if gemini_result["response"]:
                result["reply"] = gemini_result["response"]
                result["model"] = f"Gemini {model_name}"
                print(f"[AI] SUCCESS: Gemini {model_name} returned in time")
                print("="*80 + "\n")
                return result
            elif thread.is_alive():
                print(f"[AI] Gemini {model_name}: TIMEOUT (>4s)")
            else:
                print(f"[AI] Gemini {model_name} failed: {gemini_result.get('error', 'unknown')}")
                # Try next model
                continue

        except Exception as e:
            print(f"[AI] Gemini {model_name} error: {type(e).__name__}: {str(e)[:100]}")
            # Try next model
            continue

    print(f"[AI] All Gemini models exhausted - falling back to Groq")

    # All failed
    print(f"[AI] FAILED: All AI services unavailable")
    print(f"[AI] GROQ_KEY_1 valid: {bool(GROQ_API_KEY)}")
    print(f"[AI] GROQ_KEY_2 valid: {bool(GROQ_API_KEY_2)}")
    print(f"[AI] GROQ_KEY_3 valid: {bool(GROQ_API_KEY_3)}")
    print(f"[AI] GEMINI available: {GEMINI_AVAILABLE}, key valid: {bool(GEMINI_API_KEY)}")
    print("="*80 + "\n")

    result["reply"] = "AI temporarily unavailable - all services rate limited or unavailable. Try again in 30+ minutes."
    result["model"] = "none"

    return result


def call_groq(profile: dict, parsed_transcript: dict) -> dict:
    """Wrapper function - calls call_ai and returns formatted result."""
    course_map = transcript_courses_map(parsed_transcript)
    icore_percent, missing_icore = icore_prereq_completion(course_map)

    # Extract profile data
    total_credits = profile.get('total_credits', 0)
    gpa = profile.get('gpa', 0)
    student_name = profile.get('student_name', 'Student')
    declared_majors = profile.get('declared_majors', [])
    if isinstance(declared_majors, str):
        declared_majors = [m.strip() for m in declared_majors.split(',')]

    career_interests = profile.get('career_interest', 'Not specified')
    matriculation_year = profile.get('matriculation_year', '')
    expected_graduation = profile.get('expected_graduation', '')

    # Format major string for display
    majors_str = ', '.join(declared_majors) if declared_majors else 'Undeclared'

    # Format graduation year
    grad_year = expected_graduation or matriculation_year or 'Not specified'

    # Build completed courses detail
    courses = parsed_transcript.get('courses', [])
    completed_courses_list = [f"{c['code']} ({c['grade']})" for c in courses]
    completed_courses_detail = '\n'.join(completed_courses_list) if completed_courses_list else 'No courses completed'

    # Determine student status based on credits
    if total_credits < 30:
        student_status = "Pre-Business / Freshman"
        status_detail = "Focus on I-Core foundation."
    elif total_credits < 60:
        student_status = "Sophomore"
        status_detail = f"Building I-Core ({icore_percent:.0f}% complete)."
    elif total_credits < 90:
        student_status = "Junior"
        status_detail = "Ready for major-specific coursework."
    else:
        student_status = "Senior"
        status_detail = "Prioritize remaining major requirements."

    # Risk detection
    risk_flags = []
    if gpa and gpa < 2.75:
        risk_flags.append("⚠ Low GPA")
    if total_credits > 30 and icore_percent < 30:
        risk_flags.append("⚠ Behind on I-Core")
    risk_alert = "" if not risk_flags else "\n".join(risk_flags)

    print(f"[GROQ] Status: {student_status} | GPA: {gpa} | Credits: {total_credits}")
    print(f"[GROQ] Majors: {majors_str}")
    print(f"[GROQ] Risks: {risk_flags}\n")

    system_prompt = f"""You are Kelley Compass AI, an expert academic advisor at IU Kelley.

STUDENT: {student_status}
- Major(s): {majors_str}
- GPA: {gpa or 'N/A'} | Credits: {total_credits} | I-Core: {icore_percent:.0f}%
- Goal: {career_interests or 'Not specified'}
- Graduating: {grad_year}
{f'- ALERTS: {risk_alert}' if risk_alert else ''}

CONTEXT: {status_detail}

TASK: Recommend 3-5 specific next courses. PROVIDE DETAILED EXPLANATIONS (not one sentence).

IMPORTANT - DETAILED RESPONSES REQUIRED:
- Always include the FULL COURSE NAME alongside the code (e.g., "BUS-F 303 (Corporate Finance)")
- Explain WHAT each course covers (2-3 sentence description)
- Explain WHY it's needed (prerequisites, major requirements, career goal alignment)
- Reference their specific transcript when possible
- Be conversational but informative

RULES:
1. NO courses already completed
2. NO I-Core if complete
3. ONLY major requirements if student has declared major
4. Must provide substantial explanation for each course
5. NO vague phrases like "and other requirements"
6. ALWAYS include course titles - never list codes alone

FORMAT EXAMPLE:
BUS-F 303 (Corporate Finance) — This course covers valuation methods, capital structure, and financial decision-making. You need this because it's required for the Finance major and foundational before advanced finance courses. Credits: 3

(Make each recommendation substantive and helpful)"""

    user_prompt = f"""STUDENT: {student_name}
MAJOR(S): {majors_str}
GRADUATING: {grad_year}
GPA: {profile.get('gpa', 'N/A')}

CREDIT STATUS:
- Total Completed: {profile.get('total_credits', 0)}/120 credits
- Remaining: {120 - profile.get('total_credits', 0)} credits

COURSES ALREADY COMPLETED:
{completed_courses_detail}

"""

    # Determine if student should focus on I-Core vs major courses
    # Pre-Business/Freshman students (<30 cr) MUST complete I-Core first, regardless of intended majors
    pre_business_or_incomplete_icore = (total_credits < 30) or (icore_percent < 100 and total_credits < 90)

    if pre_business_or_incomplete_icore:
        # Student must focus on I-Core (even if they have intended majors)
        icore_status = '✓ COMPLETE' if icore_percent == 100 else f'{icore_percent:.0f}% complete - still need: {", ".join(missing_icore[:5])}'
        user_prompt += f"""I-CORE FOCUS: This student is Pre-Business/building I-Core.
I-CORE STATUS: {icore_status}

PRIORITY: Recommend remaining I-Core prerequisite courses ONLY.
Their intended majors ({majors_str}) can be addressed after I-Core is complete.
NEVER recommend major courses yet - focus on I-Core."""
    else:
        # Student is past I-Core, focus on major requirements
        user_prompt += f"""MAJOR REQUIREMENTS FOCUS: This student has completed I-Core.
Recommend courses from their declared major(s): {majors_str}"""

    user_prompt += f"""

QUESTION: What courses should I take next semester?

REQUIRED FORMAT - EXACTLY like this:
BUS-C 204 — Satisfies writing prerequisite for further business courses. (3 cr)
BUS-K 303 — Required for Information Systems courses. (3 cr)
ECON-Z 202 — Broadens economics foundation. (3 cr)

STRICT RULES:
1. ONLY list courses NOT already completed (see list above)
2. List EXACTLY 3-5 courses, one per line
3. Each line: COURSE-CODE — reason. (Credits)
4. Be SPECIFIC - no "other requirements" or generic phrases
5. Reference their grades and completed courses when explaining why"""

    # Call unified AI function (tries Gemini, falls back to Groq)
    # Use higher max_tokens to allow for detailed, substantive responses
    result = call_ai(system_prompt, user_prompt, max_tokens=1200)

    return {
        "reply": result["reply"],
        "model": result["model"],
        "icore_percent": icore_percent,
        "missing_icore": missing_icore,
        "error": result.get("error")
    }


def extract_recommendations(response_text: str) -> list[dict]:
    """Parse LLM response into structured recommendation cards."""
    recommendations = []

    # Look for course codes in the response (BUS-X 123 format)
    # Pattern: COURSE-CODE — description. (X cr)
    # Or: - COURSE-CODE: description (X cr)
    # Or just: COURSE-CODE description (X cr)

    pattern = r'(?:^|\n)[-\s]*(?:BUS|ECON|ENG|MATH|STAT)[-\s]?[A-Z]?\s*\d{3}(?:\s|[-–—]|:)(.+?)(\d+\.?\d*)\s*(?:credit|cr|credi)'

    matches = re.finditer(pattern, response_text, re.MULTILINE | re.IGNORECASE)
    seen_codes = set()

    for match in matches:
        # Extract course code from the matched text
        code_match = re.search(r'((?:BUS|ECON|ENG|MATH|STAT)[-\s]?[A-Z]?\s*\d{3})', match.group(0), re.IGNORECASE)
        if not code_match:
            continue

        code = normalize_course_code(code_match.group(1))

        # Skip duplicates
        if code in seen_codes:
            continue
        seen_codes.add(code)

        title = match.group(1).strip()[:100]  # Take first 100 chars as title
        credits = float(match.group(2))

        recommendations.append({
            "code": code,
            "title": title,
            "reason": "See detailed analysis above",
            "credits": credits,
            "prerequisites_met": True,
            "warning": None
        })

    # If we found at least 3 recommendations, return them
    if len(recommendations) >= 3:
        return recommendations[:5]  # Max 5

    # If fewer than 3, show all found and add fallback
    if recommendations:
        recommendations.append({
            "code": "ASK",
            "title": "Questions?",
            "reason": "Ask me a follow-up question for more details",
            "credits": 0,
            "prerequisites_met": True,
            "warning": None
        })
        return recommendations

    # If no courses found, return fallback
    return [{
        "code": "CHAT",
        "title": "Chat with Advisor",
        "reason": f"Ask me a follow-up question. Response: {response_text[:150]}...",
        "credits": 0,
        "prerequisites_met": True,
        "warning": None
    }]


def fallback_recommendations(profile: dict, parsed_transcript: dict) -> dict:
    """Generate rule-based recommendations when API unavailable."""
    course_map = transcript_courses_map(parsed_transcript)
    icore_percent, missing_icore = icore_prereq_completion(course_map)
    icore_ready = icore_complete(course_map)

    response = {
        "reply": "",
        "icore_percent": icore_percent,
        "icore_ready": icore_ready,
        "missing_icore": missing_icore,
    }

    if not icore_ready:
        response["reply"] = f"Based on your transcript, you've completed {icore_percent:.0f}% of I-Core prerequisites.\n\nMissing courses:\n" + "\n".join(missing_icore[:5])
    else:
        majors = profile.get("declared_majors", [])
        response["reply"] = f"You're I-Core eligible! Next, focus on major requirements:\n"
        for major in majors:
            if major in MAJOR_REQUIREMENTS:
                courses = MAJOR_REQUIREMENTS[major]
                response["reply"] += f"\n{major}: {', '.join(courses[:2])}"

    return response


def extract_recommendations(response_text: str) -> list[dict]:
    """Parse LLM response into structured recommendation cards."""
    recommendations = []

    # Try to extract courses from the response
    # Looks for patterns like "1. BUS-A 304 — Major — Credits"
    lines = response_text.split('\n')

    for line in lines:
        line = line.strip()
        if not line or not re.match(r'^\d+\.', line):
            continue

        # Pattern: "1. BUS-A 304 — Major — 3 cr" or "BUS-A 304 — Title — 3"
        course_match = re.search(
            r'((?:BUS|ECON|ENG|MATH|STAT)-[A-Z]?\s*\d{3})',
            line,
            re.IGNORECASE
        )

        if not course_match:
            continue

        code = normalize_course_code(course_match.group(1))

        # Extract title and credits if available
        parts = line.split('—')
        title = parts[1].strip() if len(parts) > 1 else "Course"
        credits_match = re.search(r'(\d+(?:\.\d)?)\s*cr', line, re.IGNORECASE) or re.search(r'(\d+)', parts[-1] if len(parts) > 2 else '')
        credits = float(credits_match.group(1)) if credits_match else 3

        # Look for "Why:" on next lines
        reason = ""
        line_idx = lines.index(line) if line in lines else -1
        if line_idx >= 0 and line_idx + 1 < len(lines):
            next_line = lines[line_idx + 1].strip()
            if next_line.startswith('Why:') or next_line.startswith('Reason:'):
                reason = next_line.replace('Why:', '').replace('Reason:', '').strip()[:150]

        recommendations.append({
            "code": code,
            "title": title[:80],
            "reason": reason or "Required for your major",
            "credits": credits,
            "prerequisites_met": True,
            "warning": None
        })

    # Return what we found, or generic if none
    return recommendations if recommendations else []


# ============================================================================
# ROUTES
# ============================================================================

@app.route("/")
def index():
    """Serve main chatbot page."""
    return render_template("index.html")


@app.route("/api/demo-transcripts", methods=["GET"])
def demo_transcripts():
    """List available demo transcripts."""
    demo_dir = BASE_DIR / "demo_data"
    transcripts = []

    if demo_dir.exists():
        for file in sorted(demo_dir.glob("*.txt")):
            # Parse filename: transcript_01_prefreshman_emma_chen.txt
            name = file.stem.replace("transcript_", "").replace("_", " ").title()
            transcripts.append({
                "id": file.stem,
                "filename": file.name,
                "name": name
            })

    return jsonify({"transcripts": transcripts})


@app.route("/api/load-demo/<demo_id>", methods=["GET"])
def load_demo(demo_id: str):
    """Load a demo transcript by ID."""
    demo_file = BASE_DIR / "demo_data" / f"{demo_id}.txt"

    if not demo_file.exists():
        return jsonify({"error": "Demo transcript not found"}), 404

    try:
        with open(demo_file, "r", encoding="utf-8") as f:
            transcript_text = f.read()

        return jsonify({
            "transcript_text": transcript_text,
            "filename": demo_file.name
        })
    except Exception as e:
        print(f"Error loading demo: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/chat", methods=["POST"])
def chat():
    """Handle chat messages with transcript analysis and conversation history."""
    try:
        data = request.get_json()

        # Extract and sanitize data from request
        profile = data.get("profile", {})
        transcript_text = data.get("transcript_text", "")
        user_message = sanitize_input(data.get("message", ""))  # SANITIZE
        conversation_history = data.get("conversation_history", [])

        # Initialize session conversation history if needed
        if "conversation_history" not in session:
            session["conversation_history"] = []

        # PARSE MODE: If transcript provided and message is parse request
        if transcript_text and "parse" in user_message.lower():
            parsed_transcript = parse_transcript_text(transcript_text)
            metadata = parsed_transcript.get("metadata", {})
            course_map = transcript_courses_map(parsed_transcript)
            icore_percent, missing_icore = icore_prereq_completion(course_map)

            # Build parsed profile with metadata
            parsed_profile = {
                "student_name": metadata.get("student_name", "Student"),
                "matriculation_year": metadata.get("matriculation_year"),
                "current_year": profile.get("current_year_in_school", "Unknown"),
                "declared_majors": metadata.get("declared_majors", []) or profile.get("declared_majors", []),
                "career_interests": metadata.get("career_interest", "") or profile.get("career_interests", ""),
                "courses": parsed_transcript.get("courses", []),
                "icore_percent": icore_percent,
                "icore_completed": sum(1 for c in parsed_transcript.get("courses", []) if c["code"] in ICORE_REQUIREMENTS),
                "gpa": metadata.get("gpa"),
                "total_credits": metadata.get("total_credits", 0),
                "expected_graduation": metadata.get("expected_graduation"),
                "program": metadata.get("program"),
                "advisor": metadata.get("advisor"),
                "honors_program": metadata.get("honors_program"),
                "cpa_note": metadata.get("cpa_note")
            }

            # Merge metadata into profile for Groq context
            enriched_profile = {**profile, **parsed_profile}

            # Generate recommendations
            result = call_groq(enriched_profile, parsed_transcript)
            recommendations = extract_recommendations(result["reply"])

            # Store in session
            session["parsed_transcript"] = parsed_transcript
            session["profile"] = enriched_profile
            session["analysis_done"] = True
            session["conversation_history"] = []

            return jsonify({
                "parsed_profile": parsed_profile,
                "recommendations": recommendations,
                "icore_percent": icore_percent,
                "icore_ready": icore_percent == 100
            })

        # Parse transcript if provided
        if transcript_text:
            parsed_transcript = parse_transcript_text(transcript_text)
        else:
            # Try to use previously parsed transcript from session
            parsed_transcript = session.get("parsed_transcript", {"courses": [], "notes": []})

        # Store in session for continuity
        session["parsed_transcript"] = parsed_transcript
        # NOTE: Don't store profile yet - wait until it's enriched with metadata

        # Initialize analysis flag
        if "analysis_done" not in session:
            session["analysis_done"] = False

        # If this is an initial request with transcript (first message or profile reset)
        if transcript_text and user_message and not session.get("analysis_done"):
            # Run initial analysis
            # Enrich profile with transcript metadata
            metadata = parsed_transcript.get("metadata", {})
            enriched_profile = {**profile}
            if metadata.get("student_name"):
                enriched_profile["student_name"] = metadata.get("student_name")
            if metadata.get("matriculation_year"):
                enriched_profile["matriculation_year"] = metadata.get("matriculation_year")
            if metadata.get("gpa"):
                enriched_profile["gpa"] = metadata.get("gpa")
            if metadata.get("total_credits"):
                enriched_profile["total_credits"] = metadata.get("total_credits")
            if metadata.get("declared_majors"):
                enriched_profile["declared_majors"] = metadata.get("declared_majors")
            if metadata.get("career_interest"):
                enriched_profile["career_interests"] = metadata.get("career_interest")
            if metadata.get("expected_graduation"):
                enriched_profile["expected_graduation"] = metadata.get("expected_graduation")
            if metadata.get("program"):
                enriched_profile["program"] = metadata.get("program")
            if metadata.get("advisor"):
                enriched_profile["advisor"] = metadata.get("advisor")
            if metadata.get("honors_program"):
                enriched_profile["honors_program"] = metadata.get("honors_program")
            if metadata.get("cpa_note"):
                enriched_profile["cpa_note"] = metadata.get("cpa_note")

            # NOW store the enriched profile in session for follow-up questions
            session["profile"] = enriched_profile

            result = call_groq(enriched_profile, parsed_transcript)
            session["analysis_done"] = True

            # Store in conversation history
            session["conversation_history"].append({
                "role": "user",
                "content": user_message
            })
            session["conversation_history"].append({
                "role": "assistant",
                "content": result["reply"]
            })

            course_map = transcript_courses_map(parsed_transcript)
            icore_percent, _ = icore_prereq_completion(course_map)

            return jsonify({
                "reply": result["reply"],
                "model": result.get("model", "unknown"),
                "is_analysis": True,
                "icore_percent": icore_percent,
                "icore_ready": icore_percent == 100
            })

        # For follow-up questions, include full conversation context
        if user_message and session.get("analysis_done"):
            profile = session.get("profile", {})
            parsed_transcript = session.get("parsed_transcript", {})
            course_map = transcript_courses_map(parsed_transcript)
            icore_percent, missing_icore = icore_prereq_completion(course_map)

            # Build detailed completed courses list with grades
            completed_course_details = []
            for course in parsed_transcript.get("courses", []):
                code = course.get("code", "")
                grade = course.get("grade", "")
                if code:
                    completed_course_details.append(f"{code} ({grade})")

            completed_courses_str = ", ".join(completed_course_details) or "None found"

            # Build missing major requirements
            declared_majors = profile.get("declared_majors", []) or []

            # Check what major requirements are missing
            finance_missing = []
            if 'Finance' in declared_majors:
                for code in ["BUS-F 303", "BUS-F 305", "BUS-F 402"]:
                    if code not in course_map:
                        finance_missing.append(code)

            accounting_missing = []
            if 'Accounting' in declared_majors:
                for code in ["BUS-A 329", "BUS-A 420", "BUS-A 422", "BUS-A 437", "BUS-A 440"]:
                    if code not in course_map:
                        accounting_missing.append(code)

            majors_str = ", ".join(declared_majors) if declared_majors else "Not declared"

            # Build context for system prompt
            if not declared_majors:
                # Student has no majors yet - show I-Core status
                major_context = f"I-Core: {icore_percent:.0f}% complete - Missing: {', '.join(missing_icore) if missing_icore else 'None'}"
            else:
                # Student has majors - show ONLY major requirements
                major_reqs = []
                if finance_missing:
                    major_reqs.append(f"Finance: {', '.join(finance_missing)}")
                if accounting_missing:
                    major_reqs.append(f"Accounting: {', '.join(accounting_missing)}")
                major_context = " | ".join(major_reqs) if major_reqs else "All major requirements complete!"

            # Build system prompt with detailed context
            system_prompt_text = """You are Kelley Compass AI, an expert academic advisor for Indiana University's Kelley School of Business.

Answer the student's question with specific details and relevant context from their transcript.

STUDENT: {student}
MAJOR(S): {majors}
GPA: {gpa}

REQUIREMENTS STATUS:
{major_requirements}

COMPLETED COURSES:
{completed}

GUIDELINES:
- Be specific: explain WHY each recommendation matters
- Include full course titles (e.g., "BUS-F 303 (Corporate Finance)")
- For course recommendations: mention prerequisites, course content, and how it fits their path
- For "what to take?": Give 4-5 courses with brief reasoning (1-2 sentences per course)
- Reference their actual grades and transcript when relevant
- Mention course sequencing or prerequisites if they matter
- Use Kelley Compass AI system.md knowledge to provide accurate information
- Goal: Help them understand their options, not just give a list
""".format(
                student=profile.get("student_name", "Student"),
                majors=majors_str,
                gpa=profile.get("gpa", "N/A"),
                major_requirements=major_context,
                completed=completed_courses_str
            )

            # Build user message with conversation context
            user_prompt_text = user_message

            try:
                # Use unified AI call (Gemini first, Groq fallback)
                # Increased max_tokens to 550 to allow detailed, specific responses
                result = call_ai(system_prompt_text, user_prompt_text, max_tokens=550)
                reply = result["reply"]
                model_used = result["model"]

                # Store in conversation history
                session["conversation_history"].append({
                    "role": "user",
                    "content": user_message
                })
                session["conversation_history"].append({
                    "role": "assistant",
                    "content": reply
                })

                return jsonify({
                    "reply": reply,
                    "model": model_used,
                    "is_analysis": False
                })
            except Exception as e:
                print(f"AI error: {e}")
                fallback_reply = "I'm having trouble reaching the advisor right now. Please try again or ask a different question."
                return jsonify({
                    "reply": fallback_reply,
                    "model": "none",
                    "is_analysis": False
                })

        return jsonify({"reply": "Please upload a transcript or ask a question.", "is_analysis": False})

    except Exception as e:
        print(f"Chat error: {e}")
        return jsonify({"error": str(e)}), 400


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"ok": True, "groq_configured": bool(GROQ_API_KEY)})


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") == "development"
    app.run(debug=debug, host="0.0.0.0", port=port)
