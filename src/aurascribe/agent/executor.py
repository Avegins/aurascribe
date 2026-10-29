"""Pipeline executor and orchestrator for AuraScribe.

Coordinates the end-to-end 6-stage clinical documentation flow:
[Step 1/6] Audio Validation & Ingestion
[Step 2/6] Acoustic Speech Transcription
[Step 3/6] Transcript Cleaning & Speaker Attribution
[Step 4/6] Clinical Information Extraction
[Step 5/6] Clinical Guardrail Verification & Anti-Hallucination Audit
[Step 6/6] Packaging & Form Binding Ready for Physician Review
"""

import time
import uuid
from typing import Optional
from aurascribe.agent.clinical_agent import ClinicalExtractionAgent
from aurascribe.agent.state import ExecutionState, PipelineStage
from aurascribe.tools.transcription_tool import TranscriptionTool
from aurascribe.utils.config import Settings, get_settings
from aurascribe.utils.errors import (
    AudioValidationError,
    ClinicalExtractionError,
    TranscriptionError,
    TranscriptValidationError,
)
from aurascribe.utils.logger import PipelineStepLogger, get_logger, log_operation

logger = get_logger("agent.executor")


class ClinicalPipelineExecutor:
    """Orchestrates end-to-end audio ingestion, transcription, and clinical extraction."""

    def __init__(
        self,
        transcription_tool: Optional[TranscriptionTool] = None,
        extraction_agent: Optional[ClinicalExtractionAgent] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.transcription_tool = transcription_tool or TranscriptionTool(settings=self.settings)
        self.extraction_agent = extraction_agent or ClinicalExtractionAgent(settings=self.settings)

    def process(
        self,
        audio_bytes: bytes,
        filename: str,
        media_type: str,
        language_hint: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> ExecutionState:
        """Executes the complete transcription and clinical extraction workflow.

        Step Progression:
          [Step 1/6] Audio Validation & Ingestion
          [Step 2/6] Acoustic Speech Transcription
          [Step 3/6] LLM Transcript Cleaning & Speaker Attribution
          [Step 4/6] Clinical Information Extraction
          [Step 5/6] Clinical Safety Guardrail Verification
          [Step 6/6] Form Packaging & Physician Sign-off Ready

        Returns:
            ExecutionState: Containing the transcript, structured SOAP note, and lifecycle status.
        """
        req_id = request_id or str(uuid.uuid4())
        start_time = time.perf_counter()
        state = ExecutionState(request_id=req_id, stage=PipelineStage.IDLE)
        step_logger = PipelineStepLogger(logger, total_steps=6, request_id=req_id, stage_prefix="pipeline")

        current_step = 1
        try:
            # Step 1/6: Audio Validation & Ingestion
            current_step = 1
            step_logger.start_step(
                1,
                "Validating audio payload and format constraints",
                stage="audio_validation",
                details={"filename": filename, "media_type": media_type, "size_bytes": len(audio_bytes)},
            )
            t1_start = time.perf_counter()
            state.stage = PipelineStage.AUDIO_VALIDATION
            if hasattr(self.transcription_tool, "validate_audio"):
                self.transcription_tool.validate_audio(
                    audio_bytes=audio_bytes,
                    filename=filename,
                    media_type=media_type,
                    language_hint=language_hint,
                    request_id=req_id,
                )
            t1_dur = (time.perf_counter() - t1_start) * 1000
            step_logger.success_step(
                1,
                "Audio payload validated successfully",
                stage="audio_validation",
                duration_ms=t1_dur,
            )

            # Step 2/6: Acoustic Speech Transcription
            current_step = 2
            step_logger.start_step(
                2,
                "Transcribing acoustic audio via Speech-to-Text engine",
                stage="transcription",
                details={"language_hint": language_hint, "model": self.settings.transcription_model},
            )
            t2_start = time.perf_counter()
            state.stage = PipelineStage.TRANSCRIPTION
            transcript = self.transcription_tool.execute(
                audio_bytes=audio_bytes,
                filename=filename,
                media_type=media_type,
                language_hint=language_hint,
                request_id=req_id,
            )
            state.transcript = transcript
            t2_dur = (time.perf_counter() - t2_start) * 1000
            det_lang = getattr(getattr(transcript, "metadata", None), "detected_language", None) or language_hint or "auto"
            step_logger.success_step(
                2,
                "Acoustic transcription completed",
                stage="transcription",
                duration_ms=t2_dur,
                details={"char_count": len(transcript.text), "language": det_lang},
            )

            # Step 3/6: LLM Transcript Cleaning & Speaker Attribution
            current_step = 3
            step_logger.start_step(
                3,
                "Cleaning transcript and normalizing regional phrases",
                stage="transcript_cleaning",
            )
            t3_start = time.perf_counter()
            cleaned_text = transcript.text
            try:
                from aurascribe.pipeline.bicolano_pipeline import clean_transcript
                cleaned_candidate = clean_transcript(transcript.text, settings=self.settings)
                if cleaned_candidate and cleaned_candidate.strip():
                    cleaned_text = cleaned_candidate
            except Exception as clean_exc:
                step_logger.fallback_step(
                    3,
                    "Transcript cleaning encountered an error. Proceeding with verbatim transcript.",
                    reason=str(clean_exc),
                    stage="transcript_cleaning",
                )
            t3_dur = (time.perf_counter() - t3_start) * 1000
            step_logger.success_step(
                3,
                "Transcript post-processing completed",
                stage="transcript_cleaning",
                duration_ms=t3_dur,
                details={"cleaned_length": len(cleaned_text)},
            )

            # Step 4/6: Clinical Information Extraction & Step 5/6: Guardrails
            current_step = 4
            state.stage = PipelineStage.CLINICAL_EXTRACTION
            soap_note = self.extraction_agent.extract_soap_sync(
                transcript=transcript,
                request_id=req_id,
                step_logger=step_logger,
                step_num=4,
                total_steps=6,
            )
            state.soap_note = soap_note

            # Step 6/6: Form Packaging & Physician Review Packaging
            current_step = 6
            step_logger.start_step(
                6,
                "Packaging clinical execution state for physician review",
                stage="packaging",
            )
            total_duration_ms = (time.perf_counter() - start_time) * 1000
            state.stage = PipelineStage.COMPLETED
            state.is_success = True
            state.duration_ms = total_duration_ms

            step_logger.success_step(
                6,
                "Clinical documentation ready for physician sign-off",
                stage="packaging",
                duration_ms=total_duration_ms,
                details={"review_required": soap_note.review_required, "warnings_count": len(soap_note.validation_warnings)},
            )
            return state

        except (AudioValidationError, TranscriptionError, TranscriptValidationError, ClinicalExtractionError) as exc:
            total_duration_ms = (time.perf_counter() - start_time) * 1000
            state.stage = PipelineStage.FAILED
            state.is_success = False
            state.error_message = exc.message
            state.duration_ms = total_duration_ms

            step_logger.fail_step(
                step=current_step,
                title=f"Pipeline failed at stage '{state.stage.value}': {exc.message}",
                stage="pipeline_failure",
                duration_ms=total_duration_ms,
                error_category=exc.category,
            )
            raise exc

        except Exception as exc:
            total_duration_ms = (time.perf_counter() - start_time) * 1000
            state.stage = PipelineStage.FAILED
            state.is_success = False
            state.error_message = "Unexpected error during pipeline execution."
            state.duration_ms = total_duration_ms

            step_logger.fail_step(
                step=current_step,
                title=f"Unexpected pipeline failure: {str(exc)}",
                stage="pipeline_failure",
                duration_ms=total_duration_ms,
                error_category="unexpected_error",
            )
            raise ClinicalExtractionError(f"Pipeline failed: {str(exc)}") from exc
