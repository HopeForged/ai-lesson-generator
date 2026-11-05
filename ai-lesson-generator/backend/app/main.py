from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.models import Lesson, LessonRequest
from app.services import (
    ConfigurationError,
    GenerationError,
    ResearchError,
    generate_lesson,
    research_topic,
)

load_dotenv()

app = FastAPI(
    title="AI Lesson Generator API",
    description="Researches a topic and generates a structured lesson using Tavily and Gemini.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "message": "AI Lesson Generator API is running."}


@app.post("/api/lessons/generate", response_model=Lesson)
def create_lesson(request: LessonRequest) -> Lesson:
    try:
        research = research_topic(request.topic)
        return generate_lesson(request.topic, request.script, research)
    except ConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ResearchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except GenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
