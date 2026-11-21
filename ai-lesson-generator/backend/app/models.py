from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


LEVELS = ("beginner", "intermediate", "advanced", "exam")


class LessonRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=160)
    script: str | None = Field(default=None, max_length=12000)
    language: str = Field(default="English", max_length=40)
    level: Literal["beginner", "intermediate", "advanced", "exam"] = "intermediate"
    # Text extracted from an uploaded PDF / Word / text file. The lesson is taught from it.
    material: str | None = Field(default=None, max_length=60000)

    @field_validator("topic")
    @classmethod
    def topic_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Topic cannot be blank.")
        return value.strip()


class LessonSource(BaseModel):
    title: str
    url: HttpUrl


class LessonSlide(BaseModel):
    title: str
    bullet_points: list[str] = Field(min_length=2, max_length=6)


def _clean_list(value, limit: int, max_len: int):
    """Trim AI-provided lists instead of rejecting the whole lesson over a long label."""
    if not isinstance(value, list):
        return value
    return [str(item).strip()[:max_len] for item in value if str(item).strip()][:limit]


AVATAR_ACTIONS = ("explain", "point_left", "point_right", "emphasize", "welcome")


class VisualScene(BaseModel):
    """AI-planned instructions that the frontend turns into an animated diagram.

    scene_type picks the layout: process (ordered steps), cycle (loop), comparison,
    timeline, applications, network, structure/concept (one central idea with parts
    around it) or generic.
    """

    scene_type: str = Field(default="generic", max_length=30)
    title: str = "Key idea"
    description: str = "A visual explanation of this lesson section."
    items: list[str] = Field(default_factory=lambda: ["Main idea", "Supporting idea"], min_length=1, max_length=6)
    # Optional extras. Older saved lessons simply do not have them.
    details: list[str] = Field(default_factory=list, max_length=6)
    icons: list[str] = Field(default_factory=list, max_length=6)
    # Optional animated scene written by the "director" (see animation.py). None = plain diagram.
    animation: dict | None = None

    @field_validator("animation", mode="before")
    @classmethod
    def _clean_animation(cls, value):
        from app.animation import clean_animation  # never raises: unusable animations become None

        return clean_animation(value)

    @field_validator("items", mode="before")
    @classmethod
    def _trim_items(cls, value):
        return _clean_list(value, 6, 60)

    @field_validator("details", mode="before")
    @classmethod
    def _trim_details(cls, value):
        return _clean_list(value, 6, 110)

    @field_validator("icons", mode="before")
    @classmethod
    def _trim_icons(cls, value):
        return _clean_list(value, 6, 24)


class VisualMoment(BaseModel):
    """One teaching beat: what the lecturer says, the diagram on the board, and the gesture."""

    cue_text: str = Field(min_length=5, max_length=280)
    # The lecturer's spoken words for this beat (2-4 sentences). Optional for older lessons.
    say: str = Field(default="", max_length=1500)
    scene: VisualScene
    avatar_action: Literal["explain", "point_left", "point_right", "emphasize", "welcome"] = "explain"

    @field_validator("avatar_action", mode="before")
    @classmethod
    def _known_action(cls, value):
        value = str(value or "explain").strip().lower().replace(" ", "_")
        if value == "point":
            return "point_left"
        return value if value in AVATAR_ACTIONS else "explain"


class LessonSection(BaseModel):
    heading: str
    narration: str = Field(min_length=20)
    slide: LessonSlide
    # Defaults keep older saved lesson JSON files compatible.
    visual_scene: VisualScene = Field(default_factory=VisualScene)
    # New lessons contain several scene changes within each section.
    visual_moments: list[VisualMoment] = Field(default_factory=list, max_length=5)


class LessonQualityReview(BaseModel):
    score: int = Field(ge=0, le=100)
    passed: bool
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    attempts: int = Field(default=1, ge=1, le=2)


class Lesson(BaseModel):
    title: str
    topic: str
    introduction: str
    sections: list[LessonSection] = Field(min_length=4, max_length=8)
    sources: list[LessonSource] = Field(default_factory=list)
    # Optional so older saved lesson files remain compatible.
    quality_review: LessonQualityReview | None = None
    language: str = "English"
    level: str = "intermediate"
