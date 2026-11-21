import json
import pytest
from pydantic import ValidationError

from app.models import Lesson, LessonQualityReview, LessonRequest, VisualMoment, VisualScene
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


def test_quality_review_model_accepts_passed_review():
    review = LessonQualityReview(score=92, passed=True, issues=[], suggestions=[])
    assert review.passed is True
    assert review.score == 92
    assert review.attempts == 1


def test_quality_review_score_must_be_between_zero_and_one_hundred():
    with pytest.raises(ValidationError):
        LessonQualityReview(score=101, passed=True)


def test_old_lesson_without_quality_review_remains_compatible():
    lesson = Lesson.model_validate(valid_lesson_dict())
    assert lesson.quality_review is None


def test_quality_agent_returns_lesson_when_review_passes(monkeypatch):
    from app import services

    lesson = Lesson.model_validate(valid_lesson_dict())
    monkeypatch.setattr(services, "_gemini_json_response", lambda prompt: {
        "score": 95, "passed": True, "issues": [], "suggestions": []
    })
    reviewed, report = services.review_lesson(lesson, [{"title": "Source", "url": "https://example.com", "content": "Research"}])
    assert reviewed is lesson
    assert report.passed is True
    assert report.attempts == 1


def test_quality_agent_corrects_and_reviews_once_when_first_check_fails(monkeypatch):
    from app import services

    lesson = Lesson.model_validate(valid_lesson_dict())
    responses = iter([
        {"score": 65, "passed": False, "issues": ["Needs clearer explanation"], "suggestions": ["Clarify the introduction"]},
        valid_lesson_dict(),
        {"score": 90, "passed": True, "issues": [], "suggestions": []},
    ])
    monkeypatch.setattr(services, "_gemini_json_response", lambda prompt: next(responses))
    reviewed, report = services.review_lesson(lesson, [{"title": "Source", "url": "https://example.com", "content": "Research"}])
    assert reviewed.title == lesson.title
    assert report.passed is True
    assert report.attempts == 2


def test_visual_moment_supports_avatar_teaching_action():
    moment = VisualMoment.model_validate({
        "cue_text": "Notice how the water moves into the roots.",
        "scene": {"scene_type": "process", "title": "Water uptake", "items": ["Soil", "Roots"]},
        "avatar_action": "point_left",
    })
    assert moment.avatar_action == "point_left"


def test_old_visual_moment_defaults_to_explain_action():
    moment = VisualMoment.model_validate({
        "cue_text": "The heart pumps blood around the body.",
        "scene": {"scene_type": "process", "title": "Circulation", "items": ["Heart", "Blood"]},
    })
    assert moment.avatar_action == "explain"


def test_visual_moment_falls_back_to_explain_for_unknown_avatar_action():
    # An unusual gesture from the AI should not throw away a whole generated lesson.
    moment = VisualMoment.model_validate({
        "cue_text": "The heart pumps blood around the body.",
        "scene": {"scene_type": "process", "title": "Circulation", "items": ["Heart", "Blood"]},
        "avatar_action": "dance",
    })
    assert moment.avatar_action == "explain"



def test_groq_failure_automatically_fails_over_to_gemini(monkeypatch):
    from app import services

    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    monkeypatch.setenv("AI_PRIMARY_PROVIDER", "groq")

    def groq_fails(prompt, temperature):
        raise RuntimeError("rate limit")

    monkeypatch.setattr(services, "_call_groq_json", groq_fails)
    monkeypatch.setattr(services, "_call_gemini_json", lambda prompt, temperature: {"provider": "gemini"})

    assert services._ai_json_response("test prompt") == {"provider": "gemini"}


def test_gemini_can_be_primary_when_configured(monkeypatch):
    from app import services

    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    monkeypatch.setenv("AI_PRIMARY_PROVIDER", "gemini")

    calls = []
    monkeypatch.setattr(services, "_call_gemini_json", lambda prompt, temperature: calls.append("gemini") or {"ok": True})
    monkeypatch.setattr(services, "_call_groq_json", lambda prompt, temperature: calls.append("groq") or {"ok": True})

    assert services._ai_json_response("test prompt") == {"ok": True}
    assert calls == ["gemini"]


def test_missing_both_ai_keys_gives_configuration_error(monkeypatch):
    from app import services

    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(services.ConfigurationError):
        services._ai_json_response("test prompt")


# ---- Stage 10: lecturer beats -------------------------------------------------

def beat(say, items=None, **extra):
    return {
        "say": say,
        "avatar_action": extra.get("avatar_action", "point_left"),
        "scene": {
            "scene_type": extra.get("scene_type", "process"),
            "title": "A diagram",
            "description": "What it shows.",
            "items": items or ["Sunlight", "Leaf", "Glucose"],
            "details": ["Gives energy", "Captures it", "Stores it"],
            "icons": ["sun", "leaf", "coins"],
        },
    }


def beat_lesson_dict():
    data = valid_lesson_dict()
    for section in data["sections"]:
        del section["narration"]
        section["visual_moments"] = [
            beat("Look at the board now. Sunlight reaches the Leaf. That is where it starts."),
            beat("Watch the next diagram. The Leaf turns light into Glucose.", avatar_action="emphasize"),
            beat("So remember this. Glucose stores the energy for later."),
        ]
    return data


def test_narration_is_built_from_spoken_beats():
    from app.services import normalize_lesson_payload

    lesson = Lesson.model_validate(normalize_lesson_payload(beat_lesson_dict()))
    section = lesson.sections[0]
    assert section.narration.startswith("Look at the board now.")
    assert section.narration.endswith("stores the energy for later.")
    # every cue is an exact piece of the narration, in order
    position = -1
    for moment in section.visual_moments:
        found = section.narration.find(moment.cue_text)
        assert found > position
        position = found


def test_beats_survive_ensure_visual_moments_with_their_own_diagrams():
    from app.services import normalize_lesson_payload

    lesson = ensure_visual_moments(Lesson.model_validate(normalize_lesson_payload(beat_lesson_dict())))
    moments = lesson.sections[1].visual_moments
    assert len(moments) == 3
    assert moments[0].scene.icons == ["sun", "leaf", "coins"]
    assert moments[1].avatar_action == "emphasize"


def test_oversized_ai_lists_and_unknown_actions_are_tolerated():
    scene = VisualScene.model_validate({"items": [f"Label {n}" for n in range(9)], "details": ["x"] * 9, "icons": ["sun"] * 9})
    assert len(scene.items) == 6 and len(scene.details) == 6
    moment = VisualMoment.model_validate({"cue_text": "Look here now.", "scene": {}, "avatar_action": "wave wildly"})
    assert moment.avatar_action == "explain"
    assert VisualMoment.model_validate({"cue_text": "Look here now.", "scene": {}, "avatar_action": "point"}).avatar_action == "point_left"


def test_old_lessons_without_beats_still_load():
    lesson = ensure_visual_moments(Lesson.model_validate(valid_lesson_dict()))
    assert all(len(section.visual_moments) >= 1 for section in lesson.sections)


def test_generation_prompt_is_valid_and_mentions_the_board():
    import app.services as services

    captured = {}

    def fake_ai(prompt, temperature=0.2):
        captured["prompt"] = prompt
        return beat_lesson_dict()

    original = services._ai_json_response
    services._ai_json_response = fake_ai
    try:
        lesson = services.generate_lesson("Photosynthesis", None, [{"title": "t", "url": "https://example.com", "content": "c"}])
    finally:
        services._ai_json_response = original
    assert '"say"' in captured["prompt"] and "teaching board" in captured["prompt"]
    assert "{{" not in captured["prompt"]
    assert len(lesson.sections) == 4
