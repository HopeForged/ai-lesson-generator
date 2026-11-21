import os
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

load_dotenv()

from app import config, db, jobs, sources, tts, video  # noqa: E402
from app.models import Lesson, LessonRequest  # noqa: E402
from app.qa import ask_lecturer  # noqa: E402
from app.quiz import generate_quiz  # noqa: E402
from app.services import (  # noqa: E402
    ConfigurationError,
    GenerationError,
    ResearchError,
    build_lesson,
)

app = FastAPI(
    title="LessonForge API",
    description="AI lesson generator: research, lectures with diagrams, free neural voices, quizzes, Q&A and MP4 export.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# ---------- simple per-IP rate limit for the expensive AI/voice endpoints ----------
_hits: dict[str, deque] = defaultdict(deque)
_hits_lock = threading.Lock()
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MINUTE", "40"))
LIMITED_PREFIXES = ("/api/lessons/generate", "/api/quiz", "/api/ask", "/api/video", "/api/tts")


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    path = request.url.path
    if request.method == "POST" and path.startswith(LIMITED_PREFIXES):
        ip = request.client.host if request.client else "local"
        now = time.time()
        with _hits_lock:
            window = _hits[ip]
            while window and now - window[0] > 60:
                window.popleft()
            if len(window) >= RATE_LIMIT:
                return JSONResponse({"detail": "Too many requests. Please wait a minute and try again."}, status_code=429)
            window.append(now)
    return await call_next(request)


def _fail(exc: Exception) -> HTTPException:
    if isinstance(exc, ConfigurationError):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=502, detail=str(exc))


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "message": "LessonForge API is running."}


@app.get("/api/capabilities")
def capabilities() -> dict:
    """Lets the frontend know which free extras are ready on this machine."""
    import importlib.util
    import shutil

    return {
        "voice": importlib.util.find_spec("edge_tts") is not None,
        "video": bool(shutil.which("ffmpeg")) and importlib.util.find_spec("playwright") is not None,
        "ffmpeg": bool(shutil.which("ffmpeg")) and bool(shutil.which("ffprobe")),
        "playwright": importlib.util.find_spec("playwright") is not None,
        "pdf": importlib.util.find_spec("pypdf") is not None,
        "languages": list(config.LANGUAGES.keys()),
        "lecturers": [{"id": k, **v} for k, v in config.LECTURERS.items()],
    }


# ---------------- lessons ----------------
@app.post("/api/lessons/generate", response_model=Lesson)
def create_lesson(request: LessonRequest) -> Lesson:
    """Synchronous generation (kept for compatibility)."""
    try:
        return build_lesson(request)
    except (ConfigurationError, ResearchError, GenerationError) as exc:
        raise _fail(exc) from exc


@app.post("/api/lessons/generate-async")
def create_lesson_async(request: LessonRequest) -> dict:
    """Starts generation in the background so the UI can show live progress."""
    def work(job: jobs.Job):
        lesson = build_lesson(request, progress=job.update)
        data = lesson.model_dump(mode="json")
        data["id"] = db.save_lesson(data)
        db.save_lesson(data, data["id"])
        return data

    job = jobs.start_job("lesson", work, friendly_errors=(ConfigurationError, ResearchError, GenerationError))
    return {"job_id": job.id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    job = jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job.")
    return job.public()


@app.post("/api/sources/extract")
async def extract_source(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    try:
        text = sources.extract_text(file.filename or "", data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"filename": file.filename, "characters": len(text), "text": text}


# ---------------- library ----------------
@app.get("/api/library")
def library_list() -> list[dict]:
    return db.list_lessons()


@app.post("/api/library")
def library_save(lesson: Lesson) -> dict:
    data = lesson.model_dump(mode="json")
    return {"id": db.save_lesson(data)}


@app.get("/api/library/{lesson_id}")
def library_get(lesson_id: str) -> dict:
    data = db.get_lesson(lesson_id)
    if not data:
        raise HTTPException(status_code=404, detail="Lesson not found.")
    data["id"] = lesson_id
    return data


@app.delete("/api/library/{lesson_id}")
def library_delete(lesson_id: str) -> dict:
    if not db.delete_lesson(lesson_id):
        raise HTTPException(status_code=404, detail="Lesson not found.")
    return {"deleted": True}


# ---------------- quiz ----------------
@app.get("/api/quiz/{lesson_id}")
def quiz_get(lesson_id: str) -> dict:
    quiz = db.get_quiz(lesson_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="No quiz yet.")
    return quiz


@app.post("/api/quiz/{lesson_id}")
def quiz_create(lesson_id: str) -> dict:
    lesson = db.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found. Save it to the library first.")
    cached = db.get_quiz(lesson_id)
    if cached:
        return cached
    try:
        quiz = generate_quiz(lesson).model_dump()
    except (ConfigurationError, GenerationError) as exc:
        raise _fail(exc) from exc
    db.save_quiz(lesson_id, quiz)
    return quiz


@app.post("/api/quiz/{lesson_id}/regenerate")
def quiz_regenerate(lesson_id: str) -> dict:
    lesson = db.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found.")
    try:
        quiz = generate_quiz(lesson).model_dump()
    except (ConfigurationError, GenerationError) as exc:
        raise _fail(exc) from exc
    db.save_quiz(lesson_id, quiz)
    return quiz


# ---------------- ask the lecturer ----------------
class AskRequest(BaseModel):
    lesson: dict
    section_index: int = Field(default=0, ge=0, le=20)
    question: str = Field(min_length=3, max_length=500)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=10)


@app.post("/api/ask")
def ask(request: AskRequest) -> dict:
    try:
        return ask_lecturer(request.lesson, request.section_index, request.question.strip(), request.history)
    except (ConfigurationError, GenerationError) as exc:
        raise _fail(exc) from exc


# ---------------- voice ----------------
class TtsRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=40)
    language: str = "English"
    lecturer: str = "mensah"
    rate: float = Field(default=1.0, ge=0.6, le=1.6)


@app.post("/api/tts")
def make_voice(request: TtsRequest) -> dict:
    texts = [t[:3000] for t in request.texts]
    try:
        clips = tts.synthesize_many(texts, config.voice_for(request.language, request.lecturer), request.rate)
    except tts.VoiceUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"clips": [{"url": c["url"], "duration": c["duration"], "words": c["words"], "provider": c["provider"]} for c in clips]}


@app.get("/api/audio/{name}")
def get_audio(name: str):
    path = config.AUDIO_DIR / Path(name).name
    if path.suffix != ".mp3" or not path.exists():
        raise HTTPException(status_code=404, detail="Audio not found.")
    return FileResponse(path, media_type="audio/mpeg")


# ---------------- video export ----------------
class VideoRequest(BaseModel):
    lesson: dict | None = None
    lesson_id: str | None = None
    lecturer: str = "mensah"
    rate: float = Field(default=1.0, ge=0.6, le=1.6)
    allow_silent: bool = False


@app.post("/api/video")
def video_create(request: VideoRequest) -> dict:
    lesson = db.get_lesson(request.lesson_id) if request.lesson_id else request.lesson
    if not lesson or not lesson.get("sections"):
        raise HTTPException(status_code=400, detail="Send a lesson (or a saved lesson_id) to turn into a video.")
    try:
        video.check_requirements()
    except video.VideoError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    base_url = os.getenv("RENDER_BASE_URL", "http://127.0.0.1:5173")
    voice = config.voice_for(lesson.get("language", "English"), request.lecturer)

    def work(job: jobs.Job):
        workdir = video.video_dir(job.id)
        timeline = video.build_timeline(lesson, request.lecturer, voice, request.rate, workdir, job.update, request.allow_silent)
        out = workdir / "lecture.mp4"
        video.record_and_encode(job.id, base_url, workdir, timeline, out, job.update)
        if request.lesson_id:
            db.save_video(job.id, request.lesson_id, request.lecturer, "done", timeline["total"], timeline["has_voice"])
        return {"video_id": job.id, "duration": timeline["total"], "has_voice": timeline["has_voice"],
                "url": f"/api/video/{job.id}/lecture.mp4", "captions": f"/api/video/{job.id}/captions.srt"}

    job = jobs.start_job("video", work, friendly_errors=(video.VideoError,))
    return {"job_id": job.id}


@app.get("/api/library/{lesson_id}/videos")
def library_videos(lesson_id: str) -> list[dict]:
    return [
        {**v, "url": f"/api/video/{v['id']}/lecture.mp4", "captions": f"/api/video/{v['id']}/captions.srt"}
        for v in db.list_videos(lesson_id)
        if (config.VIDEO_DIR / v["id"] / "lecture.mp4").exists()
    ]


@app.get("/api/video/jobs/{video_id}/timeline")
def video_timeline(video_id: str):
    path = config.VIDEO_DIR / Path(video_id).name / "timeline.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Timeline not found.")
    return FileResponse(path, media_type="application/json")


@app.get("/api/video/{video_id}/{name}")
def video_file(video_id: str, name: str):
    name = Path(name).name
    if name not in ("lecture.mp4", "captions.srt"):
        raise HTTPException(status_code=404, detail="File not found.")
    path = config.VIDEO_DIR / Path(video_id).name / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    media = "video/mp4" if name.endswith(".mp4") else "text/plain; charset=utf-8"
    return FileResponse(path, media_type=media, filename=name if name.endswith(".srt") else f"lesson-{video_id}.mp4")


# ---------------- serve the built frontend (Docker / production) ----------------
_dist = config.BASE_DIR.parent / "frontend" / "dist"
if _dist.exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
