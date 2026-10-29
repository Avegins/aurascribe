"""Multilingual Audio & Clinical Extraction Pipeline.

Specialized for Tagalog, Taglish, and Bicolano (Central Bikol, Rinconada, Albay) dialects.
Provides modular functions:
1. preprocess_audio(input_file_path: str) -> str
2. transcribe_audio(audio_file_path: str) -> str
3. clean_transcript(raw_transcript: str) -> str
4. generate_soap_note(cleaned_transcript: str) -> dict
"""

import io
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI, APIConnectionError, APIStatusError, RateLimitError
from aurascribe.utils.config import Settings, get_settings
from aurascribe.utils.errors import AudioValidationError, TranscriptionError, ClinicalExtractionError
from aurascribe.utils.logger import PipelineStepLogger, get_logger

logger = get_logger("pipeline.bicolano")

# Regional vocabulary hint for Speech-to-Text decoding bias
BICOLANO_TAGLISH_PROMPT = (
    "Clinical medical consultation in Tagalog, Taglish, and Bicolano (Central Bikol, Rinconada, Albay). "
    "Key terms: masakit (pain), ubo (cough), hilanat/lagnat (fever), alipunga, tyan (stomach), likod (back), "
    "nireseta (prescribed), mabalos (thank you), maray (good), dai (no), iyo (yes), tatlong araw (3 days), gamot (medicine)."
)

# Transcript Cleaning Agent Prompt
TRANSCRIPT_CLEANER_SYSTEM_PROMPT = """You are a specialized medical transcription editor fluent in English, Tagalog, Taglish, and Bicolano dialects.

Task:
Clean and format the raw consultation transcript.

Rules:
1. Fix misspellings or phonetically mistranscribed local words (e.g., convert 'masakat' to 'masakit', 'tatmong' to 'tatlong').
2. Normalize Bicolano phrases into standard context while maintaining accuracy (e.g., 'hilanat' -> fever, 'dai nin gamot' -> no medications).
3. Remove filler words ('po', 'ano', 'kuwan', 'daa', 'tabi') without altering clinical meaning.
4. Identify and attribute turns to speakers:
   Doctor: <spoken text>
   Patient: <spoken text>

Input Transcript: {raw_transcript}"""

# Structured SOAP Note Extraction Agent Prompt
SOAP_NOTE_SYSTEM_PROMPT = """You are an expert bilingual clinical scribe assistant.

Task:
Translate and extract clinical findings from the transcript into a structured English SOAP note.

Input Transcript: {cleaned_transcript}

Output JSON Format Strict Requirements:
{{
  "subjective": {{
    "chief_complaint": "Main reason for visit",
    "history_of_present_illness": "Concise overview of symptoms, duration, severity",
    "current_medications": "List of current meds or 'None reported'"
  }},
  "objective": "Physical observations or reported signs",
  "assessment": "Clinical assessment or primary concern",
  "plan": "Recommended diagnostic steps, prescriptions, or advice"
}}

Respond ONLY with valid JSON. Do not include markdown codeblocks or explanatory commentary."""


def _get_llm_client(settings: Optional[Settings] = None) -> tuple[OpenAI, str, list[str]]:
    """Helper to initialize client and fallback models according to settings."""
    cfg = settings or get_settings()
    
    # Determine API key and base URL
    provider = (cfg.llm_provider or "openai").lower().strip()
    
    fallback_models = []
    if provider in ("custom", "openai_compatible") and cfg.custom_base_url:
        client = OpenAI(
            base_url=cfg.custom_base_url,
            api_key=cfg.custom_api_key or cfg.openai_api_key or "custom-key",
            timeout=cfg.request_timeout_seconds,
        )
        primary_model = cfg.llm_model or "openai/gpt-oss-120b"
        fallback_models = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b", "llama-3.3-70b-versatile"]
    elif provider in ("llama_cpp", "llamacpp"):
        base_url = (cfg.llama_cpp_base_url or "http://localhost:8080/v1").rstrip("/")
        if not base_url.endswith("/v1"):
            base_url = f"{base_url}/v1"
        client = OpenAI(base_url=base_url, api_key="not-needed", timeout=cfg.request_timeout_seconds)
        primary_model = cfg.llm_model or "qwen2.5-7b-instruct"
    elif provider == "ollama":
        base_url = (cfg.ollama_base_url or "http://localhost:11434/v1").rstrip("/")
        if not base_url.endswith("/v1"):
            base_url = f"{base_url}/v1"
        client = OpenAI(base_url=base_url, api_key=cfg.ollama_api_key or "ollama", timeout=cfg.request_timeout_seconds)
        primary_model = cfg.llm_model or "qwen3.5:9b-q8_0"
    else:
        # Default OpenAI Cloud
        api_key = cfg.openai_api_key
        client = OpenAI(api_key=api_key or "dummy", timeout=cfg.request_timeout_seconds)
        primary_model = cfg.llm_model or "gpt-4o-mini"
        fallback_models = ["gpt-4o-mini", "gpt-3.5-turbo"]

    return client, primary_model, fallback_models


# ==============================================================================
# STEP 1: AUDIO NOISE REDUCTION
# ==============================================================================
def preprocess_audio(
    input_file_path: str,
    output_file_path: Optional[str] = None,
    step_logger: Optional[PipelineStepLogger] = None,
) -> str:
    """Pre-processes recorded audio with noise reduction using librosa, noisereduce, and soundfile.

    Filters out background noises (e.g., fans, static, ambient room chatter).
    Exports and returns the filepath of the cleaned audio file (cleaned_consultation.wav).

    Args:
        input_file_path: Absolute or relative path to the raw audio file.
        output_file_path: Optional destination path. Defaults to 'cleaned_consultation.wav'
                          in the same folder as the input.
        step_logger: Optional PipelineStepLogger instance for progress tracing.

    Returns:
        str: Filepath of the cleaned audio file.
    """
    s_logger = step_logger or PipelineStepLogger(logger, total_steps=4, stage_prefix="bicolano")

    if not os.path.exists(input_file_path):
        raise FileNotFoundError(f"Audio file not found at: {input_file_path}")

    input_path = Path(input_file_path)
    if not output_file_path:
        output_file_path = str(input_path.parent / "cleaned_consultation.wav")

    s_logger.start_step(
        1,
        f"Audio noise reduction & spectral filtering on '{input_path.name}'",
        stage="audio_preprocessing",
        details={"file": input_file_path},
    )
    t0 = time.perf_counter()

    try:
        import librosa
        import noisereduce as nr
        import soundfile as sf

        # Load audio at 16kHz (optimal sample rate for Whisper models)
        audio_data, sample_rate = librosa.load(str(input_path), sr=16000)

        # Apply spectral gating to reduce background ambient noise (static, fans, room hum)
        reduced_audio = nr.reduce_noise(
            y=audio_data,
            sr=sample_rate,
            stationary=True,
            prop_decrease=0.75,
        )

        # Export to 16-bit WAV
        sf.write(output_file_path, reduced_audio, sample_rate, subtype="PCM_16", format="WAV")
        duration_ms = (time.perf_counter() - t0) * 1000
        s_logger.success_step(
            1,
            f"Cleaned audio exported to '{Path(output_file_path).name}'",
            stage="audio_preprocessing",
            duration_ms=duration_ms,
            details={"output_path": output_file_path},
        )
        return output_file_path

    except ImportError as exc:
        s_logger.fallback_step(
            1,
            "Audio preprocessing libraries (librosa, noisereduce, soundfile) not installed. Passing original audio file.",
            reason=str(exc),
            stage="audio_preprocessing",
        )
        return str(input_file_path)

    except Exception as exc:
        s_logger.fallback_step(
            1,
            f"Audio noise reduction failed ({exc}). Passing original audio file.",
            reason=str(exc),
            stage="audio_preprocessing",
        )
        return str(input_file_path)


# ==============================================================================
# STEP 2: STT TRANSCRIPTION WITH LANGUAGE HINTING
# ==============================================================================
def transcribe_audio(
    audio_file_path: str,
    prompt: Optional[str] = None,
    language_hint: Optional[str] = None,
    temperature: float = 0.0,
    settings: Optional[Settings] = None,
    step_logger: Optional[PipelineStepLogger] = None,
) -> str:
    """Transcribes audio using Whisper / Groq / OpenAI with regional Bicolano/Taglish vocabulary hints.

    Args:
        audio_file_path: Path to the clean or raw audio file.
        prompt: Optional initial prompt string (defaults to regional Bicolano/Taglish dictionary).
        language_hint: Optional ISO language code (e.g. 'tl', 'en').
        temperature: Sampling temperature for decoding (set to 0.0 for deterministic factual fidelity).
        settings: Application settings.
        step_logger: Optional PipelineStepLogger instance for progress tracing.

    Returns:
        str: Raw transcription string.
    """
    s_logger = step_logger or PipelineStepLogger(logger, total_steps=4, stage_prefix="bicolano")
    cfg = settings or get_settings()

    if not os.path.exists(audio_file_path):
        raise FileNotFoundError(f"Audio file to transcribe not found at: {audio_file_path}")

    # Initialize transcription client
    api_key = cfg.openai_api_key or cfg.custom_api_key
    base_url = cfg.transcription_base_url or (cfg.custom_base_url if cfg.llm_provider == "custom" else None)
    
    if not api_key and not base_url:
        raise TranscriptionError(
            "OPENAI_API_KEY or AURASCRIBE_TRANSCRIPTION_BASE_URL must be configured for Speech-to-Text."
        )

    client_kwargs = {
        "api_key": api_key or "not-needed",
        "timeout": cfg.request_timeout_seconds,
    }
    if base_url:
        client_kwargs["base_url"] = base_url

    client = OpenAI(**client_kwargs)

    effective_prompt = prompt or getattr(cfg, "transcription_prompt", None) or BICOLANO_TAGLISH_PROMPT
    file_path = Path(audio_file_path)

    s_logger.start_step(
        2,
        f"Submitting audio to STT model '{cfg.transcription_model}' with regional prompt hints",
        stage="transcription",
        details={"model": cfg.transcription_model, "temperature": temperature, "language_hint": language_hint or "auto"},
    )
    t0 = time.perf_counter()

    try:
        with open(file_path, "rb") as f:
            kwargs = {
                "model": cfg.transcription_model,
                "file": f,
                "response_format": "verbose_json",
                "temperature": temperature,
                "prompt": effective_prompt,
            }
            if language_hint:
                kwargs["language"] = language_hint

            response = client.audio.transcriptions.create(**kwargs)
            transcript_text = getattr(response, "text", "") or ""

        if not transcript_text.strip():
            raise TranscriptionError("Transcription service produced an empty transcript.")

        duration_ms = (time.perf_counter() - t0) * 1000
        s_logger.success_step(
            2,
            f"STT transcription completed ({len(transcript_text)} characters)",
            stage="transcription",
            duration_ms=duration_ms,
            details={"char_count": len(transcript_text)},
        )
        return transcript_text.strip()

    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        s_logger.fail_step(
            2,
            f"Speech-to-Text transcription failed: {exc}",
            stage="transcription",
            duration_ms=duration_ms,
            error_category="stt_error",
        )
        raise TranscriptionError(f"Speech-to-Text transcription failed: {str(exc)}") from exc


# ==============================================================================
# STEP 3: TRANSCRIPT CLEANING AGENT (POST-PROCESSING)
# ==============================================================================
def clean_transcript(
    raw_transcript: str,
    model: Optional[str] = None,
    settings: Optional[Settings] = None,
    step_logger: Optional[PipelineStepLogger] = None,
) -> str:
    """Passes raw transcript to an LLM agent to fix misspellings, normalize Bicolano terms,
    remove filler words, and format speaker turns (Doctor: / Patient:).

    Args:
        raw_transcript: Raw text generated by the STT model.
        model: Optional LLM model override.
        settings: Application settings.
        step_logger: Optional PipelineStepLogger instance for progress tracing.

    Returns:
        str: Cleaned, speaker-attributed transcript.
    """
    if not raw_transcript or not raw_transcript.strip():
        return ""

    s_logger = step_logger or PipelineStepLogger(logger, total_steps=4, stage_prefix="bicolano")
    cfg = settings or get_settings()
    client, default_model, fallback_models = _get_llm_client(cfg)
    target_model = model or default_model

    formatted_system_prompt = TRANSCRIPT_CLEANER_SYSTEM_PROMPT.format(raw_transcript=raw_transcript)
    models_to_try = [target_model] + [m for m in fallback_models if m != target_model]
    last_error = None

    s_logger.start_step(
        3,
        f"Executing Transcript Cleaning Agent (model='{target_model}')",
        stage="transcript_cleaning",
        details={"model": target_model, "raw_length": len(raw_transcript)},
    )
    t0 = time.perf_counter()

    for candidate_model in models_to_try:
        try:
            response = client.chat.completions.create(
                model=candidate_model,
                messages=[
                    {"role": "system", "content": formatted_system_prompt},
                    {"role": "user", "content": f"Please clean and structure this transcript:\n\n{raw_transcript}"},
                ],
                temperature=0.1,
            )
            cleaned = response.choices[0].message.content or ""
            if cleaned.strip():
                duration_ms = (time.perf_counter() - t0) * 1000
                s_logger.success_step(
                    3,
                    f"Transcript cleaning succeeded with model '{candidate_model}'",
                    stage="transcript_cleaning",
                    duration_ms=duration_ms,
                    details={"model": candidate_model, "cleaned_length": len(cleaned.strip())},
                )
                return cleaned.strip()

        except Exception as exc:
            s_logger.fallback_step(
                3,
                f"Transcript cleaner attempt failed with model '{candidate_model}'. Trying candidate fallback...",
                reason=str(exc),
                stage="transcript_cleaning",
            )
            last_error = exc
            continue

    # Graceful fallback: Rule-based heuristic cleanup if all LLM endpoints fail
    s_logger.fallback_step(
        3,
        f"All LLM cleaning models failed ({last_error}). Applying local heuristic normalization.",
        reason=str(last_error),
        stage="transcript_cleaning",
    )
    heuristic_result = _heuristic_clean_transcript(raw_transcript)
    duration_ms = (time.perf_counter() - t0) * 1000
    s_logger.success_step(
        3,
        "Local heuristic transcript normalization applied successfully",
        stage="transcript_cleaning",
        duration_ms=duration_ms,
        details={"method": "heuristic_fallback"},
    )
    return heuristic_result


def _heuristic_clean_transcript(text: str) -> str:
    """Rule-based fallback cleanup for Bicolano/Tagalog phonetic mistranscriptions."""
    cleaned = text
    # Common phonetic replacements
    replacements = {
        r"\bmasakat\b": "masakit",
        r"\btatmong\b": "tatlong",
        r"\bhilanat\b": "hilanat (fever)",
        r"\bdai nin gamot\b": "dai nin gamot (no medications)",
        r"\bmabalos\b": "mabalos (thank you)",
    }
    for pattern, repl in replacements.items():
        cleaned = re.sub(pattern, repl, cleaned, flags=re.IGNORECASE)

    # Remove prominent verbal fillers
    fillers = [r"\bpo\b", r"\bano\b", r"\bkuwan\b", r"\bdaa\b", r"\btabi\b"]
    for f in fillers:
        cleaned = re.sub(f, "", cleaned, flags=re.IGNORECASE)

    return re.sub(r"\s+", " ", cleaned).strip()


# ==============================================================================
# STEP 4: STRUCTURED SOAP NOTE EXTRACTION AGENT
# ==============================================================================
def generate_soap_note(
    cleaned_transcript: str,
    model: Optional[str] = None,
    settings: Optional[Settings] = None,
    step_logger: Optional[PipelineStepLogger] = None,
) -> Dict[str, Any]:
    """Converts the cleaned transcript into a structured English SOAP note dictionary.

    Output format:
    {
      "subjective": {
        "chief_complaint": "Main reason for visit",
        "history_of_present_illness": "Concise overview of symptoms, duration, severity",
        "current_medications": "List of current meds or 'None reported'"
      },
      "objective": "Physical observations or reported signs",
      "assessment": "Clinical assessment or primary concern",
      "plan": "Recommended diagnostic steps, prescriptions, or advice"
    }

    Args:
        cleaned_transcript: Pre-cleaned, speaker-attributed transcript.
        model: Optional active LLM model override.
        settings: Application settings.
        step_logger: Optional PipelineStepLogger instance for progress tracing.

    Returns:
        dict: Strongly validated SOAP note dictionary.
    """
    if not cleaned_transcript or not cleaned_transcript.strip():
        raise ClinicalExtractionError("Cannot generate SOAP note from empty transcript.", status_code=400)

    s_logger = step_logger or PipelineStepLogger(logger, total_steps=4, stage_prefix="bicolano")
    cfg = settings or get_settings()
    client, default_model, fallback_models = _get_llm_client(cfg)
    target_model = model or default_model

    formatted_system_prompt = SOAP_NOTE_SYSTEM_PROMPT.format(cleaned_transcript=cleaned_transcript)
    models_to_try = [target_model] + [m for m in fallback_models if m != target_model]
    last_error = None

    s_logger.start_step(
        4,
        f"Executing Structured SOAP Note Extraction Agent (model='{target_model}')",
        stage="soap_extraction",
        details={"model": target_model, "transcript_length": len(cleaned_transcript)},
    )
    t0 = time.perf_counter()

    for candidate_model in models_to_try:
        try:
            response = client.chat.completions.create(
                model=candidate_model,
                messages=[
                    {"role": "system", "content": formatted_system_prompt},
                    {
                        "role": "user",
                        "content": f"Extract structured clinical SOAP note from this cleaned consultation:\n\n{cleaned_transcript}",
                    },
                ],
                temperature=0.0,
                response_format={"type": "json_object"} if "llama-3" in candidate_model or "gpt" in candidate_model else None,
            )

            content = response.choices[0].message.content or "{}"
            parsed_json = _parse_json_safely(content)

            # Validate mandatory structure
            validated_soap = _validate_soap_dict(parsed_json)
            duration_ms = (time.perf_counter() - t0) * 1000
            s_logger.success_step(
                4,
                f"SOAP note extraction succeeded with model '{candidate_model}'",
                stage="soap_extraction",
                duration_ms=duration_ms,
                details={"model": candidate_model},
            )
            return validated_soap

        except Exception as exc:
            s_logger.fallback_step(
                4,
                f"SOAP note generation attempt failed with model '{candidate_model}'. Trying next candidate...",
                reason=str(exc),
                stage="soap_extraction",
            )
            last_error = exc
            continue

    duration_ms = (time.perf_counter() - t0) * 1000
    s_logger.fail_step(
        4,
        f"All model endpoints failed to extract valid SOAP note: {last_error}",
        stage="soap_extraction",
        duration_ms=duration_ms,
        error_category="all_models_exhausted",
    )
    raise ClinicalExtractionError(
        f"All model endpoints failed to extract valid SOAP note: {last_error}",
        status_code=502,
    )


def _parse_json_safely(text: str) -> Dict[str, Any]:
    """Safely extracts JSON dictionary from LLM responses even if wrapped in markdown blocks."""
    text_clean = text.strip()
    if text_clean.startswith("```"):
        text_clean = re.sub(r"^```(?:json)?\s*", "", text_clean)
        text_clean = re.sub(r"\s*```$", "", text_clean)
        text_clean = text_clean.strip()

    try:
        return json.loads(text_clean)
    except json.JSONDecodeError:
        # Match outermost curly braces
        match = re.search(r"\{.*\}", text_clean, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def _validate_soap_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Ensures extracted dictionary conforms to required schema keys."""
    sub = data.get("subjective", {})
    if not isinstance(sub, dict):
        sub = {
            "chief_complaint": str(sub),
            "history_of_present_illness": "",
            "current_medications": "None reported",
        }

    return {
        "subjective": {
            "chief_complaint": str(sub.get("chief_complaint", "Not specified")),
            "history_of_present_illness": str(sub.get("history_of_present_illness", "")),
            "current_medications": str(sub.get("current_medications", "None reported")),
        },
        "objective": str(data.get("objective", "None documented")),
        "assessment": str(data.get("assessment", "Clinical impression pending")),
        "plan": str(data.get("plan", "Follow-up as recommended")),
    }
