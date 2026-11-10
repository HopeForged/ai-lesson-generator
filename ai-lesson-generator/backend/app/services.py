import json
import os
import re
from typing import Any

from app.models import Lesson, VisualMoment, VisualScene


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
        raise GenerationError("Gemini did not return a JSON lesson. Please try again.")
    return text[start : end + 1]


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
        if any(word in lowered for word in ("first", "next", "then", "step", "process", "stage")):
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
        if len(usable) >= 3:
            section.visual_moments = usable[:5]
        else:
            section.visual_moments = _fallback_visual_moments(section)
    return lesson


def generate_lesson(topic: str, script: str | None, research: list[dict[str, str]]) -> Lesson:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ConfigurationError("GEMINI_API_KEY is missing. Add it to backend/.env.")

    prompt = f"""Create a clear educational lesson for the topic: {topic!r}.
Return ONLY valid JSON matching this structure:
{{"title":"...","topic":"...","introduction":"...","sections":[{{"heading":"...","narration":"Speaking-friendly explanation, at least 20 characters.","slide":{{"title":"...","bullet_points":["...","..."]}},"visual_scene":{{"scene_type":"concept|process|comparison|timeline|applications|network|generic","title":"Short scene title","description":"One short sentence describing the visual explanation","items":["Short visual label 1","Short visual label 2"]}},"visual_moments":[{{"cue_text":"An exact sentence copied from the narration","scene":{{"scene_type":"concept|process|comparison|timeline|applications|network|generic","title":"Scene title","description":"What this moment should demonstrate","items":["Visual element 1","Visual element 2","Visual element 3"]}}}}]}}],"sources":[{{"title":"...","url":"https://..."}}]}}
Requirements:
- Include 4 to 6 sections, each with a heading, narration, slide title and 2 to 6 bullet points.
- For EVERY section, create 3 to 5 visual_moments. These are separate visual scenes that change DURING the narration, not one static slide for the whole section.
- Each visual_moment must have cue_text copied EXACTLY as a complete sentence from that section's narration. Do not paraphrase the cue. The cues must appear in the same order as the narration and must not overlap.
- Give every visual_moment its own scene with a suitable scene_type, short title, one-sentence description and 2 to 5 concise visual labels.
- Make the scenes visibly different and progressively explain the lesson: introduce the idea, demonstrate a mechanism or steps, then show an example, result or application where appropriate.
- Choose scene_type: concept for one main idea, process for ordered steps, comparison for differences, timeline for events over time, applications for real-world uses, network for connected parts, or generic when none fit.
- The visual_moments must match the exact narration passage they are linked to. Do not repeat the same scene or generic labels throughout a section.
- Also provide visual_scene as a fallback summary scene for older players.
- Use the research material below for current facts. Do not invent sources.
- Narration must sound natural when read aloud. Avoid raw URLs and awkward symbols.
- If a lecturer script is supplied, preserve its ideas and order as the lesson backbone; check and enrich it using research rather than replacing it.
- Include the supplied research URLs in sources.

Lecturer script or outline:
{script if script else 'No script supplied. Build the lesson from the topic.'}

Web research:
{json.dumps(research, ensure_ascii=False)}
"""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3,
            ),
        )
        raw_text = response.text or ""
        payload: Any = json.loads(_extract_json(raw_text))
        lesson = Lesson.model_validate(payload)
        return ensure_visual_moments(lesson)
    except (json.JSONDecodeError, ValueError) as exc:
        raise GenerationError("Gemini returned a lesson with invalid JSON or missing required fields. Try again.") from exc
    except GenerationError:
        raise
    except Exception as exc:
        message = str(exc).lower()
        if any(word in message for word in ("429", "resource_exhausted", "rate limit", "quota")):
            raise GenerationError("Gemini rate limit reached. Wait a little and try again.") from exc
        if any(word in message for word in ("connection", "network", "timeout", "dns")):
            raise GenerationError("Could not reach Gemini. Check your internet connection.") from exc
        if "api key" in message or "401" in message or "403" in message:
            raise ConfigurationError("Gemini rejected the API key. Check GEMINI_API_KEY.") from exc
        raise GenerationError("Lesson generation failed. Please try again.") from exc
