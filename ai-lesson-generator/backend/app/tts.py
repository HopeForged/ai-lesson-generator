"""Text-to-speech with exact word timings.

Providers (free):
  edge    - Microsoft Edge neural voices through the `edge-tts` package. No API key, needs internet.
  espeak  - offline robotic fallback, used only if the `espeak-ng` program is installed.
  silent  - no voice at all; timings are estimated. Used only for captions-only videos.
TTS_PROVIDER=auto (default) tries edge, then espeak. The result's "provider" tells the caller what was used.
"""
import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app import config


class VoiceUnavailable(Exception):
    pass


_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(key: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock())


def _key(text: str, voice: str, rate: float, provider: str) -> str:
    return hashlib.sha1(f"{provider}|{voice}|{rate:.2f}|{text}".encode("utf-8")).hexdigest()[:24]


def audio_duration(path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, timeout=60,
    )
    try:
        return float(out.stdout.strip())
    except ValueError as exc:
        raise VoiceUnavailable("Could not read the generated audio file (is ffmpeg installed?).") from exc


def estimate_words(text: str, duration: float) -> list[dict[str, float]]:
    """Spread the words over the duration in proportion to their length (+ a pause after punctuation)."""
    matches = list(re.finditer(r"\S+", text))
    if not matches:
        return []
    weights = [len(m.group()) + (4 if re.search(r"[.!?]$", m.group()) else 2 if re.search(r"[,;:]$", m.group()) else 0) + 1 for m in matches]
    total = sum(weights)
    out, at = [], 0.0
    for m, w in zip(matches, weights):
        span = duration * w / total
        out.append({"c": m.start(), "s": round(at, 3), "e": round(at + span * 0.92, 3)})
        at += span
    return out


def map_boundaries(text: str, boundaries: list[dict[str, Any]]) -> list[dict[str, float]]:
    """Edge gives word + time but no character offset, so find each word in the text in order."""
    lower, cursor, out = text.lower(), 0, []
    for b in boundaries:
        word = str(b["text"]).strip().lower()
        if not word:
            continue
        at = lower.find(word, cursor)
        if at < 0:
            at = lower.find(word[: max(2, len(word) // 2)], cursor)
        if at < 0:
            continue
        cursor = at + 1
        out.append({"c": at, "s": round(b["start"], 3), "e": round(b["start"] + b["dur"], 3)})
    return out


# ---------------- providers ----------------
async def _edge_stream(text: str, voice: str, rate: float, audio_path):
    import edge_tts

    pct = round((rate - 1) * 100)
    kwargs = {"rate": f"{pct:+d}%"}
    try:
        comm = edge_tts.Communicate(text, voice, boundary="WordBoundary", **kwargs)
    except TypeError:  # older edge-tts versions only emit word boundaries anyway
        comm = edge_tts.Communicate(text, voice, **kwargs)
    boundaries = []
    with open(audio_path, "wb") as handle:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                handle.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                boundaries.append({"text": chunk["text"], "start": chunk["offset"] / 1e7, "dur": chunk["duration"] / 1e7})
    return boundaries


def _edge(text, voice, rate, audio_path):
    try:
        import edge_tts  # noqa: F401
    except ImportError as exc:
        raise VoiceUnavailable("The free voice engine is not installed. Run: pip install edge-tts") from exc
    try:
        boundaries = asyncio.run(_edge_stream(text, voice, rate, audio_path))
    except Exception as exc:
        raise VoiceUnavailable(f"The voice service could not be reached ({type(exc).__name__}). Check your internet connection.") from exc
    if not audio_path.exists() or audio_path.stat().st_size < 500:
        raise VoiceUnavailable("The voice service returned no audio.")
    duration = audio_duration(audio_path)
    words = map_boundaries(text, boundaries) or estimate_words(text, duration)
    return duration, words


def _espeak(text, voice, rate, audio_path):
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe:
        raise VoiceUnavailable("espeak is not installed.")
    wav = audio_path.with_suffix(".wav")
    subprocess.run([exe, "-v", voice[:2], "-s", str(int(165 * rate)), "-w", str(wav), text], check=True, capture_output=True, timeout=120)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-codec:a", "libmp3lame", "-q:a", "4", str(audio_path)], check=True, timeout=120)
    wav.unlink(missing_ok=True)
    duration = audio_duration(audio_path)
    return duration, estimate_words(text, duration)


def _silent(text, voice, rate, audio_path):
    words = len(text.split())
    duration = max(1.5, words / (2.6 * rate))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", f"{duration:.3f}",
                    "-codec:a", "libmp3lame", "-q:a", "9", str(audio_path)], check=True, timeout=120)
    return audio_duration(audio_path), estimate_words(text, duration)


PROVIDERS = {"edge": _edge, "espeak": _espeak, "silent": _silent}


def provider_order(allow_silent: bool) -> list[str]:
    chosen = os.getenv("TTS_PROVIDER", "auto").strip().lower()
    order = [chosen] if chosen in PROVIDERS else ["edge", "espeak"]
    if allow_silent and "silent" not in order:
        order.append("silent")
    return order


def synthesize(text: str, voice: str, rate: float = 1.0, allow_silent: bool = False) -> dict[str, Any]:
    """Return {path, url, duration, words, provider}. Results are cached on disk."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        raise VoiceUnavailable("Nothing to say.")
    config.ensure_dirs()
    errors: list[str] = []
    for name in provider_order(allow_silent):
        key = _key(text, voice, rate, name)
        audio_path = config.AUDIO_DIR / f"{key}.mp3"
        meta_path = config.AUDIO_DIR / f"{key}.json"
        with _lock_for(key):  # the same sentence may be requested by two threads at once
            if audio_path.exists() and meta_path.exists():
                meta = json.loads(meta_path.read_text())
                return {**meta, "path": str(audio_path), "url": f"/api/audio/{key}.mp3", "provider": name}
            try:
                duration, words = PROVIDERS[name](text, voice, rate, audio_path)
            except VoiceUnavailable as exc:
                errors.append(str(exc))
                audio_path.unlink(missing_ok=True)
                continue
            except Exception as exc:
                errors.append(f"{name}: {type(exc).__name__}")
                audio_path.unlink(missing_ok=True)
                continue
            meta = {"duration": round(duration, 3), "words": words}
            meta_path.write_text(json.dumps(meta))
        return {**meta, "path": str(audio_path), "url": f"/api/audio/{key}.mp3", "provider": name}
    raise VoiceUnavailable(errors[0] if errors else "No voice engine is available.")


def synthesize_many(texts: list[str], voice: str, rate: float = 1.0, allow_silent: bool = False, workers: int = 3) -> list[dict[str, Any]]:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda t: synthesize(t, voice, rate, allow_silent), texts))
