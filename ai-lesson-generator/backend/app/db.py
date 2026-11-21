"""A tiny SQLite library: saved lessons, quizzes and rendered videos. No server needed."""
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from typing import Any

from app import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS lessons (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, topic TEXT NOT NULL, language TEXT NOT NULL DEFAULT 'English',
  sections INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS quizzes (lesson_id TEXT PRIMARY KEY, data TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS videos (
  id TEXT PRIMARY KEY, lesson_id TEXT NOT NULL, lecturer TEXT NOT NULL, status TEXT NOT NULL,
  created_at REAL NOT NULL, duration REAL, has_voice INTEGER NOT NULL DEFAULT 1);
"""


@contextmanager
def connect():
    config.ensure_dirs()
    conn = sqlite3.connect(config.DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def save_lesson(lesson: dict[str, Any], lesson_id: str | None = None) -> str:
    lesson_id = lesson_id or uuid.uuid4().hex[:10]
    with connect() as db:
        db.execute(
            "INSERT OR REPLACE INTO lessons (id,title,topic,language,sections,created_at,data) VALUES (?,?,?,?,?,?,?)",
            (lesson_id, lesson.get("title") or lesson.get("topic") or "Untitled", lesson.get("topic") or "",
             lesson.get("language") or "English", len(lesson.get("sections") or []), time.time(),
             json.dumps(lesson, ensure_ascii=False)),
        )
    return lesson_id


def list_lessons() -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute("SELECT id,title,topic,language,sections,created_at FROM lessons ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


def get_lesson(lesson_id: str) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute("SELECT data FROM lessons WHERE id=?", (lesson_id,)).fetchone()
    return json.loads(row["data"]) if row else None


def delete_lesson(lesson_id: str) -> bool:
    with connect() as db:
        cur = db.execute("DELETE FROM lessons WHERE id=?", (lesson_id,))
        db.execute("DELETE FROM quizzes WHERE lesson_id=?", (lesson_id,))
        db.execute("DELETE FROM videos WHERE lesson_id=?", (lesson_id,))
    return cur.rowcount > 0


def save_quiz(lesson_id: str, quiz: dict[str, Any]) -> None:
    with connect() as db:
        db.execute("INSERT OR REPLACE INTO quizzes (lesson_id,data,created_at) VALUES (?,?,?)",
                   (lesson_id, json.dumps(quiz, ensure_ascii=False), time.time()))


def get_quiz(lesson_id: str) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute("SELECT data FROM quizzes WHERE lesson_id=?", (lesson_id,)).fetchone()
    return json.loads(row["data"]) if row else None


def save_video(video_id: str, lesson_id: str, lecturer: str, status: str, duration: float | None = None, has_voice: bool = True) -> None:
    with connect() as db:
        db.execute("INSERT OR REPLACE INTO videos (id,lesson_id,lecturer,status,created_at,duration,has_voice) VALUES (?,?,?,?,?,?,?)",
                   (video_id, lesson_id, lecturer, status, time.time(), duration, 1 if has_voice else 0))


def list_videos(lesson_id: str) -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute("SELECT * FROM videos WHERE lesson_id=? AND status='done' ORDER BY created_at DESC", (lesson_id,)).fetchall()
    return [dict(row) for row in rows]
