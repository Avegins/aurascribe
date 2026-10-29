"""OpenAI Audio Transcription Client.

Handles secure in-memory audio dispatch to OpenAI Whisper API with error mapping
and operational metrics logging.
"""

import io
import time
from typing import Optional, Tuple
from openai import (
    OpenAI,
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)
from aurascribe.schemas.transcript import TranscriptMetadata, ValidatedTranscript
from aurascribe.utils.config import Settings, get_settings
from aurascribe.utils.errors import TranscriptionError, ConfigurationError
from aurascribe.utils.logger import get_logger, log_operation

logger = get_logger("models.transcription_client")


class TranscriptionClient:
    """Wrapper client for OpenAI Whisper transcription API."""

    def __init__(self, settings: Optional[Settings] = None, client: Optional[OpenAI] = None) -> None:
        self.settings = settings or get_settings()
        if client:
            self.client = client
        else:
            api_key = self.settings.openai_api_key
            base_url = self.settings.transcription_base_url
            if not api_key and not base_url:
                raise ConfigurationError(
                    "OPENAI_API_KEY must be configured to initialize TranscriptionClient "
                    "(or configure AURASCRIBE_TRANSCRIPTION_BASE_URL for a self-hosted Whisper endpoint)."
                )
            client_kwargs = {
                "api_key": api_key or "local-proxy-not-required",
                "timeout": self.settings.request_timeout_seconds,
            }
            if base_url:
                client_kwargs["base_url"] = base_url
            self.client = OpenAI(**client_kwargs)

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str,
        media_type: str,
        language_hint: Optional[str] = None,
        prompt: Optional[str] = None,
        temperature: float = 0.0,
        request_id: Optional[str] = None,
    ) -> ValidatedTranscript:
        """Submits in-memory audio bytes to OpenAI transcription API.

        Args:
            audio_bytes: Raw binary content of recorded audio.
            filename: Validated filename with extension (e.g. 'recording.webm').
            media_type: MIME type of the audio stream.
            language_hint: Optional ISO language code (e.g. 'tl', 'en').
            request_id: Optional correlation tracking ID.

        Returns:
            ValidatedTranscript: Strongly validated transcript object with metadata.

        Raises:
            TranscriptionError: On network, upstream, or formatting failures.
        """
        if not audio_bytes:
            raise TranscriptionError("Cannot transcribe empty audio buffer.", status_code=400)

        log_operation(
            logger,
            stage="transcription",
            status="started",
            request_id=request_id,
            details={
                "model": self.settings.transcription_model,
                "size_bytes": len(audio_bytes),
                "media_type": media_type,
            },
        )

        start_time = time.perf_counter()
        # Create an in-memory tuple file representation: (filename, bytes, content_type)
        file_tuple = (filename, io.BytesIO(audio_bytes), media_type)

        try:
            kwargs = {
                "model": self.settings.transcription_model,
                "file": file_tuple,
                "response_format": "verbose_json",
                "temperature": temperature,
            }
            effective_prompt = prompt or getattr(self.settings, "transcription_prompt", None)
            if effective_prompt:
                kwargs["prompt"] = effective_prompt

            effective_language = language_hint or self.settings.default_language_hint
            if effective_language:
                kwargs["language"] = effective_language

            response = self.client.audio.transcriptions.create(**kwargs)
            duration_ms = (time.perf_counter() - start_time) * 1000

            # verbose_json returns text, language, duration
            transcript_text = getattr(response, "text", "") or ""
            detected_lang = getattr(response, "language", None) or language_hint
            duration_sec = getattr(response, "duration", None)

            metadata = TranscriptMetadata(
                model=self.settings.transcription_model,
                detected_language=detected_lang,
                duration_seconds=duration_sec,
            )

            result = ValidatedTranscript(
                text=transcript_text,
                metadata=metadata,
            )

            log_operation(
                logger,
                stage="transcription",
                status="success",
                request_id=request_id,
                duration_ms=duration_ms,
                details={
                    "model": self.settings.transcription_model,
                    "detected_language": detected_lang,
                },
            )
            return result

        except AuthenticationError as exc:
            log_operation(
                logger,
                stage="transcription",
                status="failed",
                request_id=request_id,
                error_category="upstream_auth_failure",
            )
            raise TranscriptionError(
                "Upstream transcription authentication failed.",
                status_code=502,
                details={"category": "auth_error"},
            ) from exc

        except RateLimitError as exc:
            log_operation(
                logger,
                stage="transcription",
                status="failed",
                request_id=request_id,
                error_category="rate_limit_exceeded",
            )
            raise TranscriptionError(
                "Transcription rate limit exceeded. Please retry after a brief delay.",
                status_code=429,
                details={"category": "rate_limit"},
            ) from exc

        except APITimeoutError as exc:
            log_operation(
                logger,
                stage="transcription",
                status="failed",
                request_id=request_id,
                error_category="timeout",
            )
            raise TranscriptionError(
                "Transcription request timed out.",
                status_code=504,
                details={"category": "timeout"},
            ) from exc

        except BadRequestError as exc:
            log_operation(
                logger,
                stage="transcription",
                status="failed",
                request_id=request_id,
                error_category="bad_request",
            )
            raise TranscriptionError(
                f"Transcription request was rejected: {exc.message}",
                status_code=400,
                details={"category": "bad_request"},
            ) from exc

        except (APIConnectionError, APIStatusError) as exc:
            error_msg = str(getattr(exc, "message", None) or exc)
            log_operation(
                logger,
                stage="transcription",
                status="failed",
                request_id=request_id,
                error_category="upstream_service_error",
                details={"error": error_msg},
            )
            raise TranscriptionError(
                f"Upstream transcription service encountered an error: {error_msg}",
                status_code=502,
                details={"category": "upstream_error", "message": error_msg},
            ) from exc

        except Exception as exc:
            log_operation(
                logger,
                stage="transcription",
                status="failed",
                request_id=request_id,
                error_category="unexpected_error",
            )
            raise TranscriptionError(
                "An unexpected error occurred during transcription.",
                status_code=500,
                details={"category": "unexpected_error"},
            ) from exc

