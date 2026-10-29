"""Domain-specific exceptions for AuraScribe.

Provides a clean hierarchy of structured exceptions mapped to HTTP status codes
and error categories without leaking internal sensitive information.
"""

from typing import Any, Dict, Optional


class AuraScribeError(Exception):
    """Base exception for all AuraScribe domain errors."""

    def __init__(
        self,
        message: str,
        category: str = "internal_error",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.category = category
        self.status_code = status_code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """User-safe dictionary representation of the error."""
        return {
            "error": {
                "category": self.category,
                "message": self.message,
                "details": self.details,
            }
        }


class ConfigurationError(AuraScribeError):
    """Raised when required configuration or environment variables are missing or invalid."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            message=message,
            category="configuration_error",
            status_code=500,
            details=details,
        )


class AudioValidationError(AuraScribeError):
    """Raised when uploaded audio fails format, size, or integrity checks."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            message=message,
            category="audio_validation_error",
            status_code=400,
            details=details,
        )


class TranscriptValidationError(AuraScribeError):
    """Raised when generated transcript is empty or unusable."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            message=message,
            category="transcript_validation_error",
            status_code=422,
            details=details,
        )


class TranscriptionError(AuraScribeError):
    """Raised when audio transcription service fails or returns an upstream error."""

    def __init__(
        self,
        message: str,
        status_code: int = 502,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            category="transcription_error",
            status_code=status_code,
            details=details,
        )


class ClinicalExtractionError(AuraScribeError):
    """Raised when clinical extraction agent fails or schema validation fails."""

    def __init__(
        self,
        message: str,
        status_code: int = 502,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            category="clinical_extraction_error",
            status_code=status_code,
            details=details,
        )


class GuardrailViolationError(AuraScribeError):
    """Raised when clinical or schema guardrails are violated."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            message=message,
            category="guardrail_violation_error",
            status_code=422,
            details=details,
        )

