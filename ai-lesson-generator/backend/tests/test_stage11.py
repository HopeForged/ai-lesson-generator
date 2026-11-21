"""Tests for the library, voice timings, quizzes, beats, captions and the video timeline (no network needed)."""
import json
import random
import shutil
import sys
import types

import pytest

from app import beats, config, db, jobs, quiz, sources, tts, video
from tests.test_models import beat, beat_lesson_dict  # reuse the sample lesson helpers


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "AUDIO_DIR", tmp_path / "audio")
    monkeypatch.setattr(config, "VIDEO_DIR", tmp_path / "videos")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setenv("TTS_PROVIDER", "auto")


def sample_lesson():
    from app.models import Lesson
    from app.services import ensure_visual_moments, normalize_lesson_payload

    return ensure_visual_moments(Lesson.model_validate(normalize_lesson_payload(beat_lesson_dict()))).model_dump(mode="json")


# ---- library
def test_library_roundtrip():
    lesson = sample_lesson()
    lesson_id = db.save_lesson(lesson)
    assert db.get_lesson(lesson_id)["title"] == lesson["title"]
    assert db.list_lessons()[0]["id"] == lesson_id and db.list_lessons()[0]["sections"] == 4
    db.save_quiz(lesson_id, {"sections": []})
    assert db.get_quiz(lesson_id) == {"sections": []}
    assert db.delete_lesson(lesson_id) is True
    assert db.get_lesson(lesson_id) is None and db.get_quiz(lesson_id) is None
    assert db.delete_lesson(lesson_id) is False


# ---- voice
def test_estimate_words_cover_text_in_order():
    words = tts.estimate_words("Hello there. This is a test.", 4.0)
    assert [w["c"] for w in words] == [0, 6, 13, 18, 21, 23]
    assert all(a["e"] <= b["s"] + 1e-6 for a, b in zip(words, words[1:])) and words[-1]["e"] <= 4.0


def test_map_boundaries_finds_characters():
    text = "Look at the Leaf, then the leaf again."
    out = tts.map_boundaries(text, [{"text": "Look", "start": 0.0, "dur": 0.3}, {"text": "the", "start": 0.7, "dur": 0.2},
                                     {"text": "Leaf,", "start": 0.9, "dur": 0.3}, {"text": "leaf", "start": 1.8, "dur": 0.3}])
    assert [w["c"] for w in out] == [0, 8, 12, 27]


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg needed")
def test_silent_provider_and_cache(monkeypatch):
    monkeypatch.setenv("TTS_PROVIDER", "silent")
    a = tts.synthesize("This is a short test of the silent voice engine.", "en-US-GuyNeural", allow_silent=True)
    assert a["provider"] == "silent" and a["duration"] > 1.5 and len(a["words"]) == 10
    b = tts.synthesize("This is a short test of the silent voice engine.", "en-US-GuyNeural", allow_silent=True)
    assert a["url"] == b["url"]


def test_voice_unavailable_without_engines(monkeypatch):
    monkeypatch.setenv("TTS_PROVIDER", "edge")
    monkeypatch.setitem(sys.modules, "edge_tts", None)  # import fails
    with pytest.raises(tts.VoiceUnavailable):
        tts.synthesize("Hello world, this is a test.", "en-US-GuyNeural")


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg needed")
def test_edge_provider_with_fake_engine(monkeypatch, tmp_path):
    import subprocess

    tone = tmp_path / "tone.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", str(tone)], check=True)

    class FakeCommunicate:
        def __init__(self, text, voice, boundary=None, rate="+0%"):
            self.text = text

        async def stream(self):
            yield {"type": "audio", "data": tone.read_bytes()}
            for i, w in enumerate(self.text.split()):
                yield {"type": "WordBoundary", "offset": int(i * 3e6), "duration": int(2.5e6), "text": w}

    fake = types.ModuleType("edge_tts")
    fake.Communicate = FakeCommunicate
    monkeypatch.setitem(sys.modules, "edge_tts", fake)
    monkeypatch.setenv("TTS_PROVIDER", "edge")
    clip = tts.synthesize("One two three four five.", "en-US-GuyNeural")
    assert clip["provider"] == "edge" and [w["c"] for w in clip["words"]] == [0, 4, 8, 14, 19]
    assert clip["words"][1]["s"] == pytest.approx(0.3)


def test_voice_for_language_and_lecturer():
    assert config.voice_for("English", "mensah") == "en-US-GuyNeural"
    assert config.voice_for("English", "naledi") == "en-US-JennyNeural"
    assert config.voice_for("Zulu", "naledi") == "zu-ZA-ThandoNeural"
    assert config.voice_for("Klingon", "nobody") == "en-US-GuyNeural"


# ---- quiz
def make_q(n, answer=0):
    return {"question": f"Question number {n}?", "options": ["right", "w1", "w2", "w3"], "answer_index": answer, "explanation": "Because."}


def test_clean_quiz_keeps_correct_answer_after_shuffle_and_drops_bad_items():
    payload = {
        "sections": [{"section_index": 0, "questions": [make_q(1), make_q(2), {"question": "x"}]},
                     {"section_index": 9, "questions": [make_q(3)]}],
        "final": [make_q(4), {"question": "Bad?", "options": ["a", "b"], "answer_index": 5}],
        "flashcards": [{"front": "Term", "back": "Meaning"}, {"front": ""}],
    }
    q = quiz.clean_quiz(payload, section_count=4, seed="t")
    assert len(q.sections) == 1 and len(q.sections[0].questions) == 2
    for question in q.sections[0].questions + q.final:
        assert question.options[question.answer_index] == "right"
    assert len(q.final) == 1 and len(q.flashcards) == 1
    positions = {quiz.clean_quiz({"sections": [{"section_index": 0, "questions": [make_q(i)]}]}, 1, seed=str(i)).sections[0].questions[0].answer_index for i in range(20)}
    assert len(positions) > 1  # not always the same slot


def test_clean_quiz_requires_something_usable():
    from app.services import GenerationError

    with pytest.raises(GenerationError):
        quiz.clean_quiz({"sections": []}, 4)


# ---- beats / captions / timeline
def test_python_beats_match_the_narration():
    lesson = sample_lesson()
    for section in lesson["sections"]:
        result = beats.build_beats(section)
        assert len(result) == 3 and result[0]["start"] == 0 and result[-1]["end"] == len(section["narration"])
        assert " ".join(b["text"] for b in result).replace("  ", " ") == section["narration"]


def test_beats_fall_back_for_old_lessons():
    section = {"heading": "H", "narration": "One sentence here. Another one follows now. A third one ends it. And a fourth.",
               "slide": {"title": "t", "bullet_points": ["Alpha", "Beta", "Gamma"]}, "visual_moments": []}
    result = beats.build_beats(section)
    assert len(result) >= 2 and all(b["scene"]["items"] for b in result)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg needed")
def test_video_timeline_and_srt(monkeypatch, tmp_path):
    monkeypatch.setenv("TTS_PROVIDER", "silent")
    lesson = sample_lesson()
    workdir = video.video_dir("t1")
    seen = []
    timeline = video.build_timeline(lesson, "mensah", "en-US-GuyNeural", 1.0, workdir, lambda p, m: seen.append(p))
    kinds = [s["type"] for s in timeline["segments"]]
    assert kinds[0] == "title" and kinds[-1] == "outro" and kinds.count("section") == 4 and kinds.count("beat") == 12
    ends = [s["end"] for s in timeline["segments"]]
    assert all(a["end"] == pytest.approx(b["start"], abs=0.01) for a, b in zip(timeline["segments"], timeline["segments"][1:]))
    assert (workdir / "audio.wav").exists() and (workdir / "timeline.json").exists()
    assert tts.audio_duration(workdir / "audio.wav") == pytest.approx(timeline["total"], abs=0.5)
    srt = (workdir / "captions.srt").read_text()
    assert srt.startswith("1\n00:00:") and "-->" in srt and srt.count("-->") >= 12
    assert timeline["has_voice"] is False and seen and seen[-1] <= 99


# ---- uploads, jobs, qa
def test_extract_text_rules():
    assert "alpha" in sources.extract_text("n.txt", ("alpha beta gamma " * 20).encode())
    with pytest.raises(ValueError):
        sources.extract_text("x.exe", b"abc")
    with pytest.raises(ValueError):
        sources.extract_text("tiny.txt", b"short")


def test_pdf_extraction():
    pypdf = pytest.importorskip("pypdf")
    import io

    writer = pypdf.PdfWriter()
    writer.add_blank_page(200, 200)
    buf = io.BytesIO()
    writer.write(buf)
    with pytest.raises(ValueError):  # a blank page has no readable text
        sources.extract_text("blank.pdf", buf.getvalue())


def test_job_runs_and_reports():
    import time

    job = jobs.start_job("t", lambda j: (j.update(50, "half"), "result")[1])
    for _ in range(50):
        if job.status in ("done", "error"):
            break
        time.sleep(0.05)
    assert job.status == "done" and job.result == "result" and job.public()["progress"] == 100
    bad = jobs.start_job("t", lambda j: 1 / 0)
    time.sleep(0.3)
    assert bad.status == "error" and "ZeroDivisionError" in bad.error


def test_ask_lecturer_returns_a_playable_beat(monkeypatch):
    from app import qa

    monkeypatch.setattr(qa, "_ai_json_response", lambda prompt, temperature=0.2: {
        "say": "Great question! Look at the board. Sunlight reaches the Leaf and the Leaf makes Glucose. Does that make sense?",
        "avatar_action": "dance", "scene": {"scene_type": "process", "title": "Answer", "items": ["Sunlight", "Leaf", "Glucose"]}})
    answer = qa.ask_lecturer(sample_lesson(), 1, "How does the leaf make food?")
    assert answer["avatar_action"] == "point_left" and answer["scene"]["items"][0] == "Sunlight" and "Look at the board" in answer["say"]


def test_language_and_level_reach_the_prompt(monkeypatch):
    import app.services as services

    captured = {}
    monkeypatch.setattr(services, "_ai_json_response", lambda prompt, temperature=0.2: captured.setdefault("p", prompt) and beat_lesson_dict())
    lesson = services.generate_lesson("Photosynthesis", None, [], language="Zulu", level="exam", material="Chlorophyll is green. " * 5)
    assert "in Zulu" in captured["p"] and "Exam preparation" in captured["p"] and "MATERIAL START" in captured["p"]
    assert lesson.language == "Zulu" and lesson.level == "exam" and lesson.sources[0].title == "Example source"
