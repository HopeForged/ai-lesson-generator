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


class LessonSection(BaseModel):
    heading: str
    narration: str = Field(min_length=20)
    slide: LessonSlide


class Lesson(BaseModel):
    title: str
    topic: str
    introduction: str
    sections: list[LessonSection] = Field(min_length=4, max_length=8)
    sources: list[LessonSource] = Field(min_length=1)
