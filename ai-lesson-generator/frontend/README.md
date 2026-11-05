# AI Lesson Generator — Stage 2 Frontend

This is the React lesson player for the AI Lesson Generator project.

## Requirements
- Node.js 18 or newer
- Stage 1 FastAPI backend running at `http://127.0.0.1:8000`

## Run the frontend
1. Open a terminal in this `frontend` folder.
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```
4. Open the local address printed by Vite (normally `http://localhost:5173`).

Keep the backend running in its own terminal. Vite forwards `/api` requests to the backend at `http://127.0.0.1:8000`, so the browser does not need direct access to the backend port.

## Features
- Topic input and optional lecturer notes/script
- Calls `POST /api/lessons/generate`
- Displays lesson introduction and sections
- Displays slide title and bullet points
- Shows narration transcript
- Browser text-to-speech with play/pause, previous/next section, voice selection and speed
- Displays source links returned by the backend
- Handles request errors and malformed lesson responses

## Notes
- Text-to-speech voices are supplied by the user's browser/operating system. Available voices vary by device.
- The avatar and save/load features are planned for Stage 3.
- No API keys are stored in this frontend. Keep Gemini and Tavily keys in the backend `.env` file and do not commit that file.
