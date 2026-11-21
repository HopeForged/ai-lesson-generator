import json
import os
import re
from typing import Any

from app.models import Lesson, LessonQualityReview, VisualMoment, VisualScene


class ConfigurationError(Exception):
    pass


class ResearchError(Exception):
    pass


class GenerationError(Exception):
    pass


def research_topic(topic: str) -> list[dict[str, str]]:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ConfigurationError("TAVILY_API_KEY is missing. Add it to backend/.env.")

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        response = client.search(query=topic, search_depth="basic", max_results=5)
        results = response.get("results", [])
        cleaned = [
            {
                "title": str(item.get("title", "Untitled source")),
                "url": str(item.get("url", "")),
                "content": str(item.get("content", ""))[:1800],
            }
            for item in results
            if item.get("url") and item.get("content")
        ]
        if not cleaned:
            raise ResearchError("Web research returned no usable sources. Try another topic.")
        return cleaned
    except ResearchError:
        raise
    except Exception as exc:
        message = str(exc).lower()
        if any(word in message for word in ("connection", "network", "timeout", "dns")):
            raise ResearchError("Could not reach Tavily. Check your internet connection.") from exc
        if "401" in message or "403" in message:
            raise ConfigurationError("Tavily rejected the API key. Check TAVILY_API_KEY.") from exc
        raise ResearchError("Web research failed. Check your Tavily key and try again.") from exc


def _extract_json(raw_text: str) -> str:
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise GenerationError("The AI provider did not return a JSON response. Please try again.")
    return text[start : end + 1]


def _first_sentence(text: str, limit: int = 260) -> str:
    """Return the opening sentence of a spoken beat (always an exact prefix of the beat)."""
    text = text.strip()
    match = re.match(r".+?[.!?](?=\s|$)", text, flags=re.DOTALL)
    sentence = match.group(0) if match else text
    if len(sentence) > limit:
        sentence = sentence[:limit].rsplit(" ", 1)[0]
    return sentence.strip()


def normalize_lesson_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Build each section's narration from its spoken beats.

    The AI writes the lecture as beats (``say`` + diagram). Joining them guarantees that every
    cue_text is an exact piece of the narration, so the diagram changes exactly when the
    lecturer reaches that beat. Older / simpler payloads without ``say`` are left untouched.
    """
    sections = payload.get("sections") if isinstance(payload, dict) else None
    if not isinstance(sections, list):
        return payload
    for section in sections:
        if not isinstance(section, dict):
            continue
        moments = section.get("visual_moments")
        if not isinstance(moments, list):
            continue
        beats = [m for m in moments if isinstance(m, dict) and str(m.get("say", "")).strip()]
        if len(beats) < 2:
            continue
        beats = beats[:5]
        for beat in beats:
            beat["say"] = re.sub(r"\s+", " ", str(beat["say"])).strip()
            beat["cue_text"] = _first_sentence(beat["say"])
        section["visual_moments"] = beats
        section["narration"] = " ".join(beat["say"] for beat in beats)
    return payload


def _fallback_visual_moments(section) -> list[VisualMoment]:
    """Create sentence-linked visual beats if Gemini omits usable scene cues."""
    narration = section.narration.strip()
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", narration) if part.strip()]

    if len(sentences) < 3:
        words = narration.split()
        chunk_size = max(1, (len(words) + 2) // 3)
        sentences = [" ".join(words[index:index + chunk_size]) for index in range(0, len(words), chunk_size)]
        if len(sentences) > 1 and len(sentences[-1]) < 5:
            sentences[-2] = f"{sentences[-2]} {sentences[-1]}".strip()
            sentences.pop()

    selected = sentences[:4]
    points = section.slide.bullet_points or [section.slide.title, section.heading]
    moments: list[VisualMoment] = []
    for index, cue in enumerate(selected):
        primary = points[index % len(points)]
        secondary = points[(index + 1) % len(points)] if len(points) > 1 else section.heading
        lowered = cue.lower()
        if any(word in lowered for word in ("cycle", "loop", "repeat", "again and again")):
            scene_type = "cycle"
        elif any(word in lowered for word in ("first", "next", "then", "step", "process", "stage")):
            scene_type = "process"
        elif any(word in lowered for word in ("compare", "whereas", "difference", "unlike")):
            scene_type = "comparison"
        elif any(word in lowered for word in ("application", "healthcare", "education", "transport", "used in")):
            scene_type = "applications"
        else:
            scene_type = "concept"
        moments.append(VisualMoment(
            cue_text=cue[:280],
            scene=VisualScene(
                scene_type=scene_type,
                title=primary[:90],
                description=cue[:180],
                items=[primary[:70], secondary[:70]],
            ),
            avatar_action=(
                "point_left" if any(word in lowered for word in ("look", "shown", "notice", "observe"))
                else "emphasize" if any(word in lowered for word in ("important", "key", "remember", "therefore"))
                else "explain"
            ),
        ))
    return moments[:5]


def ensure_visual_moments(lesson: Lesson) -> Lesson:
    """Ensure every section has multiple visuals tied to spoken text."""
    for section in lesson.sections:
        narration_lower = section.narration.lower()
        usable = [
            moment for moment in section.visual_moments
            if moment.cue_text.strip().lower() in narration_lower
        ]
        if len(usable) >= 2 and (len(usable) >= 3 or all(m.say for m in usable)):
            section.visual_moments = usable[:5]
        else:
            section.visual_moments = _fallback_visual_moments(section)
    return lesson



def _provider_order() -> list[str]:
    primary = os.getenv("AI_PRIMARY_PROVIDER", "groq").strip().lower()
    if primary not in {"groq", "gemini"}:
        primary = "groq"
    return [primary, "gemini" if primary == "groq" else "groq"]


def _call_groq_json(prompt: str, temperature: float) -> dict[str, Any]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ConfigurationError("GROQ_API_KEY is not configured.")
    from groq import Groq

    client = Groq(api_key=api_key, timeout=90.0, max_retries=1)
    response = client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        messages=[
            {"role": "system", "content": "Return only a valid JSON object. Do not use markdown fences."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=temperature,
        max_tokens=12000,
    )
    content = response.choices[0].message.content or ""
    return json.loads(_extract_json(content))


def _call_gemini_json(prompt: str, temperature: float) -> dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ConfigurationError("GEMINI_API_KEY is not configured.")
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=temperature,
        ),
    )
    return json.loads(_extract_json(response.text or ""))


def _ai_json_response(prompt: str, temperature: float = 0.2) -> dict[str, Any]:
    """Try the primary AI provider, then automatically fail over to the other."""
    configured = {
        "groq": bool(os.getenv("GROQ_API_KEY")),
        "gemini": bool(os.getenv("GEMINI_API_KEY")),
    }
    if not any(configured.values()):
        raise ConfigurationError(
            "No AI API keys found. Add GROQ_API_KEY and/or GEMINI_API_KEY to backend/.env."
        )

    errors: list[str] = []
    for provider in _provider_order():
        if not configured[provider]:
            errors.append(f"{provider}: API key not configured")
            continue
        try:
            if provider == "groq":
                return _call_groq_json(prompt, temperature)
            return _call_gemini_json(prompt, temperature)
        except Exception as exc:
            # Any provider-side failure (quota, rate limit, temporary outage,
            # invalid response, or key problem) triggers the backup attempt.
            errors.append(f"{provider}: {type(exc).__name__}")
    tried = " and ".join(name for name in _provider_order() if configured[name])
    raise GenerationError(
        f"Both AI providers failed ({tried}). Check your API keys, model names, internet connection and usage limits."
    )


def _gemini_json_response(prompt: str) -> dict[str, Any]:
    """Backward-compatible name used by the quality-agent tests and workflow."""
    return _ai_json_response(prompt, temperature=0.1)


LEVEL_GUIDE = {
    "beginner": "Beginner: assume no prior knowledge, define every term, use simple everyday analogies.",
    "intermediate": "Intermediate: assume basic familiarity, explain mechanisms clearly, use relevant examples.",
    "advanced": "Advanced: assume a solid background, go deeper into mechanisms, trade-offs, edge cases and precise terminology.",
    "exam": "Exam preparation: focus on what is most likely to be tested, key definitions, formulas, common mistakes and memory aids; end sections with a quick recall prompt.",
}


def generate_lesson(
    topic: str,
    script: str | None,
    research: list[dict[str, str]],
    language: str = "English",
    level: str = "intermediate",
    material: str | None = None,
) -> Lesson:
    options = f"""LANGUAGE: Write ALL spoken text ("say"), slide text, diagram labels and details in {language}. Keep the JSON keys in English.
LEVEL: {LEVEL_GUIDE.get(level, LEVEL_GUIDE['intermediate'])}
"""
    if material:
        options += f"""STUDY MATERIAL: The student supplied the material below. Teach from it faithfully; it is the main source of truth. Use web research only to clarify or add context.
--- MATERIAL START ---
{material[:30000]}
--- MATERIAL END ---
"""
    prompt = f"""Create a clear educational lesson for the topic: {topic!r}.
{options}
You are writing the SCRIPT FOR A LIVE VIDEO LECTURE. A friendly human lecturer stands next to a teaching board. The board shows ONE diagram at a time, and the diagram changes every time the lecturer moves to the next beat. The lecturer speaks, points at the diagram, and explains it as it appears.

Return ONLY valid JSON with this structure:
{{"title":"...","topic":"...","introduction":"...","sections":[{{"heading":"...","slide":{{"title":"...","bullet_points":["...","..."]}},"visual_scene":{{"scene_type":"process","title":"...","description":"...","items":["...","..."]}},"visual_moments":[{{"say":"2 to 4 spoken sentences for this beat","avatar_action":"explain|point_left|emphasize|welcome","scene":{{"scene_type":"process|cycle|comparison|timeline|applications|network|structure|concept","title":"Short diagram title","description":"One sentence: what this diagram shows","items":["Label 1","Label 2","Label 3"],"details":["Short note about label 1","Short note about label 2","Short note about label 3"],"icons":["sun","leaf","droplets"]}}}}]}}],"sources":[{{"title":"...","url":"https://..."}}]}}

STRUCTURE
- 4 to 6 sections. Each section has a heading, slide (title + 2 to 6 bullet points), a fallback visual_scene, and 3 to 5 visual_moments (beats).
- Do NOT write a separate "narration" field. The narration is built automatically by joining the "say" text of the beats in order. Everything the lecturer says must be inside the "say" fields.
- Each beat's "say" is 2 to 4 natural spoken sentences (about 35 to 80 words). The lecture for a section is 3 to 5 beats long.

HOW THE LECTURER TEACHES (this matters most)
- Sound like a warm, confident university lecturer speaking to a class: contractions, direct address ("you", "we", "let's"), short sentences mixed with longer ones. Never read bullet points, never sound like a textbook or a voice-over.
- The FIRST sentence of every beat must direct the students' eyes to the board, e.g. "Now look at the diagram on the board.", "Let's turn to the illustration here.", "Watch what appears on the board now.", "Notice the three parts we have drawn." Vary the wording from beat to beat.
- Then EXPLAIN THE DIAGRAM as if pointing at it: go through the labels in the SAME ORDER as the "items" and mention each label using its exact words (e.g. "On the left you can see Sunlight arriving at the Leaf, and next to it...", "The arrow from Water to Glucose shows..."). The screen highlights each label while the lecturer says it, so the spoken order and the item order must match.
- Say what is changing or moving ("see how the arrow carries...", "notice this part grows..."), then say WHY it matters, then give a short everyday analogy or example where it helps.
- The opening beat of a section welcomes or introduces the idea (avatar_action "welcome" for the very first beat of the lesson, otherwise "explain"). Middle beats build the idea step by step. The last beat gives a one-sentence takeaway and a spoken transition to the next section ("Now that we know that, let's see how...").
- avatar_action: "point_left" when the lecturer directs attention to the board (use it for most diagram-explaining beats), "emphasize" for a key takeaway, "explain" for general talking, "welcome" only for a greeting. Vary them.

THE DIAGRAMS (each beat has its own)
- Every section must teach with its OWN diagrams about THAT section's specific content. Never reuse a generic diagram across sections, and the beats within a section must show different, progressively deeper diagrams (introduce the main parts, then the mechanism, then the result, example or application).
- scene_type chooses the layout:
  process = 3 to 5 ordered steps (arrows go left to right);
  cycle = 3 to 5 stages that loop back to the start;
  comparison = exactly 2 or 3 things side by side, details give their key characteristics;
  timeline = 3 to 5 events or phases in time order;
  applications = 3 to 5 real-world uses or examples;
  network = 4 to 6 connected parts that interact with each other;
  structure = ONE central object in items[0] with its 3 to 5 parts or ingredients in the remaining items;
  concept = ONE central idea in items[0] with 2 to 5 supporting ideas around it.
- items are short concrete labels (1 to 4 words), real names from the lesson content. Never use vague labels such as "Main idea", "Supporting detail", "Step 1", "Key concept".
- details: one short phrase (max 12 words) per item that says what that part does. Same length and order as items.
- icons: one icon per item, chosen from this list only: sun, leaf, droplets, wind, flame, snowflake, zap, atom, flask, dna, heart, brain, eye, ear, bone, cpu, database, network, server, cloud, shield, lock, key, globe, map, building, factory, home, car, plane, ship, train, rocket, book, pencil, calculator, chart, clock, calendar, coins, wallet, cart, truck, users, user, message, mail, phone, camera, music, video, lightbulb, target, flag, star, check, search, settings, wrench, hammer, tree, flower, mountain, wave, thermometer, microscope, pill, stethoscope, scale, gavel, graduation, trophy, puzzle, gear, code, wifi, battery, magnet.
- Design each diagram as a visual demonstration of objects, inputs, outputs, stages or relationships, not as a list of bullets.
- Also provide visual_scene as a short fallback summary diagram for older players.

OTHER RULES
- Use the research material below for current facts. Do not invent sources. Include the supplied research URLs in sources (an empty sources list is fine when there is no research).
- If a lecturer script or outline is supplied, keep its ideas and order as the backbone; check and enrich it using the research.
- The speech is read by a text-to-speech voice: avoid raw URLs, emojis, symbols such as arrows or "->", and unexplained abbreviations. Write chemical formulas and numbers the way you would say them.

Lecturer script or outline:
{script if script else 'No script supplied. Build the lesson from the topic.'}

Web research:
{json.dumps(research, ensure_ascii=False)}
"""
    try:
        payload = normalize_lesson_payload(_ai_json_response(prompt, temperature=0.3))
        lesson = Lesson.model_validate(payload)
        lesson.language, lesson.level = language, level
        return ensure_visual_moments(lesson)
    except (json.JSONDecodeError, ValueError) as exc:
        raise GenerationError("The AI provider returned invalid lesson data. Please try again.") from exc
    except (ConfigurationError, GenerationError):
        raise
    except Exception as exc:
        raise GenerationError("Lesson generation failed with both AI providers. Please try again.") from exc


def review_lesson(lesson: Lesson, research: list[dict[str, str]]) -> tuple[Lesson, LessonQualityReview]:
    'Review a generated lesson and make one correction attempt when needed.'
    research_context = json.dumps(
        [{"title": item.get("title", ""), "url": item.get("url", ""), "content": item.get("content", "")[:1400]}
         for item in research],
        ensure_ascii=False,
    )

    def run_review(candidate: Lesson) -> LessonQualityReview:
        prompt = f'''You are the independent quality assurance agent for an educational lesson.
Review the lesson against the supplied research. Check factual accuracy, whether claims are supported, clarity for beginners, completeness, consistency, and whether narration and visual moments agree. Also check that every section has its own distinct diagrams, that each beat's spoken text (the 'say' fields) refers to the diagram on the board and walks through its labels in order like a real lecturer, rather than merely reading slide bullets, and that the diagram contents are factually correct.
Do not mark a claim false merely because the sources are brief. If evidence is insufficient, identify it as unsupported or needing verification.
Return ONLY JSON with this exact shape:
{{"score": 0, "passed": false, "issues": ["specific issue"], "suggestions": ["specific improvement"]}}
Use a score from 0 to 100. Set passed=true only when there are no serious factual problems and the lesson is clear and coherent. A score of 80 or higher is normally a pass.
LESSON:
{candidate.model_dump_json()}
RESEARCH SOURCES:
{research_context}'''
        data = _gemini_json_response(prompt)
        data.setdefault("issues", [])
        data.setdefault("suggestions", [])
        data["score"] = max(0, min(100, int(data.get("score", 0))))
        data["passed"] = bool(data.get("passed", False)) and data["score"] >= 80
        return LessonQualityReview.model_validate(data)

    first_review = run_review(lesson)
    if first_review.passed:
        first_review.attempts = 1
        return lesson, first_review

    correction_prompt = f'''You are correcting an educational lesson after quality review.
Revise the lesson to address the review issues. Keep the same topic and preserve valid content. Do not invent facts or sources. Use only the supplied research for factual corrections. Preserve the required lesson structure. The narration is built from the 'say' text of each visual moment, so make all spoken corrections inside the 'say' fields and keep each beat's diagram (scene items, details and icons) consistent with what is said. Keep the lecturer style: each beat directs attention to the board and explains the diagram label by label.
Return ONLY the complete corrected lesson JSON with title, topic, introduction, sections, slide, visual_scene, visual_moments and sources. Do not include a quality_review field.
REVIEW ISSUES: {json.dumps(first_review.issues, ensure_ascii=False)}
REVIEW SUGGESTIONS: {json.dumps(first_review.suggestions, ensure_ascii=False)}
RESEARCH SOURCES: {research_context}
LESSON TO CORRECT: {lesson.model_dump_json()}'''
    corrected_data = _gemini_json_response(correction_prompt)
    corrected_data.pop("quality_review", None)
    corrected = ensure_visual_moments(Lesson.model_validate(normalize_lesson_payload(corrected_data)))
    corrected.language, corrected.level = lesson.language, lesson.level
    second_review = run_review(corrected)
    second_review.attempts = 2
    return corrected, second_review



def build_lesson(request, progress=None) -> Lesson:
    """Research -> write -> quality check. ``progress(percent, message)`` is called along the way."""
    say = progress or (lambda percent, message: None)
    say(6, "Researching the topic on the web")
    research: list[dict[str, str]] = []
    try:
        research = research_topic(request.topic)
    except (ConfigurationError, ResearchError):
        if not request.material:  # without study material the research is essential
            raise
    say(28, "Writing the lecture and planning the diagrams")
    lesson = generate_lesson(
        request.topic, request.script, research,
        language=request.language, level=request.level, material=request.material,
    )
    say(72, "Quality-checking the facts and the teaching flow")
    lesson, lesson.quality_review = review_lesson(lesson, research)
    try:  # animations are an upgrade: if the director fails, the plain diagrams still teach
        from app.director import add_animations

        add_animations(lesson, say)
    except Exception:
        pass
    say(97, "Almost ready")
    return lesson
