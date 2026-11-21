"""Ask the lecturer: a student's question becomes one more teaching beat (speech + diagram)."""
import json
from typing import Any

from app.models import VisualScene
from app.services import GenerationError, _ai_json_response, normalize_lesson_payload  # noqa: F401


def ask_lecturer(lesson: dict[str, Any], section_index: int, question: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    sections = lesson.get("sections", [])
    section_index = max(0, min(section_index, len(sections) - 1))
    current = sections[section_index] if sections else {}
    outline = [{"heading": s.get("heading"), "points": (s.get("slide") or {}).get("bullet_points", [])} for s in sections]
    language = lesson.get("language", "English")
    prompt = f"""You are the friendly university lecturer of the lesson {lesson.get('title')!r}. A student interrupts with a question.
Answer it the way a great lecturer would at the board: first one short sentence acknowledging the question, then a clear explanation in 3 to 6 spoken sentences (about 60 to 120 words), with a simple example or analogy, and end by checking they are following.
Speak in {language}. Plain spoken text only: no markdown, bullet points, emojis, or symbols. Use the lesson content below as your basis. If the question is unrelated to the lesson, answer briefly and steer back to the lesson.
Also draw ONE diagram for the board that illustrates your answer, and refer to it while you speak ("look at the board", then walk through its labels in order, using their exact words).
Return ONLY valid JSON:
{{"say":"...","avatar_action":"point_left","scene":{{"scene_type":"process|cycle|comparison|timeline|applications|network|structure|concept","title":"...","description":"...","items":["3 to 5 short labels"],"details":["short note per label"],"icons":["one icon name per label"]}}}}
Valid icon names include: sun leaf droplets wind flame zap atom flask dna heart brain eye cpu database network server cloud shield lock key globe map building factory home car plane rocket book pencil calculator chart clock calendar coins users user message lightbulb target flag star check search settings wrench tree mountain microscope scale gear code.
LESSON OUTLINE: {json.dumps(outline, ensure_ascii=False)}
CURRENT SECTION (the student is here): {json.dumps({'heading': current.get('heading'), 'lecture': str(current.get('narration', ''))[:2500]}, ensure_ascii=False)}
EARLIER QUESTIONS: {json.dumps((history or [])[-4:], ensure_ascii=False)}
STUDENT QUESTION: {question!r}"""
    data = _ai_json_response(prompt, temperature=0.4)
    say = " ".join(str(data.get("say", "")).split())
    if len(say) < 20:
        raise GenerationError("The lecturer could not answer that. Please rephrase the question.")
    scene = VisualScene.model_validate(data.get("scene") or {})
    action = data.get("avatar_action") if data.get("avatar_action") in ("explain", "point_left", "emphasize") else "point_left"
    result = {"say": say[:1600], "avatar_action": action, "scene": scene.model_dump()}
    try:  # animate the answer too; ignore any failure
        from app.director import animate_answer

        result["scene"]["animation"] = animate_answer(result["say"], result["scene"], language)
    except Exception:
        pass
    return result
