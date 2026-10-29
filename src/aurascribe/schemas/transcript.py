"""Transcript validation and metadata schemas."""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class TranscriptMetadata(BaseModel):
    """Metadata describing the transcription process."""

    model: str = Field(..., description="Transcription model identifier, e.g. whisper-1")
    detected_language: Optional[str] = Field(
        default=None, description="Language code detected by transcription engine"
    )
    duration_seconds: Optional[float] = Field(
        default=None, description="Audio duration in seconds if provided by engine"
    )


class ValidatedTranscript(BaseModel):
    """Clean, validated transcript ready for clinical extraction."""

    text: str = Field(..., description="Verbatim transcription text")
    metadata: TranscriptMetadata = Field(..., description="Associated transcription metadata")

    @field_validator("text")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Transcript text cannot be empty or solely whitespace.")
        if len(clean) < 3:
            raise ValueError("Transcript is too short to contain clinical content.")
        return clean

