"""Animated board scenes.

The AI "director" describes a scene with a small, topic-independent vocabulary:
actors (labelled things on a stage) and steps (appear, move, send, fill, count, ...).
Each step is triggered by a phrase the lecturer says, so the motion follows the speech.
Everything is validated here; anything unusable is dropped (the plain diagram is the fallback).
"""
import re
import xml.etree.ElementTree as ET
from typing import Any

ACTIONS = (
    "appear", "disappear", "move", "send", "stream", "pulse", "grow", "shrink", "transform",
    "fill", "count", "check", "cross", "orbit", "shake", "draw", "shift",
)
KINDS = ("node", "counter", "meter", "chart", "svg")

SVG_TAGS = {"svg", "g", "path", "circle", "ellipse", "rect", "line", "polygon", "polyline", "text", "tspan",
            "defs", "lineargradient", "radialgradient", "stop", "animate", "animatetransform", "animatemotion"}
SVG_ATTRS = {
    "viewbox", "width", "height", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "d", "points",
    "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "stroke-dasharray", "opacity",
    "fill-opacity", "stroke-opacity", "transform", "id", "offset", "stop-color", "stop-opacity", "text-anchor",
    "font-size", "font-weight", "font-family", "dominant-baseline", "gradientunits", "x1", "attributename",
    "attributetype", "from", "to", "values", "dur", "begin", "repeatcount", "keytimes", "type", "additive",
    "calcmode", "path", "rotate", "preserveaspectratio",
}


def _num(value: Any, low: float, high: float, default: float | None = None) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def _text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")[:24]


def sanitize_svg(markup: str) -> str | None:
    """Keep only harmless drawing tags/attributes. Returns None if the drawing is not acceptable."""
    markup = (markup or "").strip()
    if not markup or len(markup) > 4000 or "<!" in markup or "<?" in markup or "javascript:" in markup.lower():
        return None
    try:
        root = ET.fromstring(markup)
    except ET.ParseError:
        return None

    def local(name: str) -> str:
        return name.split("}")[-1].lower()

    if local(root.tag) != "svg":
        return None

    def clean(node: ET.Element) -> bool:
        if local(node.tag) not in SVG_TAGS:
            return False
        node.tag = node.tag.split("}")[-1]
        for attr in list(node.attrib):
            key = attr.split("}")[-1].lower()
            value = node.attrib.pop(attr)
            if key not in SVG_ATTRS or key.startswith("on") or re.search(r"url\(|javascript|data:|<|>", value, re.I):
                continue
            node.attrib[attr.split("}")[-1]] = value
        return all(clean(child) for child in list(node))

    if not clean(root):
        return None
    root.attrib.setdefault("viewBox", "0 0 100 100")
    out = ET.tostring(root, encoding="unicode")
    out = re.sub(r"\sxmlns(:\w+)?=\"[^\"]*\"", "", out)
    return out.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)


def _clean_actor(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    actor_id = _slug(raw.get("id") or raw.get("label"))
    label = _text(raw.get("label"), 40)
    if not actor_id:
        return None
    kind = str(raw.get("kind") or "node").lower()
    kind = kind if kind in KINDS else "node"
    actor: dict[str, Any] = {
        "id": actor_id, "label": label or actor_id.replace("_", " ").title(), "kind": kind,
        "icon": _text(raw.get("icon"), 24).lower(), "detail": _text(raw.get("detail"), 60),
        "x": _num(raw.get("x"), 8, 92, 50), "y": _num(raw.get("y"), 14, 86, 50),
        "prefix": _text(raw.get("prefix"), 6), "suffix": _text(raw.get("suffix"), 8),
    }
    if kind == "chart":
        series = []
        for line in raw.get("series") or []:
            if isinstance(line, list):
                nums = [_num(v, -1e9, 1e9) for v in line[:12]]
                if len(nums) >= 2 and None not in nums:
                    series.append(nums)
        if not series:
            return None
        actor["series"] = series[:3]
        actor["series_names"] = [_text(n, 24) for n in (raw.get("series_names") or [])[:3]]
        actor["chart_type"] = "bar" if str(raw.get("chart_type")).lower() == "bar" else "line"
    if kind == "svg":
        svg = sanitize_svg(str(raw.get("svg") or ""))
        if not svg:
            actor["kind"] = "node"
        else:
            actor["svg"] = svg
    return actor


def clean_animation(raw: Any) -> dict[str, Any] | None:
    """Validate a director's animation. Returns None when it is not usable."""
    if not isinstance(raw, dict):
        return None
    actors: dict[str, dict[str, Any]] = {}
    for item in (raw.get("actors") or [])[:10]:
        actor = _clean_actor(item)
        if actor and actor["id"] not in actors:
            actors[actor["id"]] = actor
    steps = []
    for item in (raw.get("steps") or [])[:20]:
        if not isinstance(item, dict):
            continue
        action = str(item.get("do") or item.get("action") or "").strip().lower()
        if action not in ACTIONS:
            continue
        actor_id, to_id = _slug(item.get("actor") or item.get("from")), _slug(item.get("to"))
        if actor_id not in actors:
            continue
        if action in ("send", "stream", "orbit") and to_id not in actors:
            continue
        if action in ("draw", "shift") and actors[actor_id]["kind"] != "chart":
            continue
        steps.append({
            "do": action, "actor": actor_id, "to": to_id if to_id in actors else "",
            "x": _num(item.get("x"), 8, 92), "y": _num(item.get("y"), 14, 86),
            "say": _text(item.get("say"), 80), "text": _text(item.get("text") or item.get("item"), 40),
            "icon": _text(item.get("icon"), 24).lower(), "value": _num(item.get("value"), -1e9, 1e9),
            "series": int(_num(item.get("series"), 0, 2, 0)),
        })
    used = {s["actor"] for s in steps} | {s["to"] for s in steps if s["to"]}
    actors = {k: v for k, v in actors.items() if k in used}
    steps = [s for s in steps if s["actor"] in actors]
    if len(actors) < 2 or len(steps) < 3:
        return None
    return {"actors": list(actors.values())[:8], "steps": steps[:16]}
