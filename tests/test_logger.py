"""Unit tests for the centralized logging module and PipelineStepLogger."""

import logging
import io
import pytest
from aurascribe.utils.logger import (
    PipelineStepLogger,
    configure_logging,
    get_logger,
    log_operation,
    STANDARD_LOG_FORMAT,
)


class TestPipelineStepLogger:
    """Verifies step progression markers, formatting, and fallback visibility."""

    @pytest.fixture
    def memory_logger(self):
        """Creates a dedicated logger with an in-memory stream for testing output formatting."""
        log_stream = io.StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setFormatter(logging.Formatter(STANDARD_LOG_FORMAT))
        test_logger = logging.getLogger("test.pipeline_logger")
        test_logger.setLevel(logging.INFO)
        test_logger.handlers = [handler]
        test_logger.propagate = False
        return test_logger, log_stream

    def test_step_progression_markers(self, memory_logger):
        logger, stream = memory_logger
        step_logger = PipelineStepLogger(logger, total_steps=6, request_id="req-123", stage_prefix="test_stage")

        # Step 1: Start
        step_logger.start_step(1, "Validating audio integrity", details={"size": 1024})
        # Step 1: Success
        step_logger.success_step(1, "Audio validated successfully", duration_ms=12.5)

        output = stream.getvalue()
        assert "---> [Step 1/6] START: Validating audio integrity" in output
        assert "✓ [Step 1/6] SUCCESS: Audio validated successfully" in output
        assert "request_id=req-123" in output
        assert "duration_ms=12.50" in output
        assert "size=1024" in output

    def test_fallback_indicator(self, memory_logger):
        logger, stream = memory_logger
        step_logger = PipelineStepLogger(logger, total_steps=6, request_id="req-456")

        step_logger.fallback_step(
            4,
            "Primary extraction schema rejected. Engaging structured fallback...",
            reason="Schema validation failed for model output",
        )

        output = stream.getvalue()
        assert "⚠️  [Step 4/6 - FALLBACK]: Primary extraction schema rejected" in output
        assert "fallback_reason=Schema validation failed" in output
        assert "request_id=req-456" in output

    def test_failure_marker(self, memory_logger):
        logger, stream = memory_logger
        step_logger = PipelineStepLogger(logger, total_steps=6, request_id="req-789")

        step_logger.fail_step(
            2,
            "Speech-to-Text service timed out",
            duration_ms=5000.0,
            error_category="timeout_error",
        )

        output = stream.getvalue()
        assert "x [Step 2/6] FAILED: Speech-to-Text service timed out" in output
        assert "error_category=timeout_error" in output
        assert "duration_ms=5000.00" in output

    def test_track_step_context_manager_success(self, memory_logger):
        logger, stream = memory_logger
        step_logger = PipelineStepLogger(logger, total_steps=4)

        with step_logger.track_step(2, "Running noise reduction"):
            pass

        output = stream.getvalue()
        assert "---> [Step 2/4] START: Running noise reduction" in output
        assert "✓ [Step 2/4] SUCCESS: Running noise reduction" in output
        assert "duration_ms=" in output

    def test_track_step_context_manager_exception(self, memory_logger):
        logger, stream = memory_logger
        step_logger = PipelineStepLogger(logger, total_steps=4)

        with pytest.raises(ValueError):
            with step_logger.track_step(3, "Processing data"):
                raise ValueError("Corrupt data block")

        output = stream.getvalue()
        assert "---> [Step 3/4] START: Processing data" in output
        assert "x [Step 3/4] FAILED: Processing data (ValueError)" in output

    def test_privacy_redaction_in_metadata(self, memory_logger):
        logger, stream = memory_logger
        step_logger = PipelineStepLogger(logger, total_steps=6)

        step_logger.start_step(
            1,
            "Safe operation check",
            details={
                "model": "whisper-large-v3",
                "api_key": "sk-secret12345",
                "transcript": "Doctor: Ano masakit? Patient: Likod ko po",
                "user_token": "bearer-secret-token",
            },
        )

        output = stream.getvalue()
        assert "model=whisper-large-v3" in output
        assert "sk-secret12345" not in output
        assert "Doctor: Ano masakit" not in output
        assert "bearer-secret-token" not in output

    def test_backward_compatibility_log_operation(self, memory_logger):
        logger, stream = memory_logger
        # Classic log_operation call without step
        log_operation(
            logger,
            stage="classic_stage",
            status="success",
            request_id="classic-001",
            duration_ms=45.67,
            details={"client": "browser"},
        )

        output = stream.getvalue()
        assert "stage=classic_stage | status=success | request_id=classic-001 | duration_ms=45.67 | client=browser" in output
        assert "[Step" not in output

