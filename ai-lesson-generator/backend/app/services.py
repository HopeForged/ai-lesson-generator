import json
import os
import re
from typing import Any

from app.models import Lesson


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


def generate_lesson(topic: str, script: str | None, research: list[dict[str, str]]) -> Lesson:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ConfigurationError("GEMINI_API_KEY is missing. Add it to backend/.env.")

    prompt = f"""Create a clear educational lesson for the topic: {topic!r}.
Return ONLY valid JSON matching this structure:
{{"title":"...","topic":"...","introduction":"...","sections":[{{"heading":"...","narration":"Speaking-friendly explanation, at least 20 characters.","slide":{{"title":"...","bullet_points":["...","..."]}}}}],"sources":[{{"title":"...","url":"https://..."}}]}}
Requirements:
- Include 4 to 6 sections, each with a heading, narration, slide title and 2 to 6 bullet points.
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
        return Lesson.model_validate(payload)
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
