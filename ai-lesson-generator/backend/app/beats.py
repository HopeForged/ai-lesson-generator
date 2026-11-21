"""Python twin of frontend/src/lectureUtils.js: turns a section into teaching beats
(spoken text + diagram + gesture). Used by the video exporter so the video matches the live player."""
import re
from typing import Any


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.findall(r"[^.!?]+[.!?]+[\"')\]]*|[^.!?]+$", text or "") if s.strip()]


def _infer_scene_type(text: str) -> str:
    value = text.lower()
    if re.search(r"\b(cycle|loop|repeat|again and again)\b", value):
        return "cycle"
    if re.search(r"\b(first|next|then|step|process|stage|sequence)\b", value):
        return "process"
    if re.search(r"\b(compare|whereas|difference|unlike|however)\b", value):
        return "comparison"
    if re.search(r"\b(application|healthcare|education|transport|used in|for example)\b", value):
        return "applications"
    if re.search(r"\b(network|connected|communicate|relationship)\b", value):
        return "network"
    return "concept"


def _fallback_moments(section: dict[str, Any]) -> list[dict[str, Any]]:
    narration = section.get("narration", "")
    chunks = split_sentences(narration)
    if len(chunks) < 2:
        words = narration.split()
        size = max(1, -(-len(words) // 3))
        chunks = [" ".join(words[i:i + size]) for i in range(0, len(words), size)]
    groups = min(4, max(1, -(-len(chunks) // 2)))
    per = -(-len(chunks) // groups)
    texts = [" ".join(chunks[i:i + per]) for i in range(0, len(chunks), per)]
    bullets = (section.get("slide") or {}).get("bullet_points") or [section.get("heading") or "Key idea"]
    out = []
    for index, text in enumerate(texts):
        items = []
        for k in range(3):
            item = bullets[(index + k) % len(bullets)]
            if item not in items:
                items.append(item)
        if len(items) < 2:
            items.append(section.get("heading") or "Key idea")
        out.append({
            "cue_text": (split_sentences(text) or [text])[0],
            "avatar_action": "welcome" if index == 0 else "explain",
            "scene": {"scene_type": _infer_scene_type(text), "title": bullets[index % len(bullets)],
                      "description": section.get("heading", ""), "items": items[:3]},
        })
    return out


def build_beats(section: dict[str, Any]) -> list[dict[str, Any]]:
    narration = section.get("narration", "")
    if not narration:
        return []
    lower = narration.lower()
    mapped, cursor = [], 0
    for moment in section.get("visual_moments") or []:
        cue = str(moment.get("cue_text", "")).strip()
        if not cue:
            continue
        start = lower.find(cue.lower(), cursor)
        if start < 0:
            start = lower.find(" ".join(cue.split()[:5]).lower(), cursor)
        if start < 0:
            continue
        cursor = start + 1
        mapped.append({**moment, "start": start})
    if len(mapped) < 2:
        mapped, at = [], 0
        for moment in _fallback_moments(section):
            found = lower.find(moment["cue_text"].lower(), at)
            start = found if found >= 0 else at
            at = start + 1
            mapped.append({**moment, "start": start})
    deduped = []
    for m in mapped:
        if not deduped or m["start"] > deduped[-1]["start"]:
            deduped.append(m)
    deduped[0]["start"] = 0
    beats = []
    for i, m in enumerate(deduped):
        end = deduped[i + 1]["start"] if i + 1 < len(deduped) else len(narration)
        beats.append({**m, "end": end, "text": narration[m["start"]:end].strip(),
                      "scene": m.get("scene") or section.get("visual_scene") or {}})
    return beats
