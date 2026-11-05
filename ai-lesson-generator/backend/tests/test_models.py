import json
import pytest
from pydantic import ValidationError

from app.models import Lesson, LessonRequest
from app.services import GenerationError, _extract_json


def valid_lesson_dict():
    return {
        "title": "Introduction to Networks",
        "topic": "Computer networks",
        "introduction": "A beginner-friendly introduction.",
        "sections": [
            {
                "heading": f"Section {number}",
                "narration": "This section explains an important networking idea in simple terms.",
                "slide": {"title": f"Slide {number}", "bullet_points": ["First point", "Second point"]},
            }
            for number in range(1, 5)
        ],
        "sources": [{"title": "Example source", "url": "https://example.com/article"}],
    }


def test_valid_lesson_is_accepted():
    lesson = Lesson.model_validate(valid_lesson_dict())
    assert len(lesson.sections) == 4


def test_lesson_without_title_is_rejected():
    data = valid_lesson_dict()
    del data["title"]
    with pytest.raises(ValidationError):
        Lesson.model_validate(data)


def test_lesson_without_sections_is_rejected():
    data = valid_lesson_dict()
    data["sections"] = []
    with pytest.raises(ValidationError):
        Lesson.model_validate(data)


def test_lesson_with_fewer_than_four_sections_is_rejected():
    data = valid_lesson_dict()
    data["sections"] = data["sections"][:3]
    with pytest.raises(ValidationError):
        Lesson.model_validate(data)


def test_section_without_narration_is_rejected():
    data = valid_lesson_dict()
    del data["sections"][0]["narration"]
    with pytest.raises(ValidationError):
        Lesson.model_validate(data)


def test_lesson_with_invalid_source_url_is_rejected():
    data = valid_lesson_dict()
    data["sources"][0]["url"] = "not-a-url"
    with pytest.raises(ValidationError):
        Lesson.model_validate(data)


def test_topic_is_trimmed_and_blank_topic_is_rejected():
    assert LessonRequest(topic="  databases  ").topic == "databases"
    with pytest.raises(ValidationError):
        LessonRequest(topic="   ")


def test_json_extractor_handles_markdown_code_fence():
    raw = '```json\n{"title": "Demo"}\n```'
    assert json.loads(_extract_json(raw)) == {"title": "Demo"}


def test_json_extractor_rejects_non_json_reply():
    with pytest.raises(GenerationError):
        _extract_json("I cannot create a lesson right now.")
