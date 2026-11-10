from pydantic import BaseModel, Field, HttpUrl, field_validator


class LessonRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=160)
    script: str | None = Field(default=None, max_length=12000)

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


class VisualScene(BaseModel):
    """AI-planned instructions that the frontend turns into an animated scene."""

    scene_type: str = Field(default="generic", max_length=30)
    title: str = "Key idea"
    description: str = "A visual explanation of this lesson section."
    items: list[str] = Field(default_factory=lambda: ["Main idea", "Supporting idea"], min_length=1, max_length=5)


class VisualMoment(BaseModel):
    """A visual scene linked to an exact passage in the spoken narration."""

    cue_text: str = Field(min_length=5, max_length=280)
    scene: VisualScene


class LessonSection(BaseModel):
    heading: str
    narration: str = Field(min_length=20)
    slide: LessonSlide
    # Defaults keep older saved lesson JSON files compatible.
    visual_scene: VisualScene = Field(default_factory=VisualScene)
    # New lessons contain several scene changes within each section.
    visual_moments: list[VisualMoment] = Field(default_factory=list, max_length=5)


class Lesson(BaseModel):
    title: str
    topic: str
    introduction: str
    sections: list[LessonSection] = Field(min_length=4, max_length=8)
    sources: list[LessonSource] = Field(min_length=1)
