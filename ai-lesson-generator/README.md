# AI Lesson Generator — Stage 1

Stage 1 provides the backend foundation: FastAPI, Tavily web research, Gemini lesson generation, JSON validation and automated tests. The React lesson player and avatar are planned for later stages.

## Requirements

- Python 3.10 or newer
- A Gemini API key
- A Tavily API key
- Internet access when generating a real lesson

## Setup (Windows)

**Quick start:** open the `backend` folder, double-click `start_backend.bat`, then add your API keys to the `.env` file when prompted. Double-click the same file again to start the server.

**Manual setup (PowerShell):**

1. Open a terminal in the `backend` folder.
2. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install packages:

   ```powershell
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env` and enter your keys:

   ```powershell
   Copy-Item .env.example .env
   ```

   Keep `.env` private. It is excluded from Git by `.gitignore`.

5. Start the API:

   ```powershell
   uvicorn app.main:app --reload
   ```

6. Open the interactive API page at http://127.0.0.1:8000/docs. The health check is at http://127.0.0.1:8000/health.

## Generate a lesson

In `/docs`, open `POST /api/lessons/generate`, select **Try it out**, and send:

```json
{
  "topic": "How computer networks work",
  "script": "Optional lecturer script or outline goes here."
}
```

The script field is optional. A successful response contains a title, topic, introduction, at least four lesson sections, slide bullet points and source links.

## Run automated tests

From the `backend` folder, double-click `run_tests.bat`, or with the virtual environment activated run:

```powershell
pytest
```

The tests use sample data and do not call Gemini or Tavily. They test lesson validation and JSON parsing.

## API endpoints

- `GET /health` — confirms that the API is running.
- `POST /api/lessons/generate` — researches the topic with Tavily and generates a validated lesson with Gemini.

## Stage 1 commit

After you have run and checked the project, commit it to your own repository:

```bash
git add .
git commit -m "Initial working backend with AI lesson generation"
git branch -M main
git push -u origin main
```

## AI assistance and academic integrity

AI assistance was used to create the initial Stage 1 scaffold. Review, run, test and understand the code; adapt it yourself and disclose this assistance in the AI-use log required by the project brief. Do not submit code you cannot explain.
