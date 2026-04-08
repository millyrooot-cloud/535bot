# Kelley Compass AI - Product Requirements Document (v3.0)

## Overview
Intelligent course planning chatbot for Indiana University's Kelley School of Business. Simple, intuitive, single-screen interface focused on transcript parsing and recommendations.

## Core Design Principle
**One screen, three states** — No mode switching, no hidden panels. The interface adapts based on what the student has done.

---

## Three-State Machine

### State 1: Landing (Initial Load)
- **Visual**: Giant drag-and-drop zone dominating the screen
- **Secondary**: Chat input below the drop zone (greyed out)
- **Call-to-action**: "Drop your transcript here or start typing"
- **Behavior**:
  - User can drag PDF/TXT file → triggers upload + State 2
  - User can type transcript directly → triggers parsing + State 2
  - User can ask question in chat → conversational mode (no parse confirmation)

### State 2: Parse Confirmation
- **Visual**: Clean card showing extracted data
- **Fields extracted**:
  - Student name
  - Matriculation year
  - Current year/program
  - Completed courses (course code + grade + term)
  - I-Core completion %
  - Declared major(s)
  - GPA (if available)
- **Actions available**:
  - "Fix something" — inline editing of misread fields
  - "Looks good" → proceeds to State 3
- **Error handling**: If parsing fails, show simplified form asking for key fields (major, year, semester planning)

### State 3: Recommendations + Chat
- **Visual Layout** (single scrollable area):
  1. Student profile header (compact) — name, major, I-Core status
  2. Recommendation cards (3-5 courses)
  3. Chat interface below (full conversational area)
- **No switching back** — once in State 3, chat is primary interface
- **Persistent context**: All conversation turns include parsed profile data

---

## Transcript Parsing Specification

### Input Formats Supported
- **PDF transcripts** (IU official format and others)
- **TXT paste** (any readable format)
- **Direct typing** (student can paste course list)

### Extraction Instructions
Extract and normalize these fields:

```
{
  "student_name": "string",
  "matriculation_year": "YYYY or 'Unknown'",
  "current_year": "Pre-Business | Freshman | Sophomore | Junior | Senior",
  "program": "string (e.g., 'Pre-Business')",

  "courses": [
    {
      "code": "DEPT-L NNN (normalized, e.g., 'BUS-A 304')",
      "grade": "A+ | A | A- | B+ | B | B- | C+ | C | C- | D+ | D | F",
      "term": "SEASON YYYY (e.g., 'Fall 2024') or empty string",
      "credits": "number or null"
    }
  ],

  "icore_status": {
    "completed_count": "number",
    "total_required": "19",
    "percent": "0-100",
    "ready": "boolean"
  },

  "majors": ["array of declared majors or empty"],
  "gpa": "number or null",
  "notes": ["any parsing issues or warnings"]
}
```

### Parsing Rules
1. **Course codes**: Extract DEPT-L NNN patterns (BUS-A 304, ECON-B 251, etc.)
2. **Grades**: Look for letter grades, prioritize A+/A-/B+/B- patterns before single letters
3. **Skip headers/footers**: Ignore "REGISTRAR", "ACADEMIC RECORD", separators, etc.
4. **Flexible spacing**: Handle "BUS-A 304", "BUSA304", "BUS A 304"
5. **I-Core calculation**: Check against ICORE_REQUIREMENTS mapping; count completed courses with passing grades (C minimum)
6. **Duplicate handling**: If same course appears twice, keep only the first (or highest grade)

---

## Confirmation Card Schema

### Display Format
```
┌─────────────────────────────────────┐
│ Emma Chen                    2024    │
│ Pre-Business → Finance Major         │
│ I-Core: 5 of 19 (26%)                │
├─────────────────────────────────────┤
│ Courses Found: 5                     │
│ • ENG-W 131 — A- (Fall 2024)        │
│ • BUS-C 104 — B+ (Fall 2024)        │
│ • BUS-T 175 — A (Fall 2024)         │
│ • ECON-B 251 — B (Fall 2024)        │
│ • MATH-M 119 — B+ (Fall 2024)       │
│                                      │
│ GPA: 3.44                            │
│ Credits: 13.5                        │
├─────────────────────────────────────┤
│ [Fix Something]  [Looks Good →]     │
└─────────────────────────────────────┘
```

### "Fix Something" Behavior
- Opens inline edit mode for selected field
- Keeps other data locked
- Returns to confirmation when done
- Allows: course removal, grade correction, major change, year correction

### Validation Rules
- Must have at least 1 course code extracted
- Major can be empty (user selects later in chat)
- If critical data missing, prompt before proceeding

---

## Recommendation Card Schema

### Per-Course Card Format
```
┌──────────────────────────────────────┐
│ BUS-A 304                    3 cr    │
│ Financial Reporting & Analysis       │
├──────────────────────────────────────┤
│ ✓ Prerequisites met                  │
│                                      │
│ Why: As a Finance major, you need    │
│ accounting fundamentals before       │
│ upper-level courses. This is         │
│ required for I-Core completion.      │
│                                      │
│ Grade required: C or higher          │
└──────────────────────────────────────┘

⚠ Warning (if applicable):
  Finance BUS-F 370 requires C+ or higher in prerequisite

📊 I-Core Progress (shown once):
  5 of 19 completed (26%)
  Missing: [list courses]
```

### Recommendation Algorithm
1. **Identify gaps**: Which I-Core prerequisites are missing?
2. **Check prerequisites**: Can student take this course now?
3. **Prioritize**: I-Core → major requirements → electives
4. **Credit balance**: Aim for 12-18 credits (user preference)
5. **Flag warnings**: Courses with grade prerequisites (C+ for Finance, etc.)

---

## Chat Context & Follow-ups

### Persistent Profile Context
Every chat message includes:
```json
{
  "parsed_profile": {
    "student_name": "Emma Chen",
    "matriculation_year": 2024,
    "current_year": "Sophomore",
    "declared_majors": ["Finance"],
    "semester_planning_for": "Fall 2026",
    "credit_hours_preference": 15,
    "icore_percent": 26,
    "icore_ready": false,
    "courses_completed": ["ENG-W 131", "BUS-C 104", ...],
    "transcript_summary": "5 courses, GPA 3.44, 26% I-Core complete"
  },
  "conversation_history": [ /* full chat history */ ],
  "current_recommendations": [ /* courses already recommended */ ]
}
```

### Expected Follow-up Questions
Students should be able to ask:
- "What if I drop Marketing?" → recommend without those courses
- "Show me next year's plan" → multi-semester recommendations
- "Am I ready for I-Core?" → explicit answer + missing courses
- "What are my major requirements?" → list all requirements + progress
- "Can I take [course]?" → check prerequisites
- "Why [course]?" → explain recommendation from first turn

### System Prompt Requirement
Advisor should:
1. Reference student's specific courses and grades
2. Explain WHY each course is recommended
3. Flag prerequisites and grade requirements
4. Show progress toward I-Core/major
5. Adjust recommendations based on conversation (e.g., "drop this course" → recalculate)

---

## Technical Requirements

### Parsing Accuracy
- **Course code extraction**: 95%+ accuracy on standard formats
- **Grade parsing**: Correctly distinguish A+/A/A-, B+/B/B-, etc.
- **I-Core calculation**: Match against official 19 requirements
- **Fallback**: If parsing < 50% accurate, show form to manually add key fields

### Performance
- **File upload**: Handle up to 10MB PDFs
- **Parse time**: < 2 seconds for typical transcript
- **LLM response time**: < 10 seconds for recommendations (Groq API)

### State Management
- **No page refresh** during state transitions
- **Auto-save**: Don't lose parsed data if student navigates away
- **Browser session**: Store profile/transcript in session for continuity

---

## UI/UX Details

### Landing State
- Drop zone: 50vh tall, centered, high visual priority
- Text: "📄 Drop your transcript here"
- Subtext: "PDF or TXT file, or paste below"
- Chat input below: greyed out, hint text "or type your transcript directly"

### Confirmation State
- Card centered, 600px wide max
- Course list scrollable if > 10 courses
- "Fix Something" and "Looks Good" buttons clearly visible
- Back button to upload new transcript

### Recommendations + Chat State
- Top: Student profile header (sticky, compact)
- Middle: Recommendation cards (scrollable)
- Bottom: Chat interface (input always visible)
- No sidebar, no panels — single scrolling experience

---

## Error Handling

### Parsing Failures
- **No courses found**: Show form, ask for major + semester
- **Malformed file**: Suggest manual entry or re-upload
- **Empty transcript**: Allow conversational-only mode ("Just chat with me about your goals")

### API Failures (Groq)
- **Fallback recommendations**: Use rule-based system
- **Retry logic**: Retry once after 2 seconds
- **Graceful degradation**: Show partial recommendations if API times out

---

## Future Enhancements
- Pre-filled form if student logs in (university SSO)
- Export course plan as PDF
- Share recommendations with advisor
- Multi-year plan visualization
- Schedule conflict detection

---

**Version**: 3.0
**Last Updated**: April 2026
**Status**: Ready for implementation
