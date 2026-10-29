"""Processing state and pipeline lifecycle representation."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from aurascribe.schemas.transcript import ValidatedTranscript
from aurascribe.schemas.soap import SOAPNote


class PipelineStage(str, Enum):
    """Lifecycle stages of the clinical processing pipeline."""

    IDLE = "idle"
    AUDIO_VALIDATION = "audio_validation"
    TRANSCRIPTION = "transcription"
    TRANSCRIPT_VALIDATION = "transcript_validation"
    CLINICAL_EXTRACTION = "clinical_extraction"
    GUARDRAIL_EVALUATION = "guardrail_evaluation"
    COMPLETED = "completed"
    FAILED = "failed"


class ExecutionState(BaseModel):
    """Runtime execution state tracked during audio-to-SOAP processing."""

    request_id: str = Field(..., description="Unique request tracing correlation ID")
    stage: PipelineStage = Field(default=PipelineStage.IDLE, description="Current processing stage")
    transcript: Optional[ValidatedTranscript] = Field(default=None, description="Produced transcript")
    soap_note: Optional[SOAPNote] = Field(default=None, description="Extracted clinical SOAP note")
    is_success: bool = Field(default=False, description="True if workflow completed without errors")
    error_message: Optional[str] = Field(default=None, description="Error message if pipeline failed")
    duration_ms: Optional[float] = Field(default=None, description="Total pipeline execution duration in ms")

