"""Transcription Tool coordinator.

Validates uploaded audio payloads and manages transcription execution via the
transcription client.
"""

from typing import Optional
from aurascribe.models.transcription_client import TranscriptionClient
from aurascribe.schemas.audio import AudioValidationInput, AudioValidationResult
from aurascribe.schemas.transcript import ValidatedTranscript
from aurascribe.utils.config import Settings, get_settings
from aurascribe.utils.errors import AudioValidationError, TranscriptValidationError
from aurascribe.utils.logger import get_logger, log_operation

logger = get_logger("tools.transcription_tool")


class TranscriptionTool:
    """Coordinates audio validation and transcription execution."""

    def __init__(
        self,
        client: Optional[TranscriptionClient] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or TranscriptionClient(settings=self.settings)

    def validate_audio(
        self,
        audio_bytes: bytes,
        filename: str,
        media_type: str,
        language_hint: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> AudioValidationResult:
        """Validates incoming audio format, byte length, and size constraints.

        Raises:
            AudioValidationError: If format, MIME, or length constraints are violated.
        """
        size_bytes = len(audio_bytes)
        log_operation(
            logger,
            stage="audio_validation",
            status="started",
            request_id=request_id,
            message="Validating incoming audio payload format and constraints",
            details={"filename": filename, "media_type": media_type, "size_bytes": size_bytes},
        )

        # Check upload size limit
        if size_bytes > self.settings.max_audio_size_bytes:
            log_operation(
                logger,
                stage="audio_validation",
                status="failed",
                request_id=request_id,
                error_category="file_too_large",
                message=f"Audio payload ({size_bytes} bytes) exceeds limit ({self.settings.max_audio_size_bytes})",
            )
            raise AudioValidationError(
                f"Audio payload ({size_bytes} bytes) exceeds maximum configured limit of "
                f"{self.settings.max_audio_size_bytes} bytes."
            )

        try:
            val_input = AudioValidationInput(
                filename=filename,
                media_type=media_type,
                size_bytes=size_bytes,
                language_hint=language_hint,
            )
            result = AudioValidationResult(
                filename=val_input.filename,
                media_type=val_input.media_type,
                size_bytes=val_input.size_bytes,
                language_hint=val_input.language_hint,
                is_valid=True,
            )
            log_operation(
                logger,
                stage="audio_validation",
                status="success",
                request_id=request_id,
                message="Audio validation checks passed",
            )
            return result
        except Exception as exc:
            log_operation(
                logger,
                stage="audio_validation",
                status="failed",
                request_id=request_id,
                error_category="validation_failure",
                message=f"Audio validation failed: {str(exc)}",
            )
            raise AudioValidationError(f"Audio validation failed: {str(exc)}") from exc

    def execute(
        self,
        audio_bytes: bytes,
        filename: str,
        media_type: str,
        language_hint: Optional[str] = None,
        prompt: Optional[str] = None,
        temperature: float = 0.0,
        request_id: Optional[str] = None,
    ) -> ValidatedTranscript:
        """Validates audio and triggers transcription, returning a ValidatedTranscript.

        Raises:
            AudioValidationError: On invalid audio input.
            TranscriptionError: On upstream transcription API failures.
            TranscriptValidationError: If generated transcript is empty or unusable.
        """
        validated_audio = self.validate_audio(
            audio_bytes=audio_bytes,
            filename=filename,
            media_type=media_type,
            language_hint=language_hint,
            request_id=request_id,
        )

        log_operation(
            logger,
            stage="transcription",
            status="started",
            request_id=request_id,
            message="Dispatching audio payload to transcription client",
            details={"filename": validated_audio.filename, "media_type": validated_audio.media_type},
        )

        transcript = self.client.transcribe(
            audio_bytes=audio_bytes,
            filename=validated_audio.filename,
            media_type=validated_audio.media_type,
            language_hint=validated_audio.language_hint,
            prompt=prompt,
            temperature=temperature,
            request_id=request_id,
        )

        # Ensure transcript is not empty or gibberish
        if not transcript.text or not transcript.text.strip():
            log_operation(
                logger,
                stage="transcript_validation",
                status="failed",
                request_id=request_id,
                error_category="empty_transcript",
                message="Transcription service produced empty or blank transcript",
            )
            raise TranscriptValidationError("Transcription service produced an empty transcript.")

        log_operation(
            logger,
            stage="transcript_validation",
            status="success",
            request_id=request_id,
            message="Transcription text validated successfully",
            details={"char_count": len(transcript.text)},
        )
        return transcript
