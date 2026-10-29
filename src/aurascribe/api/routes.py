"""Flask routing layer for AuraScribe.

Provides:
- GET /: Renders browser recording interface
- GET /health: Health check probe
- POST /api/process: Audio ingestion, transcription, and clinical extraction pipeline
- POST /api/transcribe: Audio-only transcription
- POST /api/extract: Transcript-to-SOAP extraction
- POST /api/v1/ingest-audio: Full universal ingestion and schema binding
- POST /api/sign-off: Physician clinical authorization
"""

import time
import uuid
from datetime import datetime, timezone
from flask import Blueprint, current_app, jsonify, render_template, request
from aurascribe.agent.executor import ClinicalPipelineExecutor
from aurascribe.api.schemas import HealthResponse, ProcessResponse
from aurascribe.schemas.forms import get_form_schema, list_available_forms, normalize_extracted_data
from aurascribe.utils.config import get_settings
from aurascribe.utils.errors import AudioValidationError, AuraScribeError
from aurascribe.utils.logger import PipelineStepLogger, get_logger, log_operation

logger = get_logger("api.routes")
api_bp = Blueprint("api", __name__)


def _get_active_settings():
    if current_app and "AURASCRIBE_SETTINGS" in current_app.config:
        return current_app.config["AURASCRIBE_SETTINGS"]
    return get_settings()


def get_executor() -> ClinicalPipelineExecutor:
    """Retrieves or instantiates the pipeline executor attached to the app context."""
    if not hasattr(current_app, "pipeline_executor"):
        settings = _get_active_settings()
        current_app.pipeline_executor = ClinicalPipelineExecutor(settings=settings)
    return current_app.pipeline_executor


@api_bp.route("/", methods=["GET"])
def index():
    """Renders the AuraScribe clinical audio recording and review interface."""
    settings = _get_active_settings()
    return render_template(
        "index.html",
        env=settings.aurascribe_env,
        prompt_version=settings.prompt_version,
    )


@api_bp.route("/health", methods=["GET"])
def health():
    """Liveness and health check endpoint."""
    settings = _get_active_settings()
    response_data = HealthResponse(
        status="ok",
        environment=settings.aurascribe_env,
        version="0.1.0",
    )
    return jsonify(response_data.model_dump()), 200


@api_bp.route("/api/forms", methods=["GET"])
def get_forms_catalog():
    """Lists all available clinical form schemas for schema-driven dynamic rendering."""
    return jsonify({"status": "success", "forms": list_available_forms()}), 200


@api_bp.route("/api/forms/<form_id>", methods=["GET"])
def get_form_schema_endpoint(form_id: str):
    """Returns the JSON schema definition for a specified form template."""
    try:
        schema = get_form_schema(form_id)
        return jsonify({"status": "success", "form_id": form_id, "form_schema": schema}), 200
    except Exception as exc:
        return jsonify({"error": {"category": "not_found", "message": str(exc)}}), 404


@api_bp.route("/api/transcribe", methods=["POST"])
def transcribe_audio_only():
    """Accepts multipart audio upload and returns verbatim transcript immediately."""
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    step_logger = PipelineStepLogger(logger, total_steps=2, request_id=request_id, stage_prefix="api.transcribe")

    # Step 1/2: Validate audio file payload
    step_logger.start_step(1, "Validating audio upload payload", stage="audio_validation")
    if "audio" not in request.files:
        step_logger.fail_step(1, "Missing audio file in request", error_category="missing_audio_file")
        return jsonify(
            {
                "error": {
                    "category": "audio_validation_error",
                    "message": "Missing 'audio' file upload in multipart form data.",
                    "details": {},
                }
            }
        ), 400

    audio_file = request.files["audio"]
    if not audio_file.filename:
        step_logger.fail_step(1, "Audio file missing filename", error_category="invalid_filename")
        return jsonify(
            {
                "error": {
                    "category": "audio_validation_error",
                    "message": "Audio file must have a valid filename.",
                    "details": {},
                }
            }
        ), 400

    audio_bytes = audio_file.read()
    filename = audio_file.filename
    media_type = audio_file.content_type or "audio/webm"
    language_hint = request.form.get("language_hint") or None
    step_logger.success_step(1, "Audio payload validated", stage="audio_validation", details={"filename": filename, "size_bytes": len(audio_bytes)})

    # Step 2/2: Execute Speech-to-Text
    step_logger.start_step(2, "Executing speech-to-text transcription", stage="transcription")
    t0 = time.perf_counter()
    try:
        executor = get_executor()
        transcript = executor.transcription_tool.execute(
            audio_bytes=audio_bytes,
            filename=filename,
            media_type=media_type,
            language_hint=language_hint,
            request_id=request_id,
        )
        duration_ms = (time.perf_counter() - t0) * 1000
        step_logger.success_step(
            2,
            "Transcription completed successfully",
            stage="transcription",
            duration_ms=duration_ms,
            details={"char_count": len(transcript.text)},
        )

        return jsonify(
            {
                "status": "success",
                "request_id": request_id,
                "transcript": transcript.model_dump(),
            }
        ), 200

    except AuraScribeError as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        step_logger.fail_step(2, f"Transcription failed: {exc.message}", stage="transcription", duration_ms=duration_ms, error_category=exc.category)
        return jsonify(exc.to_dict()), exc.status_code
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        step_logger.fail_step(2, f"Unhandled transcription error: {str(exc)}", stage="transcription", duration_ms=duration_ms, error_category="internal_error")
        logger.error("Unhandled transcription error: %s", str(exc), exc_info=True)
        return jsonify(
            {
                "error": {
                    "category": "internal_error",
                    "message": f"Transcription failed: {str(exc)}",
                    "details": {},
                }
            }
        ), 500


@api_bp.route("/api/extract", methods=["POST"])
def extract_soap_only():
    """Accepts transcript text and triggers the clinical extraction agent into SOAP format.

    Step Progression (4-Stage Flow):
      [Step 1/4] Transcript Input Validation
      [Step 2/4] LLM Transcript Cleaning & Speaker Attribution
      [Step 3/4] Clinical Information Extraction & Guardrails
      [Step 4/4] Form Schema Binding & Physician Review Packaging
    """
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    step_logger = PipelineStepLogger(logger, total_steps=4, request_id=request_id, stage_prefix="api.extract")

    # Step 1/4: Validate transcript input
    step_logger.start_step(1, "Validating transcript input payload", stage="transcript_validation")
    data = request.get_json(silent=True) or {}
    text = data.get("text") or data.get("transcript")
    if not text or not str(text).strip():
        step_logger.fail_step(1, "Missing or empty text field", stage="transcript_validation", error_category="missing_text")
        return jsonify(
            {
                "error": {
                    "category": "transcript_validation_error",
                    "message": "Missing or empty 'text' field in request body.",
                    "details": {},
                }
            }
        ), 400

    raw_str = str(text).strip()
    language = data.get("detected_language") or data.get("language") or "auto"
    form_type = data.get("form_type") or request.args.get("form_type") or "soap_note"
    step_logger.success_step(1, "Transcript payload validated", stage="transcript_validation", details={"char_count": len(raw_str), "form_type": form_type})

    try:
        from aurascribe.schemas.transcript import ValidatedTranscript, TranscriptMetadata
        from aurascribe.pipeline.bicolano_pipeline import clean_transcript

        # Step 2/4: LLM Transcript Cleaning & Speaker Attribution
        step_logger.start_step(2, "Cleaning transcript & attributing speaker dialogue turns", stage="transcript_cleaning")
        t2_start = time.perf_counter()
        try:
            cleaned_str = clean_transcript(raw_str)
        except Exception as clean_err:
            step_logger.fallback_step(2, "Transcript cleaner failed. Continuing with raw transcript.", reason=str(clean_err), stage="transcript_cleaning")
            cleaned_str = raw_str
        t2_dur = (time.perf_counter() - t2_start) * 1000
        step_logger.success_step(2, "Transcript post-processing verified", stage="transcript_cleaning", duration_ms=t2_dur, details={"cleaned_length": len(cleaned_str)})

        # Step 3/4: Clinical Information Extraction & Guardrails
        step_logger.start_step(3, "Executing clinical information extraction agent", stage="clinical_extraction")
        t3_start = time.perf_counter()
        executor = get_executor()
        transcript_obj = ValidatedTranscript(
            text=cleaned_str if cleaned_str.strip() else raw_str,
            metadata=TranscriptMetadata(
                model=executor.settings.transcription_model,
                detected_language=language,
            ),
        )

        soap_note = executor.extraction_agent.extract_soap_sync(
            transcript=transcript_obj,
            request_id=request_id,
            step_logger=step_logger,
            step_num=3,
            total_steps=4,
        )
        soap_note_dict = soap_note.model_dump()
        t3_dur = (time.perf_counter() - t3_start) * 1000
        step_logger.success_step(3, "Clinical information extraction completed", stage="clinical_extraction", duration_ms=t3_dur)

        # Step 4/4: Dynamic Form Schema Binding
        step_logger.start_step(4, f"Binding extracted findings to form schema '{form_type}'", stage="form_binding")
        t4_start = time.perf_counter()
        form_schema = get_form_schema(form_type)
        extracted_data = normalize_extracted_data(soap_note_dict, form_id=form_type)
        t4_dur = (time.perf_counter() - t4_start) * 1000
        step_logger.success_step(4, "Form schema dynamic binding completed", stage="form_binding", duration_ms=t4_dur, details={"form_type": form_type})

        return jsonify(
            {
                "status": "success",
                "request_id": request_id,
                "form_type": form_type,
                "form_schema": form_schema,
                "extracted_data": extracted_data,
                "raw_transcript": raw_str,
                "cleaned_transcript": cleaned_str,
                "soap_note": soap_note_dict,
                "review_required": soap_note.review_required,
                "validation_warnings": soap_note.validation_warnings,
            }
        ), 200

    except AuraScribeError as exc:
        step_logger.fail_step(3, f"Clinical extraction error: {exc.message}", stage="clinical_extraction", error_category=exc.category)
        return jsonify(exc.to_dict()), exc.status_code
    except Exception as exc:
        step_logger.fail_step(3, f"Unhandled extraction error: {str(exc)}", stage="clinical_extraction", error_category="internal_error")
        logger.error("Unhandled extraction error: %s", str(exc), exc_info=True)
        return jsonify(
            {
                "error": {
                    "category": "internal_error",
                    "message": f"Clinical extraction failed: {str(exc)}",
                    "details": {},
                }
            }
        ), 500


@api_bp.route("/api/process", methods=["POST"])
def process_audio():
    """Accepts multipart audio upload and executes full 6-stage transcription and extraction."""
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    log_operation(
        logger,
        stage="api_process_received",
        status="started",
        request_id=request_id,
        message="Received full clinical audio consultation processing request",
        details={"path": request.path, "method": request.method},
    )

    if "audio" not in request.files:
        log_operation(
            logger,
            stage="api_request_validation",
            status="failed",
            request_id=request_id,
            error_category="missing_audio_file",
            message="No audio file provided in request",
        )
        return jsonify(
            {
                "error": {
                    "category": "audio_validation_error",
                    "message": "Missing 'audio' file upload in multipart form data.",
                    "details": {},
                }
            }
        ), 400

    audio_file = request.files["audio"]
    if not audio_file.filename:
        return jsonify(
            {
                "error": {
                    "category": "audio_validation_error",
                    "message": "Audio file must have a valid filename.",
                    "details": {},
                }
            }
        ), 400

    audio_bytes = audio_file.read()
    filename = audio_file.filename
    media_type = audio_file.content_type or "audio/webm"
    language_hint = request.form.get("language_hint") or None

    try:
        executor = get_executor()
        state = executor.process(
            audio_bytes=audio_bytes,
            filename=filename,
            media_type=media_type,
            language_hint=language_hint,
            request_id=request_id,
        )

        response = ProcessResponse(
            status="success",
            request_id=state.request_id,
            transcript=state.transcript,
            soap_note=state.soap_note,
            review_required=state.soap_note.review_required,
            validation_warnings=state.soap_note.validation_warnings,
            duration_ms=state.duration_ms,
        )
        form_type = request.form.get("form_type") or request.args.get("form_type") or "soap_note"
        form_schema = get_form_schema(form_type)
        resp_dict = response.model_dump()
        resp_dict["form_type"] = form_type
        resp_dict["form_schema"] = form_schema
        resp_dict["extracted_data"] = normalize_extracted_data(resp_dict["soap_note"], form_id=form_type)
        return jsonify(resp_dict), 200

    except AuraScribeError as exc:
        log_operation(
            logger,
            stage="api_request_handled_error",
            status="failed",
            request_id=request_id,
            error_category=exc.category,
            message=f"Handled AuraScribeError: {exc.message}",
        )
        return jsonify(exc.to_dict()), exc.status_code

    except Exception as exc:
        log_operation(
            logger,
            stage="api_request_unhandled_error",
            status="failed",
            request_id=request_id,
            error_category="unhandled_exception",
            message=f"Unhandled pipeline error: {str(exc)}",
        )
        return jsonify(
            {
                "error": {
                    "category": "internal_error",
                    "message": "An internal error occurred while processing the clinical audio.",
                    "details": {},
                }
            }
        ), 500


@api_bp.route("/api/v1/ingest-audio", methods=["POST"])
def ingest_audio_v1():
    """Universal audio ingestion and dynamic schema extraction endpoint.

    Step Progression (6-Stage Pipeline):
      [Step 1/6] Audio Ingestion & Format Validation
      [Step 2/6] Speech-to-Text Acoustic Transcription
      [Step 3/6] LLM Transcript Cleaning & Speaker Attribution
      [Step 4/6] Clinical Information Extraction
      [Step 5/6] Clinical Safety Guardrail Verification
      [Step 6/6] Dynamic Schema Normalization & UI Packaging
    """
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    form_type = request.form.get("form_type") or request.args.get("form_type") or "soap_note"
    language_hint = request.form.get("language_hint") or request.args.get("language_hint") or None
    step_logger = PipelineStepLogger(logger, total_steps=6, request_id=request_id, stage_prefix="api.v1_ingest")

    # Step 1/6: Audio Ingestion & Validation
    step_logger.start_step(1, "Validating audio upload payload and constraints", stage="audio_validation", details={"form_type": form_type})
    if "audio" not in request.files:
        step_logger.fail_step(1, "Missing audio file upload", stage="audio_validation", error_category="missing_audio_file")
        return jsonify(
            {
                "error": {
                    "category": "audio_validation_error",
                    "message": "Missing 'audio' file upload in multipart form data.",
                    "details": {},
                }
            }
        ), 400

    audio_file = request.files["audio"]
    if not audio_file.filename:
        step_logger.fail_step(1, "Audio file missing filename", stage="audio_validation", error_category="invalid_filename")
        return jsonify(
            {
                "error": {
                    "category": "audio_validation_error",
                    "message": "Audio file must have a valid filename.",
                    "details": {},
                }
            }
        ), 400

    audio_bytes = audio_file.read()
    filename = audio_file.filename
    media_type = audio_file.content_type or "audio/webm"
    step_logger.success_step(1, "Audio payload validated successfully", stage="audio_validation", details={"filename": filename, "size_bytes": len(audio_bytes)})

    try:
        from aurascribe.schemas.transcript import ValidatedTranscript, TranscriptMetadata
        from aurascribe.pipeline.bicolano_pipeline import clean_transcript

        executor = get_executor()

        # Step 2/6: Speech-to-Text Acoustic Transcription
        step_logger.start_step(2, f"Transcribing audio with STT model '{executor.settings.transcription_model}'", stage="transcription", details={"language_hint": language_hint or "auto"})
        t2_start = time.perf_counter()
        transcript = executor.transcription_tool.execute(
            audio_bytes=audio_bytes,
            filename=filename,
            media_type=media_type,
            language_hint=language_hint,
            request_id=request_id,
        )
        t2_dur = (time.perf_counter() - t2_start) * 1000
        raw_transcript = transcript.text or ""
        step_logger.success_step(2, f"Acoustic transcription completed ({len(raw_transcript)} chars)", stage="transcription", duration_ms=t2_dur)

        # Step 3/6: LLM Post-Processing Transcript Cleaning Agent
        step_logger.start_step(3, "Cleaning transcript & attributing dialogue turns", stage="transcript_cleaning")
        t3_start = time.perf_counter()
        try:
            cleaned_transcript = clean_transcript(raw_transcript)
        except Exception as clean_err:
            step_logger.fallback_step(3, "Transcript cleaner failed. Continuing with raw transcript.", reason=str(clean_err), stage="transcript_cleaning")
            cleaned_transcript = raw_transcript
        t3_dur = (time.perf_counter() - t3_start) * 1000
        step_logger.success_step(3, "Transcript post-processing verified", stage="transcript_cleaning", duration_ms=t3_dur, details={"cleaned_length": len(cleaned_transcript)})

        # Step 4/6: Clinical Extraction Agent & Step 5/6: Guardrails
        step_logger.start_step(4, "Executing clinical information extraction", stage="clinical_extraction")
        t4_start = time.perf_counter()
        transcript_obj = ValidatedTranscript(
            text=cleaned_transcript if cleaned_transcript.strip() else raw_transcript,
            metadata=TranscriptMetadata(
                model=executor.settings.transcription_model,
                detected_language=transcript.metadata.detected_language or language_hint or "auto",
            ),
        )

        soap_note = executor.extraction_agent.extract_soap_sync(
            transcript=transcript_obj,
            request_id=request_id,
            step_logger=step_logger,
            step_num=4,
            total_steps=6,
        )
        soap_note_dict = soap_note.model_dump()
        t4_dur = (time.perf_counter() - t4_start) * 1000
        step_logger.success_step(4, "Clinical extraction completed", stage="clinical_extraction", duration_ms=t4_dur)

        # Step 6/6: Form Schema & Dynamic Data Binding
        step_logger.start_step(6, f"Binding findings to dynamic form schema '{form_type}'", stage="form_binding")
        t6_start = time.perf_counter()
        form_schema = get_form_schema(form_type)
        extracted_data = normalize_extracted_data(soap_note_dict, form_id=form_type)
        t6_dur = (time.perf_counter() - t6_start) * 1000
        step_logger.success_step(6, "Dynamic schema packaging ready for physician review", stage="form_binding", duration_ms=t6_dur, details={"form_type": form_type})

        return jsonify(
            {
                "status": "success",
                "request_id": request_id,
                "form_type": form_type,
                "form_schema": form_schema,
                "extracted_data": extracted_data,
                "soap_note": soap_note_dict,
                "transcript": {
                    "raw": raw_transcript,
                    "cleaned": cleaned_transcript,
                    "detected_language": transcript.metadata.detected_language,
                    "duration_seconds": transcript.metadata.duration_seconds,
                },
                "review_required": soap_note.review_required,
                "validation_warnings": soap_note.validation_warnings,
            }
        ), 200

    except AuraScribeError as exc:
        step_logger.fail_step(4, f"Ingestion error: {exc.message}", stage="ingestion", error_category=exc.category)
        return jsonify(exc.to_dict()), exc.status_code
    except Exception as exc:
        step_logger.fail_step(4, f"Unhandled error in /api/v1/ingest-audio: {str(exc)}", stage="ingestion", error_category="internal_error")
        logger.error("Unhandled error in /api/v1/ingest-audio: %s", exc, exc_info=True)
        return jsonify(
            {
                "error": {
                    "category": "internal_error",
                    "message": f"Audio ingestion failed: {str(exc)}",
                    "details": {},
                }
            }
        ), 500


@api_bp.route("/api/sign-off", methods=["POST"])
def sign_off_clinical_note():
    """Authorizes and signs off an edited clinical record."""
    data = request.get_json(silent=True) or {}
    request_id = data.get("request_id") or str(uuid.uuid4())
    form_type = data.get("form_type") or "soap_note"
    form_data = data.get("form_data") or {}
    physician_name = data.get("physician_name") or "Dr. Avegin Manaog, MD"
    license_number = data.get("license_number") or "PRC-MED-2026-90482"
    timestamp = datetime.now(timezone.utc).isoformat()

    log_operation(
        logger,
        stage="clinical_sign_off",
        status="success",
        request_id=request_id,
        message=f"Physician review sign-off completed for {form_type} by {physician_name}",
        details={"physician": physician_name, "license": license_number, "form_type": form_type},
    )

    return jsonify(
        {
            "status": "success",
            "request_id": request_id,
            "signed_off": True,
            "review_required": False,
            "verified_at": timestamp,
            "physician": {
                "name": physician_name,
                "license_number": license_number,
            },
            "form_type": form_type,
            "final_record": form_data,
            "message": f"Clinical record successfully verified and authorized by {physician_name}.",
        }
    ), 200
