# AI-Powered Pharmaceutical Customer Complaint Management System — Backend

Phase 1 (Project Setup) deliverable: the FastAPI application skeleton.

## Requirements

- Python 3.12

## Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
```

## Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Verify

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "app_name": "Pharmaceutical Complaint Management System",
  "version": "1.0.0",
  "environment": "development"
}
```

## Test

```bash
pytest
```

## Project Structure

```text
backend/
├── app/
│   ├── api/          # FastAPI routers (thin, request validation only)
│   ├── config/        # Environment-driven application settings
│   ├── database/       # Reserved: SQLAlchemy engine/session (future phase)
│   ├── graph/           # Reserved: LangGraph nodes/workflow (future phase)
│   ├── knowledge/         # Reserved: taxonomy & risk rule config (future phase)
│   ├── models/              # Typed Pydantic data models
│   ├── prompts/               # Reserved: LLM prompt templates (future phase)
│   ├── services/                # Reserved: business logic services (future phase)
│   ├── utils/                     # Cross-cutting helpers (logging, etc.)
│   └── main.py                      # FastAPI application entry point
├── docs/
├── tests/
├── .env.example
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

## Scope

This phase implements only the project skeleton: folder structure, the
FastAPI application instance, configuration/environment handling, and the
`/health` endpoint. No business logic, database, LangGraph, or LLM
integration is implemented yet — those arrive in later development phases.
