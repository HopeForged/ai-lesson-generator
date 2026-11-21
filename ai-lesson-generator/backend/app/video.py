"""Lecture video export.

1. build_timeline: voice (audio + word timings) for every beat -> one timeline JSON + one audio track.
2. record: headless Chromium plays the timeline on the /#/render page in real time and records it.
3. ffmpeg trims the recording to the exact start, adds the audio and encodes an MP4. A .srt caption file is written too.
Everything is free: edge-tts, Playwright and ffmpeg.
"""
import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from app import config
from app.beats import build_beats, split_sentences
from app.tts import VoiceUnavailable, audio_duration, synthesize_many

TITLE_SECONDS = 4.0
SECTION_SECONDS = 2.2
BEAT_GAP = 0.45
OUTRO_SECONDS = 4.0


class VideoError(Exception):
    pass


def video_dir(video_id: str) -> Path:
    path = config.VIDEO_DIR / video_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _silence(path: Path, seconds: float) -> Path:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", f"{seconds:.3f}", str(path)], check=True, timeout=120)
    return path


def _to_wav(src: str, dst: Path) -> Path:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-ar", "44100", "-ac", "2", str(dst)], check=True, timeout=300)
    return dst


def build_timeline(lesson: dict[str, Any], lecturer: str, voice: str, rate: float, workdir: Path,
                   progress: Callable[[float, str], None] | None = None, allow_silent: bool = True) -> dict[str, Any]:
    """Create timeline.json + audio.wav in workdir. Returns the timeline dict."""
    say = progress or (lambda p, m: None)
    sections = lesson.get("sections", [])
    plan = []  # (section index, beat index, beat dict)
    for si, section in enumerate(sections):
        for bi, beat in enumerate(build_beats(section)):
            plan.append((si, bi, beat))
    if not plan:
        raise VideoError("This lesson has no narration to turn into a video.")

    say(5, "Recording the lecturer's voice")
    clips = []
    # synthesize in small batches so the progress bar moves
    batch = 6
    for i in range(0, len(plan), batch):
        chunk = plan[i:i + batch]
        try:
            clips += synthesize_many([b["text"] for _, _, b in chunk], voice, rate, allow_silent=allow_silent)
        except VoiceUnavailable as exc:
            raise VideoError(str(exc)) from exc
        say(5 + 35 * min(1, (i + batch) / len(plan)), "Recording the lecturer's voice")
    has_voice = any(c["provider"] != "silent" for c in clips)

    say(42, "Building the timeline")
    segments: list[dict[str, Any]] = []
    audio_parts: list[Path] = []
    clock = 0.0

    def add_silence(seconds: float) -> None:
        audio_parts.append(_silence(workdir / f"sil_{len(audio_parts)}.wav", seconds))

    segments.append({"type": "title", "start": 0.0, "end": TITLE_SECONDS})
    add_silence(TITLE_SECONDS)
    clock = TITLE_SECONDS
    clip_iter = iter(clips)
    last_section = -1
    for si, bi, beat in plan:
        if si != last_section:
            segments.append({"type": "section", "section": si, "start": clock, "end": clock + SECTION_SECONDS})
            add_silence(SECTION_SECONDS)
            clock += SECTION_SECONDS
            last_section = si
        clip = next(clip_iter)
        wav = _to_wav(clip["path"], workdir / f"beat_{len(audio_parts)}.wav")
        duration = audio_duration(wav)  # the decoded length is what ends up in the video's audio track
        audio_parts.append(wav)
        add_silence(BEAT_GAP)
        segments.append({
            "type": "beat", "section": si, "beat": bi, "start": round(clock, 3), "end": round(clock + duration + BEAT_GAP, 3),
            "speech_end": round(clock + duration, 3), "text": beat["text"], "scene": beat["scene"],
            "avatar_action": beat.get("avatar_action", "explain"), "words": clip["words"],
        })
        clock += duration + BEAT_GAP
    segments.append({"type": "outro", "start": round(clock, 3), "end": round(clock + OUTRO_SECONDS, 3)})
    add_silence(OUTRO_SECONDS)
    clock += OUTRO_SECONDS

    say(48, "Mixing the audio track")
    listing = workdir / "audio_list.txt"
    listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in audio_parts))
    audio = workdir / "audio.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(audio)], check=True, timeout=600)
    for part in audio_parts:
        part.unlink(missing_ok=True)

    timeline = {
        "total": round(clock, 3), "width": 1280, "height": 720, "has_voice": has_voice,
        "lecturer": lecturer,
        "lesson": {"title": lesson.get("title"), "topic": lesson.get("topic"), "introduction": lesson.get("introduction"),
                   "sections": [{"heading": s.get("heading")} for s in sections]},
        "segments": segments,
    }
    (workdir / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False))
    (workdir / "captions.srt").write_text(make_srt(timeline), encoding="utf-8")
    return timeline


def _srt_time(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def make_srt(timeline: dict[str, Any]) -> str:
    cues, n = [], 1
    for seg in timeline["segments"]:
        if seg["type"] != "beat":
            continue
        text, words = seg["text"], seg["words"]
        sentences = split_sentences(text)
        offset = 0
        starts = []
        for sentence in sentences:
            at = text.find(sentence, offset)
            starts.append(at)
            offset = at + len(sentence)
        for i, sentence in enumerate(sentences):
            first = next((w for w in words if w["c"] >= starts[i]), None)
            nxt = next((w for w in words if i + 1 < len(starts) and w["c"] >= starts[i + 1]), None)
            t0 = seg["start"] + (first["s"] if first else 0)
            t1 = seg["start"] + (nxt["s"] if nxt else (seg["speech_end"] - seg["start"]))
            t1 = max(t1, t0 + 0.6)
            wrapped = re.sub(r"(.{1,42})(\s+|$)", r"\1\n", sentence).strip()
            cues.append(f"{n}\n{_srt_time(t0)} --> {_srt_time(t1)}\n{wrapped}\n")
            n += 1
    return "\n".join(cues)


def check_requirements() -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise VideoError("ffmpeg is not installed. Install it free from https://ffmpeg.org (or: winget install ffmpeg).")
    try:
        import playwright  # noqa: F401
    except ImportError as exc:
        raise VideoError("Video export needs Playwright. Run: pip install playwright  then  playwright install chromium") from exc


def record_and_encode(video_id: str, base_url: str, workdir: Path, timeline: dict[str, Any], out_path: Path,
                      progress: Callable[[float, str], None] | None = None) -> None:
    say = progress or (lambda p, m: None)
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    total = float(timeline["total"])
    raw_dir = workdir / "raw"
    shutil.rmtree(raw_dir, ignore_errors=True)
    raw_dir.mkdir()
    say(50, "Opening the recording studio")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        except PlaywrightError as exc:
            raise VideoError("Chromium is not installed for Playwright. Run: playwright install chromium") from exc
        context = browser.new_context(viewport={"width": 1280, "height": 720}, record_video_dir=str(raw_dir),
                                      record_video_size={"width": 1280, "height": 720}, device_scale_factor=1)
        created = time.time()
        page = context.new_page()
        try:
            page.goto(f"{base_url.rstrip('/')}/#/render/{video_id}", wait_until="load", timeout=60000)
            page.wait_for_function("window.__videoReady === true || !!window.__videoError", timeout=60000)
        except PlaywrightError as exc:
            context.close(); browser.close()
            raise VideoError(f"Could not open the video page at {base_url}. Is the frontend running (npm run dev)? ({type(exc).__name__})") from exc
        if page.evaluate("window.__videoError || ''"):
            err = page.evaluate("window.__videoError")
            context.close(); browser.close()
            raise VideoError(f"The video page failed to load: {err}")
        page.wait_for_timeout(600)  # let fonts and the first frame settle
        started_ms = page.evaluate("window.__startTimeline()")
        offset = started_ms / 1000 - created
        begun = time.time()
        while True:
            page.wait_for_timeout(1000)
            elapsed = time.time() - begun
            say(52 + 38 * min(1, elapsed / total), "Recording the lecture")
            if page.evaluate("window.__videoDone === true") or elapsed > total + 90:
                break
        page.wait_for_timeout(500)
        video_path = page.video.path()
        context.close()
        browser.close()

    say(92, "Encoding the MP4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{offset:.3f}", "-i", str(video_path), "-i", str(workdir / "audio.wav"),
           "-t", f"{total:.3f}", "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
           "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-shortest", str(out_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if result.returncode != 0 or not out_path.exists():
        raise VideoError(f"ffmpeg could not encode the video: {result.stderr[-300:]}")
    shutil.rmtree(raw_dir, ignore_errors=True)
