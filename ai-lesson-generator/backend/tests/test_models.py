import json
import pytest
from pydantic import ValidationError

from app.models import Lesson, LessonRequest, VisualMoment, VisualScene
from app.services import GenerationError, _extract_json, ensure_visual_moments


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


def test_visual_scene_accepts_ai_planned_process():
    scene = VisualScene.model_validate({
        "scene_type": "process",
        "title": "How data moves",
        "description": "Data passes through three stages.",
        "items": ["Input", "Processing", "Output"],
    })
    assert scene.scene_type == "process"
    assert len(scene.items) == 3


def test_old_lesson_without_visual_scene_remains_compatible():
    data = valid_lesson_dict()
    lesson = Lesson.model_validate(data)
    assert lesson.sections[0].visual_scene.scene_type == "generic"
    assert len(lesson.sections[0].visual_scene.items) >= 2


def test_visual_moment_requires_a_narration_cue_and_scene():
    moment = VisualMoment.model_validate({
        "cue_text": "The heart pumps blood around the body.",
        "scene": {
            "scene_type": "process",
            "title": "Blood circulation",
            "description": "Show blood moving through the body.",
            "items": ["Heart", "Arteries", "Body"],
        },
    })
    assert moment.scene.scene_type == "process"


def test_legacy_lesson_defaults_to_no_visual_moments():
    lesson = Lesson.model_validate(valid_lesson_dict())
    assert lesson.sections[0].visual_moments == []


def test_ensure_visual_moments_creates_multiple_sentence_linked_scenes():
    lesson = Lesson.model_validate(valid_lesson_dict())
    lesson = ensure_visual_moments(lesson)
    section = lesson.sections[0]
    assert len(section.visual_moments) >= 3
    assert all(moment.cue_text in section.narration for moment in section.visual_moments)
