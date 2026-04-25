# SciCheck

A static analysis tool for scientific code that detects domain-specific bugs and anti-patterns in genomics and other research workflows.

## Overview

SciCheck analyzes Python and R code for common methodological errors in scientific computing — things like incorrect statistical assumptions, misused genomics functions, or off-by-one errors in indexing — and reports findings with explanations.

## Project Structure

```
SciCheck/
├── backend/               # FastAPI server
│   ├── main.py            # API entry point
│   ├── analyzer.py        # Core analysis logic
│   ├── indexer.py         # Code indexing
│   ├── models.py          # Request/response models
│   ├── rlt.py             # Rule/logic types
│   ├── requirements.txt   # Python dependencies
│   ├── .env.example       # Environment variable template
│   └── patterns/          # Domain-specific pattern libraries
│       └── genomics.py    # Genomics pattern checks
└── frontend/              # React + Vite UI
    ├── src/
    │   ├── App.jsx
    │   ├── components/
    │   │   ├── FileUploader.jsx
    │   │   └── FindingCard.jsx
    │   └── index.css
    └── index.html
```

## Getting Started

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # Add your API key
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:5173` and connects to the backend at `http://localhost:8000`.

## API

| Method | Endpoint         | Description                        |
|--------|------------------|------------------------------------|
| GET    | `/health`        | Health check                       |
| POST   | `/analyze`       | Analyze a code snippet             |
| POST   | `/analyze/files` | Analyze one or more uploaded files |

## Environment Variables

Create a `.env` file in the `backend/` directory based on `.env.example`:

```
GEMINI_API_KEY=your-gemini-api-key-here
```
