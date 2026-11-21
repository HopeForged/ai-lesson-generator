# LessonForge – AI lesson generator (stage 11)

Type a topic (or upload a PDF / Word / text file) and get a **lecture taught by a human lecturer** with a natural voice, diagrams that build as they speak, quizzes, flashcards, a live "ask the lecturer" chat, study notes and an **exportable MP4 video**. Everything below is free to run: Groq + Gemini + Tavily (your existing keys), Edge neural voices, SQLite, Playwright and ffmpeg.

## What you get
| Feature | How it works |
|---|---|
| Lecturer | 3 selectable lecturers (Dr. Mensah, Prof. Naledi, Mr. Walker) with matching voices; gestures, blinking, lip-sync to the real audio |
| Natural voice | `edge-tts` (free Microsoft neural voices, 14 languages incl. Zulu, Swahili, Afrikaans). Falls back to the browser voice automatically |
| Diagrams | 7 layouts (steps, cycle, hub, network, comparison, timeline, grid), a new set per lecture beat, each label lights up when the lecturer says it |
| Ask the lecturer | Type or speak a question; the lecturer answers at the board with a new diagram |
| Quizzes | 3 questions per section, a final test, flashcards, saved scores and progress |
| Library | Every lesson is stored in SQLite, shareable link `#/lesson/<id>` |
| Teach from your files | PDF, Word (.docx), .txt, .md |
| Languages & levels | 14 languages; beginner / intermediate / advanced / exam prep |
| Exports | MP4 lecture video (+ .srt captions), print / save study notes as PDF, Markdown notes, lesson JSON |
| Live progress | Background jobs with a progress bar while the lesson is built |
| Safety | per-IP rate limit, upload size limit, Docker image |

## Run it (Windows / Mac / Linux)
```bash
# backend
cd backend
python -m venv .venv && .venv\Scripts\activate        # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                                  # then paste your keys
uvicorn app.main:app --reload

# frontend (second terminal)
cd frontend
npm install
npm run dev                                             # open http://localhost:5173
```
The app works with just the keys. The extras switch on when installed (the app tells you what is missing):

1. **Natural voice**: `pip install edge-tts` (already in requirements.txt). Needs internet, no key.
2. **PDF / Word upload**: `pypdf`, `python-docx` (in requirements.txt).
3. **Video export**: `playwright install chromium` and install **ffmpeg** (`winget install ffmpeg`, `brew install ffmpeg` or `apt install ffmpeg`). Keep `npm run dev` running: the recorder opens the app at `RENDER_BASE_URL` (default http://127.0.0.1:5173).

### Video export notes
- The lecture is recorded in real time by a headless browser (about 1.2x the lecture length), then encoded to MP4 with the voice track. You can keep using the app meanwhile.
- No voice engine? You can still make a captions-only video (tick the box in the video panel).

### Docker (one command, includes ffmpeg and Chromium)
```bash
docker compose up --build        # http://localhost:8000
```

## Honest limits
- Voices need an internet connection (free Microsoft service; they could change it someday). The browser voice is the automatic fallback.
- There are no user accounts: the library is shared by everyone who can reach the server and progress/scores are saved per browser. Add authentication before putting it on the public internet.
- The library and quiz endpoints work on lessons saved on the server; links only work for people who can reach your server.
- Video is recorded in real time, so very long lectures take a while.
- Quality of facts depends on the AI models; the built-in quality check helps but does not replace reading the sources.

## Tests
`cd backend && python -m pytest -q` (47 tests, no network or API keys needed).

Older install notes are in `docs/`.


## Stage 12: animated scenes
See STAGE12-CHANGES.txt. Each diagram is now an AI-directed animation (actors, movement, charts, counters) that follows what the lecturer says; the plain diagram is the automatic fallback.
