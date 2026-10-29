"""Audio validation contracts and schema definitions."""

from typing import FrozenSet, Optional
from pydantic import BaseModel, Field, field_validator
from aurascribe.utils.errors import AudioValidationError

SUPPORTED_AUDIO_MIME_TYPES: FrozenSet[str] = frozenset(
    {
        "audio/webm",
        "audio/webm;codecs=opus",
        "video/webm",  # MediaRecorder in Chrome often emits video/webm container for audio
        "audio/wav",
        "audio/x-wav",
        "audio/wave",
        "audio/mp3",
        "audio/mpeg",
        "audio/mp4",
        "audio/m4a",
        "audio/x-m4a",
        "audio/ogg",
        "audio/ogg;codecs=opus",
        "audio/aac",
        "audio/flac",
    }
)

SUPPORTED_AUDIO_EXTENSIONS: FrozenSet[str] = frozenset(
    {"webm", "wav", "mp3", "mpeg", "mp4", "m4a", "ogg", "aac", "flac"}
)

MIN_AUDIO_BYTES: int = 64  # Minimal header byte threshold


class AudioValidationInput(BaseModel):
    """Input payload describing audio stream to be validated."""

    filename: str = Field(..., description="Original filename of the audio upload")
    media_type: str = Field(..., description="MIME content type of the audio stream")
    size_bytes: int = Field(..., description="Length of the audio stream in bytes")
    language_hint: Optional[str] = Field(
        default=None, description="Optional ISO language hint (e.g. 'tl', 'en')"
    )

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Filename cannot be empty")
        parts = clean.split(".")
        if len(parts) < 2 or parts[-1].lower() not in SUPPORTED_AUDIO_EXTENSIONS:
            raise ValueError(
                f"Unsupported file extension: {parts[-1] if len(parts) > 1 else 'none'}. "
                f"Supported: {', '.join(sorted(SUPPORTED_AUDIO_EXTENSIONS))}"
            )
        return clean

    @field_validator("media_type")
    @classmethod
    def validate_mime(cls, v: str) -> str:
        clean = v.strip().lower()
        # Normalise mime type by stripping parameters for lookup if needed
        base_mime = clean.split(";")[0].strip()
        if clean not in SUPPORTED_AUDIO_MIME_TYPES and base_mime not in SUPPORTED_AUDIO_MIME_TYPES:
            raise ValueError(
                f"Unsupported audio MIME type: {clean}. "
                f"Supported: {', '.join(sorted(SUPPORTED_AUDIO_MIME_TYPES))}"
            )
        return clean

    @field_validator("size_bytes")
    @classmethod
    def validate_size(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Audio payload cannot be empty (0 bytes)")
        if v < MIN_AUDIO_BYTES:
            raise ValueError(f"Audio payload is too small ({v} bytes). Minimum required is {MIN_AUDIO_BYTES} bytes.")
        return v


class AudioValidationResult(BaseModel):
    """Validated audio metadata approved for transcription."""

    filename: str
    media_type: str
    size_bytes: int
    language_hint: Optional[str] = None
    is_valid: bool = True

