"""Shared settings, folders, languages and lecturer voices."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("LESSONFORGE_DATA", BASE_DIR / "data"))
AUDIO_DIR = DATA_DIR / "audio"
VIDEO_DIR = DATA_DIR / "videos"
DB_PATH = DATA_DIR / "lessonforge.db"


def ensure_dirs() -> None:
    for folder in (DATA_DIR, AUDIO_DIR, VIDEO_DIR):
        folder.mkdir(parents=True, exist_ok=True)


# language name -> (male voice, female voice) from the free Microsoft Edge neural voices
LANGUAGES: dict[str, tuple[str, str]] = {
    "English": ("en-US-GuyNeural", "en-US-JennyNeural"),
    "English (UK)": ("en-GB-RyanNeural", "en-GB-SoniaNeural"),
    "English (South Africa)": ("en-ZA-LukeNeural", "en-ZA-LeahNeural"),
    "French": ("fr-FR-HenriNeural", "fr-FR-DeniseNeural"),
    "Spanish": ("es-ES-AlvaroNeural", "es-ES-ElviraNeural"),
    "Portuguese": ("pt-BR-AntonioNeural", "pt-BR-FranciscaNeural"),
    "German": ("de-DE-ConradNeural", "de-DE-KatjaNeural"),
    "Italian": ("it-IT-DiegoNeural", "it-IT-ElsaNeural"),
    "Swahili": ("sw-KE-RafikiNeural", "sw-KE-ZuriNeural"),
    "Zulu": ("zu-ZA-ThembaNeural", "zu-ZA-ThandoNeural"),
    "Afrikaans": ("af-ZA-WillemNeural", "af-ZA-AdriNeural"),
    "Arabic": ("ar-SA-HamedNeural", "ar-SA-ZariyahNeural"),
    "Hindi": ("hi-IN-MadhurNeural", "hi-IN-SwaraNeural"),
    "Chinese": ("zh-CN-YunxiNeural", "zh-CN-XiaoxiaoNeural"),
}

# The lecturers the student can choose between. "voice" picks the male/female voice of the language.
LECTURERS: dict[str, dict[str, str]] = {
    "mensah": {"name": "Dr. Mensah", "voice": "male"},
    "naledi": {"name": "Prof. Naledi", "voice": "female"},
    "walker": {"name": "Mr. Walker", "voice": "male"},
}


def voice_for(language: str, lecturer: str) -> str:
    male, female = LANGUAGES.get(language, LANGUAGES["English"])
    return female if LECTURERS.get(lecturer, LECTURERS["mensah"])["voice"] == "female" else male
