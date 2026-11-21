"""The animation director: after a lesson is written, plan the motion for every teaching beat."""
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from app.animation import clean_animation
from app.beats import build_beats
from app.services import _ai_json_response

ICON_LIST = ("sun leaf droplets wind flame snowflake zap atom flask dna heart brain eye ear bone cpu database network server "
             "cloud shield lock key globe map building factory home car plane ship train rocket book pencil calculator chart clock "
             "calendar coins wallet cart truck users user message mail phone camera music video lightbulb target flag star check "
             "search settings wrench hammer tree flower mountain wave thermometer microscope pill stethoscope scale gavel graduation "
             "trophy puzzle gear code wifi battery magnet")

DIRECTOR_RULES = f"""You are the animation director for a video lecture. For each beat below, design ONE short animated scene for the teaching board that SHOWS what the lecturer is explaining, as things moving and changing, not as a static list.

An animation is JSON: {{"actors":[...],"steps":[...]}}

ACTORS (max 7 per beat) are labelled things on a stage. The stage is a grid from x=0..100 (left to right) and y=0..100 (top to bottom). Keep actors at least 22 apart. Use x between 12 and 88 and y between 22 and 78.
  {{"id":"bank","label":"Bank","icon":"building","x":75,"y":50,"detail":"optional short note"}}
  Optional "kind": "node" (default), "counter" (a big number; use "prefix"/"suffix" like "$" or "%"), "meter" (a progress bar), "chart" (needs "series":[[numbers],[numbers]] up to 3 lines of 2 to 12 numbers, optional "series_names", and "chart_type":"line" or "bar"), "svg" (your own small animated drawing: "svg":"<svg viewBox='0 0 100 100'>...</svg>", only shapes, may use <animate>/<animateTransform>, under 1500 characters).
  Use icons from: {ICON_LIST}.

STEPS (4 to 9 per beat, in the order the lecturer talks). Every step has "do", "actor" and "say":
  appear / disappear: actor shows up or leaves.
  move: actor glides to "x","y".
  send: a token (with "text" and optional "icon") travels from "actor" to "to". stream: same but several tokens.
  pulse: actor lights up to draw attention. grow / shrink: actor scales ("value" 1.3 or 0.7).
  transform: actor turns into something else (new "text" label and "icon").
  fill: actor's progress bar fills to "value" (0 to 100). count: actor's number counts up/down to "value".
  check / cross: a tick or a cross appears on the actor. orbit: actor circles around "to".
  shake: actor shakes (a problem or error). draw: chart actor draws line/bars of "series" (0,1,2). shift: chart line "series" moves by "x","y" (use small numbers like 10 or -10).
"say" is the TRIGGER: copy 1 to 4 words EXACTLY as they appear in that beat's spoken text, in the order they are spoken. The step happens when the lecturer says those words. Never invent words that are not in the text.

QUALITY RULES
- Show the real mechanism of THIS topic: what goes in, what moves where, what changes, what the result is. Use the topic's own actors and names (Customer, Server, Voter, Enzyme, Invoice, Water, Demand...).
- Start with 'appear' steps for the main actors as they are first mentioned, then show the action.
- Prefer 3 to 6 actors. Every actor must be used by at least one step.
- Choose the stage that fits: movements between actors for processes; "chart" for trends, supply and demand, growth; "counter"/"meter" for amounts and scores.

EXAMPLE for a beat saying: "Here is the customer. They ask the bank for a loan. The bank checks their credit score, and then the money moves to the customer."
{{"actors":[{{"id":"customer","label":"Customer","icon":"user","x":18,"y":55}},{{"id":"bank","label":"Bank","icon":"building","x":82,"y":55}},{{"id":"score","label":"Credit score","icon":"chart","kind":"meter","x":50,"y":28}},{{"id":"cash","label":"Loan","icon":"coins","kind":"counter","prefix":"$","x":50,"y":78}}],
"steps":[{{"do":"appear","actor":"customer","say":"customer"}},{{"do":"appear","actor":"bank","say":"bank"}},{{"do":"send","actor":"customer","to":"bank","text":"Loan request","icon":"mail","say":"ask the bank"}},{{"do":"fill","actor":"score","value":80,"say":"credit score"}},{{"do":"check","actor":"bank","say":"checks"}},{{"do":"count","actor":"cash","value":10000,"say":"money"}},{{"do":"send","actor":"bank","to":"customer","text":"$10,000","icon":"coins","say":"moves to the customer"}}]}}

Return ONLY valid JSON: {{"beats":[{{"index":0,"animation":{{...}}}}]}} with one entry per beat index given."""


def _call_director(heading: str, language: str, beats: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    payload = [{"index": i, "diagram_title": b["scene"].get("title", ""), "labels": b["scene"].get("items", []), "text": b["text"]} for i, b in enumerate(beats)]
    prompt = f"""{DIRECTOR_RULES}

Language of the labels and the "text" fields: {language}. The "say" triggers must match the spoken text exactly, in its own language.
SECTION: {heading}
BEATS: {json.dumps(payload, ensure_ascii=False)}"""
    data = _ai_json_response(prompt, temperature=0.4)
    out: dict[int, dict[str, Any]] = {}
    for entry in data.get("beats", []) if isinstance(data, dict) else []:
        try:
            cleaned = clean_animation(entry.get("animation"))
            if cleaned:
                out[int(entry["index"])] = cleaned
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    return out


def direct_section(section, language: str = "the lesson language") -> int:
    """Attach animations to a LessonSection's moments. Returns how many beats got one. Never raises."""
    try:
        beats = build_beats(section.model_dump())
        if not beats:
            return 0
        plans = _call_director(section.heading, language, beats)
    except Exception:
        return 0
    by_cue = {m.cue_text: m for m in section.visual_moments}
    attached = 0
    for i, beat in enumerate(beats):
        moment = by_cue.get(beat.get("cue_text", ""))
        if moment is not None and i in plans:
            moment.scene.animation = plans[i]
            attached += 1
    return attached


def add_animations(lesson, progress: Callable[[float, str], None] | None = None) -> int:
    """Run the director on every section (2 at a time). Failures only mean a plain diagram for that beat."""
    say = progress or (lambda p, m: None)
    total = len(lesson.sections)
    done = 0

    def work(section) -> int:
        return direct_section(section, lesson.language)

    count = 0
    with ThreadPoolExecutor(max_workers=2) as pool:
        for attached in pool.map(work, lesson.sections):
            done += 1
            count += attached
            say(76 + 20 * done / total, f"Animating the diagrams ({done}/{total})")
    return count


def animate_answer(say_text: str, scene: dict[str, Any], language: str) -> dict[str, Any] | None:
    """One animation for an Ask-the-lecturer answer. Returns None on any problem."""
    try:
        beat = {"text": say_text, "scene": scene}
        plans = _call_director("Student question", language, [beat])
        return plans.get(0)
    except Exception:
        return None
