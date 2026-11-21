"""AI-generated quizzes, a final test and flashcards for a lesson."""
import json
import random
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.services import GenerationError, _ai_json_response


class QuizQuestion(BaseModel):
    question: str = Field(min_length=5, max_length=400)
    options: list[str] = Field(min_length=2, max_length=4)
    answer_index: int = Field(ge=0, le=3)
    explanation: str = Field(default="", max_length=600)

    @field_validator("options", mode="before")
    @classmethod
    def _trim(cls, value):
        return [str(v).strip()[:200] for v in value if str(v).strip()][:4] if isinstance(value, list) else value

    @model_validator(mode="after")
    def _answer_exists(self):
        if self.answer_index >= len(self.options):
            raise ValueError("answer_index is outside the options")
        return self


class SectionQuiz(BaseModel):
    section_index: int = Field(ge=0)
    questions: list[QuizQuestion] = Field(min_length=1, max_length=5)


class Flashcard(BaseModel):
    front: str = Field(min_length=2, max_length=240)
    back: str = Field(min_length=2, max_length=500)


class Quiz(BaseModel):
    sections: list[SectionQuiz]
    final: list[QuizQuestion] = Field(default_factory=list, max_length=15)
    flashcards: list[Flashcard] = Field(default_factory=list, max_length=20)


def _shuffled(question: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    """Language models love putting the right answer in slot B; move it around."""
    options = list(question.get("options", []))
    try:
        correct = options[int(question.get("answer_index", 0))]
    except (IndexError, ValueError, TypeError):
        return question
    rng.shuffle(options)
    return {**question, "options": options, "answer_index": options.index(correct)}


def _clean_questions(items: Any, rng: random.Random) -> list[dict[str, Any]]:
    out = []
    for item in items if isinstance(items, list) else []:
        try:
            q = QuizQuestion.model_validate(item)
        except Exception:
            continue
        out.append(_shuffled(q.model_dump(), rng))
    return out


def clean_quiz(payload: dict[str, Any], section_count: int, seed: str = "") -> Quiz:
    rng = random.Random(seed or "lessonforge")
    sections = []
    for entry in payload.get("sections", []) if isinstance(payload, dict) else []:
        try:
            index = int(entry.get("section_index"))
        except (TypeError, ValueError, AttributeError):
            continue
        questions = _clean_questions(entry.get("questions"), rng)
        if 0 <= index < section_count and questions:
            sections.append({"section_index": index, "questions": questions[:5]})
    cards = []
    for card in payload.get("flashcards", []) if isinstance(payload, dict) else []:
        try:
            cards.append(Flashcard.model_validate(card).model_dump())
        except Exception:
            continue
    quiz = Quiz(sections=sections, final=_clean_questions(payload.get("final"), rng)[:12], flashcards=cards[:20])
    if not quiz.sections:
        raise GenerationError("The AI did not return usable quiz questions. Please try again.")
    return quiz


def generate_quiz(lesson: dict[str, Any]) -> Quiz:
    language = lesson.get("language", "English")
    summary = [
        {
            "section_index": i,
            "heading": s.get("heading"),
            "key_points": (s.get("slide") or {}).get("bullet_points", []),
            "lecture": str(s.get("narration", ""))[:1800],
        }
        for i, s in enumerate(lesson.get("sections", []))
    ]
    prompt = f"""Write a quiz for this lesson: {lesson.get('title')!r} (level: {lesson.get('level', 'intermediate')}).
Write all text in {language}. Questions must test understanding of what the lecture actually taught, not trivia.
Return ONLY valid JSON:
{{"sections":[{{"section_index":0,"questions":[{{"question":"...","options":["A","B","C","D"],"answer_index":0,"explanation":"One or two sentences explaining why the answer is right."}}]}}],
"final":[same question objects covering the whole lesson],
"flashcards":[{{"front":"term or question","back":"short clear answer"}}]}}
Rules: exactly 3 questions for EVERY section (use each section_index from the lesson), 4 options each with exactly one correct answer and plausible wrong answers, 8 final-test questions mixing all sections, 10 flashcards of the most important ideas. Do not put the correct answer in the same position every time. Do not mention "the lecture" or "the lesson" in the questions.
LESSON: {json.dumps(summary, ensure_ascii=False)}"""
    payload = _ai_json_response(prompt, temperature=0.4)
    return clean_quiz(payload, len(summary), seed=str(lesson.get("title", "")))
