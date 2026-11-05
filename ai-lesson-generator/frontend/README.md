# AI Lesson Generator — React Frontend

## Requirements
- Node.js 18 or newer
- FastAPI backend running at `http://127.0.0.1:8000`

## Run
From this folder:

```bash
npm install
npm run dev
```

Open the local address printed by Vite, normally `http://localhost:5173`. Keep the backend running in a separate terminal.

## Features
- Generate lessons from a topic and optional lecturer notes.
- View lesson sections, slides, narration and source links.
- Browser text-to-speech with play/pause, previous/next, voice and speed controls.
- Animated AI tutor that moves and changes its mouth while narration plays.
- Save the current lesson as a JSON file.
- Load a previously saved JSON lesson without making an AI request.
- Basic validation and error messages for invalid saved files and failed requests.

The browser/operating system supplies the available speech voices. No Gemini or Tavily API key is used in the frontend.
