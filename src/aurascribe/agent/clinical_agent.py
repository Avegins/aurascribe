"""Pydantic AI Clinical Extraction Agent.

Coordinates clinical information extraction from verified transcripts into
strongly validated SOAP notes, applying strict anti-hallucination guardrails.
"""

from pathlib import Path
import time
from typing import Optional, Union
from pydantic_ai import Agent
from pydantic_ai.models import Model
from aurascribe.models.llm_client import get_llm_model, get_openai_model
from aurascribe.schemas.soap import SOAPNote
from aurascribe.schemas.transcript import ValidatedTranscript
from aurascribe.utils.config import Settings, get_settings
from aurascribe.utils.errors import ClinicalExtractionError, ConfigurationError
from aurascribe.utils.logger import PipelineStepLogger, get_logger, log_operation

logger = get_logger("agent.clinical_agent")

PROMPT_FILE_PATH = Path(__file__).parent.parent / "prompts" / "clinical_extraction.md"


def load_system_prompt(target_language: Optional[str] = None) -> str:
    """Reads the versioned prompt markdown file and appends target language directives if specified."""
    if not PROMPT_FILE_PATH.exists():
        raise ConfigurationError(f"Prompt template missing at: {PROMPT_FILE_PATH}")
    prompt_text = PROMPT_FILE_PATH.read_text(encoding="utf-8")
    if target_language and target_language.strip().lower() not in ("english", "en", "default"):
        prompt_text += (
            f"\n\n---\n\n## Target Output Language Directive\n\n"
            f"The designated clinical documentation language is: **{target_language.strip()}**.\n"
            f"Translate and synthesize all clinical assessments, impressions, and management plans "
            f"into {target_language.strip()}, while preserving verbatim patient quotes in the Subjective section.\n"
        )
    return prompt_text


class ClinicalExtractionAgent:
    """Executes clinical extraction using Pydantic AI with strict clinical guardrails."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        model: Optional[Union[Model, str]] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.system_prompt = load_system_prompt(target_language=self.settings.target_language)

        if model is not None:
            self.model = model
        else:
            # Fall back to configured model (OpenAI or Ollama) using application settings
            self.model = get_llm_model(settings=self.settings)

        self.agent: Agent[None, SOAPNote] = Agent(
            model=self.model,
            output_type=SOAPNote,
            system_prompt=self.system_prompt,
            retries=self.settings.agent_retry_limit,
        )

    def apply_clinical_guardrails(self, note: SOAPNote, transcript_text: str) -> SOAPNote:
        """Enforces clinical safety, anti-hallucination, and verification guardrails.

        Rules enforced:
        1. Mandatory physician review flag (review_required = True).
        2. Preservation of uncertainties and contradictions in validation warnings.
        3. Audit of clinical impression supporting evidence.
        4. Cross-check for vital signs fabrication.
        """
        # Rule 1: Mandatory Physician Review
        note.review_required = True

        # Copy existing warnings to prevent mutation issues
        warnings = list(note.validation_warnings)

        # Rule 2: Unresolved clinical uncertainties
        if note.assessment.uncertainties:
            for uncertainty in note.assessment.uncertainties:
                warn_msg = f"Unresolved clinical uncertainty: {uncertainty}"
                if warn_msg not in warnings:
                    warnings.append(warn_msg)

        # Rule 3: Clinical Impression Evidence Validation
        if note.assessment.clinical_impression and not note.assessment.supporting_evidence:
            warn_msg = "Clinical impression documented without explicit supporting evidence in transcript."
            if warn_msg not in warnings:
                warnings.append(warn_msg)

        # Rule 4: Anti-hallucination vitals check
        if note.objective.vital_signs:
            vitals = note.objective.vital_signs
            vitals_present = any(
                [
                    vitals.blood_pressure,
                    vitals.heart_rate,
                    vitals.respiratory_rate,
                    vitals.temperature,
                    vitals.oxygen_saturation,
                    vitals.weight,
                ]
            )
            if vitals_present:
                # Basic check if transcript contains numbers or typical vitals indicators
                has_numbers = any(char.isdigit() for char in transcript_text)
                if not has_numbers:
                    warn_msg = "Vital signs present in SOAP note but no numerical data found in transcript. Review for hallucination."
                    if warn_msg not in warnings:
                        warnings.append(warn_msg)

        # Update note warnings
        note.validation_warnings = warnings
        return note

    def extract_soap_sync(
        self,
        transcript: ValidatedTranscript,
        request_id: Optional[str] = None,
        step_logger: Optional[PipelineStepLogger] = None,
        step_num: int = 4,
        total_steps: int = 6,
    ) -> SOAPNote:
        """Synchronously executes the Pydantic AI agent against the transcript."""
        s_logger = step_logger or PipelineStepLogger(
            logger=logger,
            total_steps=total_steps,
            request_id=request_id,
            stage_prefix="clinical",
        )

        s_logger.start_step(
            step=step_num,
            title="Executing Pydantic AI clinical extraction agent",
            stage="clinical_extraction",
            details={
                "model": self.settings.llm_model,
                "prompt_version": self.settings.prompt_version,
                "transcript_length": len(transcript.text),
            },
        )

        start_time = time.perf_counter()
        user_prompt = (
            f"Here is the verbatim clinical dialogue transcript:\n\n"
            f"\"\"\"\n{transcript.text}\n\"\"\"\n\n"
            f"Extract the complete, structured SOAP note adhering strictly to the guidelines."
        )

        try:
            run_result = self.agent.run_sync(user_prompt)
            raw_soap_note: SOAPNote = run_result.output

            duration_ms = (time.perf_counter() - start_time) * 1000
            s_logger.success_step(
                step=step_num,
                title="Primary Pydantic AI clinical extraction completed",
                stage="clinical_extraction",
                duration_ms=duration_ms,
                details={"model": self.settings.llm_model},
            )

            # Step 5: Apply clinical safety guardrails
            guardrail_step = step_num + 1 if total_steps >= step_num + 1 else step_num
            s_logger.start_step(
                step=guardrail_step,
                title="Verifying clinical safety guardrails & anti-hallucination checks",
                stage="guardrails",
            )
            g_start = time.perf_counter()
            guarded_note = self.apply_clinical_guardrails(raw_soap_note, transcript.text)
            g_dur = (time.perf_counter() - g_start) * 1000

            s_logger.success_step(
                step=guardrail_step,
                title="Clinical safety guardrails verified and audit passed",
                stage="guardrails",
                duration_ms=g_dur,
                details={
                    "warnings_count": len(guarded_note.validation_warnings),
                    "review_required": guarded_note.review_required,
                },
            )
            return guarded_note

        except Exception as exc:
            # Fallback & Retry Visibility: Highlight fallback transition
            s_logger.fallback_step(
                step=step_num,
                title="Primary extraction schema rejected. Engaging structured fallback...",
                reason=str(exc),
                stage="clinical_extraction",
            )
            try:
                from aurascribe.pipeline.bicolano_pipeline import generate_soap_note
                from aurascribe.schemas.soap import Subjective, Objective, Assessment, Plan

                soap_dict = generate_soap_note(transcript.text, settings=self.settings)
                sub_dict = soap_dict.get("subjective", {})
                if not isinstance(sub_dict, dict):
                    sub_dict = {"chief_complaint": str(sub_dict)}

                raw_soap_note = SOAPNote(
                    subjective=Subjective(
                        chief_complaint=str(sub_dict.get("chief_complaint") or "Not specified"),
                        history=str(sub_dict.get("history_of_present_illness") or "") or None,
                        symptoms=[str(sub_dict.get("chief_complaint"))] if sub_dict.get("chief_complaint") else [],
                        associated_symptoms=[],
                    ),
                    objective=Objective(
                        examination_findings=str(soap_dict.get("objective") or "") or None,
                        observations=[],
                    ),
                    assessment=Assessment(
                        clinical_impression=str(soap_dict.get("assessment") or "") or None,
                        supporting_evidence=[],
                        uncertainties=[],
                    ),
                    plan=Plan(
                        treatment=str(soap_dict.get("plan") or "") or None,
                        medications=[],
                        tests=[],
                        follow_up=None,
                    ),
                    review_required=True,
                    validation_warnings=[],
                )
                duration_ms = (time.perf_counter() - start_time) * 1000
                s_logger.success_step(
                    step=step_num,
                    title="Structured fallback clinical extraction succeeded",
                    stage="clinical_extraction",
                    duration_ms=duration_ms,
                    details={"fallback": True},
                )

                # Apply clinical guardrails on fallback note
                guardrail_step = step_num + 1 if total_steps >= step_num + 1 else step_num
                s_logger.start_step(
                    step=guardrail_step,
                    title="Verifying clinical safety guardrails on fallback note",
                    stage="guardrails",
                )
                g_start = time.perf_counter()
                guarded_note = self.apply_clinical_guardrails(raw_soap_note, transcript.text)
                g_dur = (time.perf_counter() - g_start) * 1000

                s_logger.success_step(
                    step=guardrail_step,
                    title="Clinical safety guardrails verified on fallback note",
                    stage="guardrails",
                    duration_ms=g_dur,
                    details={
                        "warnings_count": len(guarded_note.validation_warnings),
                        "review_required": guarded_note.review_required,
                    },
                )
                return guarded_note

            except Exception as fallback_exc:
                s_logger.fail_step(
                    step=step_num,
                    title=f"Structured SOAP extraction fallback also failed: {fallback_exc}",
                    stage="clinical_extraction",
                    error_category="agent_run_failure",
                )
                raise ClinicalExtractionError(
                    f"Clinical extraction agent failed to produce a valid SOAP note: {str(exc)}"
                ) from exc
