"""Pydantic API request and response data contracts."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from aurascribe.schemas.soap import SOAPNote
from aurascribe.schemas.transcript import ValidatedTranscript


class HealthResponse(BaseModel):
    """Application health endpoint response."""

    status: str = Field(default="ok", description="Service health status")
    environment: str = Field(..., description="Active runtime environment")
    version: str = Field(..., description="Application version")


class ErrorDetails(BaseModel):
    """Structured error descriptor."""

    category: str = Field(..., description="Machine-readable error category")
    message: str = Field(..., description="Safe human-readable error explanation")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional non-sensitive error context")


class ErrorResponse(BaseModel):
    """Standardized error response payload."""

    error: ErrorDetails


class ProcessResponse(BaseModel):
    """Successful audio processing response payload."""

    status: str = Field(default="success", description="Outcome indicator")
    request_id: str = Field(..., description="Unique request tracing identifier")
    transcript: ValidatedTranscript = Field(..., description="Transcribed audio text with metadata")
    soap_note: SOAPNote = Field(..., description="Pydantic-validated SOAP note")
    review_required: bool = Field(default=True, description="Mandatory physician review requirement")
    validation_warnings: List[str] = Field(default_factory=list, description="Clinical safety warnings")
    duration_ms: Optional[float] = Field(default=None, description="Processing duration in ms")

