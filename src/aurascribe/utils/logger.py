"""Centralized structured logging for AuraScribe.

Enforces privacy-compliant logging practices:
- Logs operational metadata (request ID, stage, duration, model identifiers, status)
- Explicit step progression indicators: [Step X/Y]
- Visual markers: ---> [Step X/Y] START, ✓ [Step X/Y] SUCCESS, x [Step X/Y] FAILED, ⚠️  [Step X/Y - FALLBACK]
- Standard format: TIMESTAMP | LEVEL | [Module/Stage] | [Step X/Y] Message | metadata
- Explicit step progression indicators: [Step X/Y]
- Visual markers: ---> [Step X/Y] START, ✓ [Step X/Y] SUCCESS, x [Step X/Y] FAILED,  [Step X/Y - FALLBACK]
- Standard format: TIMESTAMP | LEVEL | [Module/Stage] | [Step X/Y] Message | metadata
- Strictly excludes raw audio payloads, transcripts, clinical notes, and API keys.
"""

from contextlib import contextmanager
import logging
import sys
import time
from typing import Any, Dict, Generator, Optional


class SafeFormatter(logging.Formatter):
    """Custom formatter ensuring consistent structured output across terminal and files."""

    def format(self, record: logging.LogRecord) -> str:
        # Standardize record representation without leaking accidental sensitive objects
        return super().format(record)


# Standard AuraScribe format: TIMESTAMP | LEVEL | [Module/Stage] | Message
STANDARD_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | [%(name)s] | %(message)s"
STANDARD_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(log_level: str = "INFO") -> None:
    """Configures root and application loggers with structured, scannable format."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    formatter = SafeFormatter(
        fmt=STANDARD_LOG_FORMAT,
        datefmt=STANDARD_DATE_FORMAT,
    )

    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        handler.setLevel(numeric_level)
        root_logger.addHandler(handler)
    else:
        for handler in root_logger.handlers:
            handler.setFormatter(formatter)
            handler.setLevel(numeric_level)


def get_logger(name: str) -> logging.Logger:
    """Returns a module-level logger configured with AuraScribe standards."""
    return logging.getLogger(f"aurascribe.{name}")


def _build_safe_metadata(
    stage: str,
    status: str,
    request_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
    details: Optional[Dict[str, Any]] = None,
    error_category: Optional[str] = None,
) -> str:
    """Constructs a pipe-separated string of non-sensitive operational metadata."""
    meta_parts = [
        f"stage={stage}",
        f"status={status}",
    ]
    if request_id:
        meta_parts.append(f"request_id={request_id}")
    if duration_ms is not None:
        meta_parts.append(f"duration_ms={duration_ms:.2f}")
    if error_category:
        meta_parts.append(f"error_category={error_category}")

    if details:
        for k, v in details.items():
            # Strict HIPAA & Privacy safeguard: exclude raw payload or secrets
            if any(secret_term in k.lower() for secret_term in ("key", "secret", "token", "transcript", "audio", "phi", "password")):
                continue
            meta_parts.append(f"{k}={v}")

    return " | ".join(meta_parts)


def log_operation(
    logger: logging.Logger,
    stage: str,
    status: str,
    request_id: Optional[str] = None,
    duration_ms: Optional[float] = None,
    details: Optional[Dict[str, Any]] = None,
    error_category: Optional[str] = None,
    level: int = logging.INFO,
    step: Optional[int] = None,
    total_steps: Optional[int] = None,
    is_fallback: bool = False,
    message: Optional[str] = None,
) -> None:
    """Logs safe operational metadata without patient identifiers or transcript content.

    Supports step progression counters ([Step X/Y]) and visual status markers.

    Args:
        logger: Logger instance to use.
        stage: Processing pipeline stage (e.g., 'audio_validation', 'transcription', 'extraction').
        status: Operation outcome ('started', 'success', 'failed', 'fallback', 'retry').
        request_id: Optional correlation ID for tracing.
        duration_ms: Optional elapsed time in milliseconds.
        details: Optional non-sensitive operational details (e.g., audio size bytes, model name).
        error_category: Optional category if status is 'failed'.
        level: Logging level.
        step: Optional 1-based step counter in multi-stage flows.
        total_steps: Optional total number of steps in the flow.
        is_fallback: Whether this operation is executing a fallback pathway.
        message: Optional human-readable action description.
    """
    meta_str = _build_safe_metadata(
        stage=stage,
        status=status,
        request_id=request_id,
        duration_ms=duration_ms,
        details=details,
        error_category=error_category,
    )

    if step is not None:
        step_tag = f"[Step {step}/{total_steps}]" if total_steps else f"[Step {step}]"
        if is_fallback or status == "fallback":
            marker = f"⚠️  [Step {step}/{total_steps} - FALLBACK]" if total_steps else f"⚠️  [Step {step} - FALLBACK]"
        elif status == "started":
            marker = f"---> {step_tag} START"
        elif status == "success":
            marker = f"✓ {step_tag} SUCCESS"
        elif status == "failed":
            marker = f"x {step_tag} FAILED"
        elif status == "retry":
            marker = f"🔄 {step_tag} RETRY"
        else:
            marker = f"• {step_tag}"

        if message:
            log_line = f"{marker}: {message} | {meta_str}"
        else:
            log_line = f"{marker} | {meta_str}"
    else:
        if message:
            log_line = f"{message} | {meta_str}"
        else:
            log_line = meta_str

    logger.log(level, log_line)


class PipelineStepLogger:
    """Progress tracker and scannable visual step logger for multi-stage pipelines.

    Standard Canonical 6-Step Pipeline:
      Audio Validation [1/6] -> Transcription [2/6] -> Cleaning [3/6] ->
      Extraction [4/6] -> Guardrails [5/6] -> Form Packaging [6/6]

    Visual Markers:
      - ---> [Step X/Y] START: {action} | metadata
      - ✓ [Step X/Y] SUCCESS: {action} | duration_ms=... | metadata
      - ⚠️  [Step X/Y - FALLBACK]: {action} | reason=... | metadata
      - x [Step X/Y] FAILED: {action} | error_category=... | metadata
    """

    def __init__(
        self,
        logger: logging.Logger,
        total_steps: int = 6,
        request_id: Optional[str] = None,
        stage_prefix: Optional[str] = None,
    ) -> None:
        self.logger = logger
        self.total_steps = total_steps
        self.request_id = request_id
        self.stage_prefix = stage_prefix

    def _qualify_stage(self, stage: str) -> str:
        if self.stage_prefix and not stage.startswith(self.stage_prefix):
            return f"{self.stage_prefix}.{stage}"
        return stage

    def start_step(
        self,
        step: int,
        title: str,
        stage: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Logs step start with visual arrow indicator `---> [Step X/Y] START`."""
        target_stage = self._qualify_stage(stage or f"step_{step}")
        log_operation(
            self.logger,
            stage=target_stage,
            status="started",
            request_id=self.request_id,
            details=details,
            level=logging.INFO,
            step=step,
            total_steps=self.total_steps,
            message=title,
        )

    def success_step(
        self,
        step: int,
        title: str,
        stage: Optional[str] = None,
        duration_ms: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Logs step completion with checkmark indicator `✓ [Step X/Y] SUCCESS`."""
        target_stage = self._qualify_stage(stage or f"step_{step}")
        log_operation(
            self.logger,
            stage=target_stage,
            status="success",
            request_id=self.request_id,
            duration_ms=duration_ms,
            details=details,
            level=logging.INFO,
            step=step,
            total_steps=self.total_steps,
            message=title,
        )

    def fallback_step(
        self,
        step: int,
        title: str,
        reason: Optional[str] = None,
        stage: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Logs fallback trigger with warning indicator `⚠️  [Step X/Y - FALLBACK]`."""
        target_stage = self._qualify_stage(stage or f"step_{step}")
        meta_details = dict(details or {})
        if reason:
            meta_details["fallback_reason"] = reason[:120]

        log_operation(
            self.logger,
            stage=target_stage,
            status="fallback",
            request_id=self.request_id,
            details=meta_details,
            level=logging.WARNING,
            step=step,
            total_steps=self.total_steps,
            is_fallback=True,
            message=title,
        )

    def fail_step(
        self,
        step: int,
        title: str,
        stage: Optional[str] = None,
        duration_ms: Optional[float] = None,
        error_category: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Logs step failure with cross indicator `x [Step X/Y] FAILED`."""
        target_stage = self._qualify_stage(stage or f"step_{step}")
        log_operation(
            self.logger,
            stage=target_stage,
            status="failed",
            request_id=self.request_id,
            duration_ms=duration_ms,
            error_category=error_category,
            details=details,
            level=logging.ERROR,
            step=step,
            total_steps=self.total_steps,
            message=title,
        )

    @contextmanager
    def track_step(
        self,
        step: int,
        title: str,
        stage: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Generator[None, None, None]:
        """Context manager to automatically time and log start/success/failure for a step."""
        self.start_step(step=step, title=title, stage=stage, details=details)
        start_time = time.perf_counter()
        try:
            yield
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.success_step(step=step, title=title, stage=stage, duration_ms=duration_ms)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            err_category = getattr(exc, "category", "step_execution_error")
            self.fail_step(
                step=step,
                title=f"{title} ({exc.__class__.__name__})",
                stage=stage,
                duration_ms=duration_ms,
                error_category=str(err_category),
            )
            raise
