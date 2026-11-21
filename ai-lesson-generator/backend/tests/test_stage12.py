import app.director as director
from app.animation import clean_animation, sanitize_svg
from app.models import VisualScene

GOOD = {
    "actors": [{"id": "a", "label": "Customer", "icon": "user", "x": 20, "y": 50}, {"id": "b", "label": "Bank", "icon": "building", "x": 80, "y": 50}],
    "steps": [{"do": "appear", "actor": "a", "say": "customer"}, {"do": "send", "actor": "a", "to": "b", "text": "Loan", "say": "asks"}, {"do": "check", "actor": "b", "say": "checks"}],
}


def test_clean_animation_accepts_good_and_rejects_thin():
    out = clean_animation(GOOD)
    assert out and len(out["actors"]) == 2 and len(out["steps"]) == 3
    assert clean_animation({"actors": GOOD["actors"][:1], "steps": GOOD["steps"]}) is None
    assert clean_animation("nonsense") is None
    assert clean_animation(None) is None


def test_clean_animation_drops_bad_steps_and_clamps():
    bad = {"actors": [dict(GOOD["actors"][0], x=500), GOOD["actors"][1]],
           "steps": GOOD["steps"] + [{"do": "explode", "actor": "a"}, {"do": "move", "actor": "ghost"}]}
    out = clean_animation(bad)
    assert out and all(s["do"] != "explode" for s in out["steps"]) and all(s["actor"] != "ghost" for s in out["steps"])
    assert max(a["x"] for a in out["actors"]) <= 92


def test_sanitize_svg_blocks_scripts_and_handlers():
    assert sanitize_svg("<svg><script>alert(1)</script></svg>") is None
    cleaned = sanitize_svg("<svg viewBox='0 0 10 10' onload='x()'><circle cx='5' cy='5' r='3' onclick='y()' style='fill:red'/></svg>")
    assert cleaned and "onload" not in cleaned and "onclick" not in cleaned and "style" not in cleaned and "circle" in cleaned


def test_visual_scene_never_raises_on_bad_animation():
    assert VisualScene(scene_type="process", title="t", animation={"actors": "x"}).animation is None
    assert VisualScene(scene_type="process", title="t", animation=GOOD).animation is not None


def test_director_attaches_by_cue_and_survives_failure(monkeypatch):
    from tests.test_models import beat_lesson_dict
    from app.models import Lesson
    from app.services import normalize_lesson_payload

    lesson = Lesson.model_validate(normalize_lesson_payload(beat_lesson_dict()))
    monkeypatch.setattr(director, "_ai_json_response", lambda prompt, temperature=0.4: {"beats": [{"index": 0, "animation": GOOD}]})
    count = director.add_animations(lesson)
    assert count >= 1
    assert any(m.scene.animation for s in lesson.sections for m in s.visual_moments)

    def boom(*a, **k):
        raise RuntimeError("ai down")

    lesson2 = Lesson.model_validate(normalize_lesson_payload(beat_lesson_dict()))
    monkeypatch.setattr(director, "_ai_json_response", boom)
    assert director.add_animations(lesson2) == 0
