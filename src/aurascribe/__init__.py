"""AuraScribe - AI-powered audio transcription and structured clinical documentation."""

from aurascribe.pipeline import (
    preprocess_audio,
    transcribe_audio,
    clean_transcript,
    generate_soap_note,
    BICOLANO_TAGLISH_PROMPT,
)

__version__ = "0.1.0"
__all__ = [
    "preprocess_audio",
    "transcribe_audio",
    "clean_transcript",
    "generate_soap_note",
    "BICOLANO_TAGLISH_PROMPT",
]


