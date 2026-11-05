# AI Lesson Generator

AI Lesson Generator researches a topic and creates a structured lesson with sections, presentation slides, narration, source links and a simple animated AI tutor.

## Requirements

- Python 3.10 or newer
- Node.js 18 or newer
- Gemini API key
- Tavily API key
- Internet access when generating a new lesson

## 1. Configure the backend (first time only)

Open a terminal in `backend` and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `backend/.env` and enter your own Gemini and Tavily API keys. Never upload `.env` to GitHub.

## 2. Start the backend

In a terminal inside `backend` (with the virtual environment active):

```powershell
uvicorn app.main:app --reload
```

The API runs at `http://127.0.0.1:8000`. Check `http://127.0.0.1:8000/health`.

## 3. Start the frontend

Open a second terminal in `frontend`:

```powershell
npm install
npm run dev
```

Open the local address printed by Vite, normally `http://localhost:5173`. Keep both terminals running while using the application.

## Features

- Researches topics with Tavily and generates lessons with Gemini.
- Accepts an optional lecturer script or outline.
- Produces structured sections, narration, slide bullet points and sources.
- Browser text-to-speech with play, pause, previous/next, voice and speed controls.
- Animated on-screen AI tutor that reacts while narration is playing.
- Saves a lesson as a JSON file.
- Loads a saved JSON lesson without calling Gemini or Tavily.
- Displays useful errors for missing API keys, research/network failures and generation problems.

## Save and load

Use **Save lesson** in the lesson view to download a `.json` lesson file. Use **Load lesson** in the top bar to open that file later. Loading a saved lesson is local and does not make an AI request.

## Automated tests

From the `backend` folder, run:

```powershell
.\run_tests.bat
```

Or, with the virtual environment active:

```powershell
pytest
```

The tests use sample data and do not require live Gemini or Tavily calls.

## API endpoints

- `GET /health` — backend health check.
- `POST /api/lessons/generate` — research and generate a lesson.

## Git and security

- Keep API keys in `backend/.env`; `.env` is ignored by Git.
- Do not commit virtual environments, `node_modules`, or API keys.
- Use meaningful commits when completing project stages.

## AI assistance

AI assistance was used during development. Review and understand the code, verify its behaviour, and disclose AI assistance in the AI-use log required by the project brief. Do not submit code you cannot explain.
