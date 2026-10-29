# AuraScribe 🩺✨

**AuraScribe** is an AI-powered clinical audio transcription and structured clinical documentation (SOAP note) application. Built for **multilingual medical dialogues**—supporting English, Tagalog, Taglish, Bisaya/Cebuano, Ilocano, Spanish, French, Japanese, and any regional or global language—AuraScribe converts recorded physician-patient consultations into verbatim transcripts and strongly validated, schema-compliant JSON SOAP notes with accurate clinical translation.

> [!IMPORTANT]
> **Mandatory Physician Review Required:** AuraScribe is an assistive clinical documentation tool, **not** an autonomous diagnostic or prescriptive system. Every generated transcript and structured note requires formal review, verification, and sign-off by a licensed physician prior to any clinical or medical record use.

---

## Architecture and End-to-End Pipeline

```
Browser Recording (MediaRecorder API)
          │
          ▼
   Flask REST API (/api/process)
          │
          ▼
   Audio Validation (Size, MIME, Audio Header Integrity)
          │
          ▼
   Transcription Service (OpenAI Audio API: whisper-1)
          │
          ▼
   Transcript Validation (Non-empty, Linguistic Integrity)
          │
          ▼
   Clinical Extraction Agent (Pydantic AI + Versioned Prompt)
          │
          ▼
   Pydantic v2 Schema Validation (Subjective, Objective, Assessment, Plan)
          │
          ▼
   Clinical Guardrails (No hallucinated diagnoses/rx, uncertainty preservation)
          │
          ▼
   JSON Response & Physician Review Interface (Browser)
```

---

## Directory Structure

```
aurascribe/
├── README.md                           # Documentation, setup, and architectural guidelines
├── requirements.txt                    # Pinned and validated Python dependencies
├── Dockerfile                          # Multi-stage production container build
├── compose.yaml                        # Docker Compose service definition
├── .env.example                        # Template for environment configuration
├── .gitignore                          # Git ignore rules
├── pyproject.toml                      # Build definitions and pytest configuration
├── src/
│   └── aurascribe/
│       ├── __init__.py
│       ├── main.py                     # Flask application factory and entrypoint
│       ├── agent/
│       │   ├── __init__.py
│       │   ├── clinical_agent.py       # Pydantic AI agent definition and extraction logic
│       │   ├── executor.py             # Pipeline orchestrator
│       │   └── state.py                # Typed pipeline state and processing status
│       ├── tools/
│       │   ├── __init__.py
│       │   └── transcription_tool.py   # Transcription coordinator and audio preparation
│       ├── models/
│       │   ├── __init__.py
│       │   ├── llm_client.py           # LLM client abstractions for agent operations
│       │   └── transcription_client.py # Audio transcription API client
│       ├── prompts/
│       │   └── clinical_extraction.md  # Version-controlled prompt instructions
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── audio.py                # Audio validation metadata contract
│       │   ├── transcript.py           # Transcript metadata contract
│       │   └── soap.py                 # Pydantic v2 SOAP Note clinical models
│       ├── api/
│       │   ├── __init__.py
│       │   ├── routes.py               # Flask endpoints (/health, /api/process, /)
│       │   └── schemas.py              # API request and response contracts
│       └── utils/
│           ├── __init__.py
│           ├── config.py               # Validated Pydantic settings
│           ├── logger.py               # Structured privacy-preserving logger
│           └── errors.py               # Centralized domain exceptions & HTTP mapping
├── templates/
│   └── index.html                      # Clean clinical recording & review UI
├── static/
│   ├── css/
│   │   └── style.css                   # Professional clinical UI styling
│   └── js/
│       └── recorder.js                 # MediaRecorder API controller & submission handler
└── tests/
    ├── conftest.py                     # Test fixtures and mocks
    ├── test_schemas.py                 # Pydantic validation unit tests
    ├── test_agent.py                   # Pydantic AI agent extraction tests
    ├── test_tools.py                   # Audio and transcription client tests
    └── test_api.py                     # Flask route and integration tests
```

---

## Technology Stack

- **Python:** 3.12
- **Web Backend:** Flask 3.x
- **Data Validation & Schemas:** Pydantic v2 & Pydantic Settings
- **Agent Orchestration:** Pydantic AI
- **External AI Services:** OpenAI Audio API (`whisper-1`) & OpenAI LLM (`gpt-4o-mini` / `gpt-4o`)
- **WSGI Server:** Gunicorn 22.x
- **Frontend:** HTML5, Jinja2, CSS3, Vanilla JavaScript (MediaRecorder API)
- **Testing:** pytest, pytest-mock, pytest-asyncio
- **Containerization:** Docker & Docker Compose

---

## Privacy and Audio Data Handling

- **In-Memory Audio Processing:** Audio bytes uploaded via `/api/process` are streamed into in-memory buffers (`io.BytesIO`) during validation and upstream API dispatch.
- **Zero Local Disk Persistence:** Neither raw audio recordings nor temporary chunk files are stored in Docker volumes or host directories.
- **Privacy-Compliant Logging:** Application logs record only operational metadata (request ID, pipeline stage, duration, model identifier, HTTP status). Raw transcripts, audio payloads, and Protected Health Information (PHI) are strictly filtered out of log statements.
- **Limitation Note:** External API providers (such as OpenAI) process payloads subject to their organizational zero-data-retention (ZDR) and business agreements. This MVP is designed for testing with synthetic, simulated, or consented recordings and does not directly connect to an electronic medical records (EMR) system.

---

## Getting Started

### Prerequisites

- Python 3.12+ (or Docker / Docker Compose)
- OpenAI API Key

### 1. Environment Setup

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` and set your desired provider and configuration:

```ini
# Environment
AURASCRIBE_ENV=development

# LLM Backend: 'ollama' (GPU local/remote) or 'openai' (cloud)
AURASCRIBE_LLM_PROVIDER=ollama
AURASCRIBE_LLM_MODEL=qwen3.5:9b-q8_0
OLLAMA_BASE_URL=http://philgood:11434/v1
OLLAMA_API_KEY=

# Target language for clinical documentation synthesis ('English', 'Spanish', 'Tagalog', etc.)
AURASCRIBE_TARGET_LANGUAGE=English

# Audio Transcription (Cloud OpenAI or self-hosted Whisper)
OPENAI_API_KEY=
AURASCRIBE_TRANSCRIPTION_PROVIDER=openai
AURASCRIBE_TRANSCRIPTION_MODEL=whisper-1
AURASCRIBE_TRANSCRIPTION_BASE_URL=
AURASCRIBE_DEFAULT_LANGUAGE_HINT=
```

### 2. Local Installation

```bash
# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run Locally

```bash
# Development mode
python -m aurascribe.main

# Or via Gunicorn
gunicorn --bind 127.0.0.1:5000 aurascribe.main:app
```

Navigate to `http://127.0.0.1:5000` in your browser.

---

## Docker Deployment

Build and run using Docker Compose:

```bash
# Build and run containers
docker compose up --build -d

# View logs
docker compose logs -f

# Check container status
docker compose ps

# Rebuild container after changes
docker compose build --no-cache && docker compose up -d

# Shut down container
docker compose down
```

The application will be accessible at `http://127.0.0.1:5000`.

---

## Running Automated Tests

A comprehensive suite of tests covers schemas, agent extractions, tools, error handling, and API endpoints without calling external paid APIs:

```bash
# Run all tests
pytest -v

# Run specific test modules
pytest tests/test_schemas.py -v
pytest tests/test_agent.py -v
pytest tests/test_tools.py -v
pytest tests/test_api.py -v
```

---

## Prompt Engineering & Versioning

Prompt instructions for the clinical extraction agent are managed in `src/aurascribe/prompts/clinical_extraction.md`. The prompt enforces:
1. Strict grounding in transcript text only.
2. Nuanced comprehension of Tagalog, Taglish, and English phrasing.
3. Separation of patient-reported symptoms (Subjective) from clinician-observed findings (Objective).
4. Explicit documentation of ambiguities, uncertainties, and contradictions.
5. Strict refusal to invent vitals, dosages, follow-ups, or unverified diagnoses.
6. Mandatory attribution of `review_required = True`.

