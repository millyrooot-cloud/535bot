# Kelley Compass AI

Intelligent course planning chatbot for Indiana University's Kelley School of Business. Get personalized course recommendations based on your transcript, major, and degree requirements.

## Features

- ✅ **Optional Fields**: Get advice even with minimal information
- ✅ **Conversation Memory**: Bot remembers full chat context
- ✅ **Professional UI**: Clean, corporate university design
- ✅ **Smooth Animations**: Polished transitions and interactions
- ✅ **Responsive**: Works on desktop, tablet, and mobile
- ✅ **Fast**: No build step, no npm dependencies
- ✅ **Smart**: Analyzes transcripts, prerequisites, and major requirements

## Quick Start

### Prerequisites
- Python 3.8+
- Groq API key (free at https://groq.com)

### Installation

```bash
# Clone/navigate to project
cd 535bot

# Create virtual environment
python -m venv .venv
source .venv/Scripts/activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Configure Groq API
# Edit .env.local and add your API key:
# GROQ_API_KEY=your_key_here

# Run the app
python app.py
```

Open http://localhost:5000 in your browser.

## How to Use

### 1. Submit Your Profile
Fill in what you know (all fields optional):
- Major(s), current year, graduation timeline
- Credit hours preference, career interests
- Paste your transcript (even partial works)

### 2. Get Recommendations
- Click "Get Recommendations"
- System analyzes your situation
- Returns 3-5 personalized courses with explanations

### 3. Ask Follow-Up Questions
- Bot remembers everything from the conversation
- Ask about prerequisites, major requirements, graduation timeline
- All answers reference your specific academic situation

## What It Does

**Analyzes:**
- Your completed courses and grades
- I-Core prerequisite progress
- Major requirements and sequences
- Graduation timeline

**Provides:**
- Personalized course recommendations
- Prerequisites and grade requirements
- Explanations for each recommendation
- Career-aligned suggestions

**Remembers:**
- Your profile and transcript
- Full conversation history
- Previous recommendations and context

## Architecture

```
Frontend (HTML/CSS/JS)
        ↓
    Flask Backend
        ↓
    Groq API (LLM)
        ↓
    Session Storage (Conversation + Profile)
```

### Tech Stack
- **Backend**: Flask 3.0+, Python
- **Frontend**: HTML5, CSS3, Vanilla JavaScript
- **AI**: Groq API (llama-3.3-70b-versatile)
- **No buildstep**: Plain HTML/CSS/JS

## File Structure

```
535bot/
├── app.py                    # Flask backend
├── requirements.txt          # Dependencies
├── .env.local               # Groq API key
├── README.md                # This file
├── CHANGELOG.md             # Version history
├── templates/
│   └── index.html           # Main app
├── static/
│   ├── css/styles.css       # Professional styling
│   └── js/app.js            # Chat client
├── RAG/
│   └── RAG_PRD.md          # Product requirements
└── .venv/                   # Python environment
```

## Development

### Run locally with hot reload
```bash
python app.py
```

### Test the API
```bash
# Health check
curl http://localhost:5000/api/health

# Chat endpoint
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "profile": {"declared_majors": ["Finance"]},
    "transcript_text": "BUS-A 304 | A",
    "message": "Please recommend courses"
  }'
```

## API

### GET /
Returns the main chatbot page

### GET /api/health
Health check
```json
{"ok": true, "groq_configured": true}
```

### POST /api/chat
Chatbot endpoint

**Request:**
```json
{
  "profile": {
    "declared_majors": ["Finance"],
    "semester_planning_for": "Fall 2026",
    "credit_hours_preference": 15
  },
  "transcript_text": "BUS-A 304 | A\nECON-B 251 | B+",
  "message": "Please recommend courses"
}
```

**Response:**
```json
{
  "reply": "Recommendations and explanation...",
  "is_analysis": true,
  "icore_percent": 26.3,
  "icore_ready": false
}
```

## Configuration

### .env.local
```
GROQ_API_KEY=your_key_here
GROQ_MODEL=llama-3.3-70b-versatile
FLASK_SECRET_KEY=dev-secret-key
```

## Troubleshooting

**Port already in use:**
```bash
# Windows
netstat -ano | findstr :5000
taskkill /PID [PID] /F

# Mac/Linux
lsof -i :5000 | xargs kill -9
```

**Groq API failing:**
- Verify `.env.local` has valid API key
- Check Groq dashboard for rate limits
- App falls back to rule-based recommendations

**Chat not remembering context:**
- Ensure browser cookies are enabled
- Clear browser cache if issues persist

## Version

**Current**: 2.0 (April 2026)

See [CHANGELOG.md](CHANGELOG.md) for complete history and improvements.

## License

Internal use only.
