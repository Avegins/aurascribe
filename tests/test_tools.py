"""Unit tests for TranscriptionClient and TranscriptionTool with mocked OpenAI interactions."""

from unittest.mock import MagicMock
import pytest
from openai import (
    AuthenticationError,
    BadRequestError,
    RateLimitError,
    APITimeoutError,
)
from aurascribe.models.transcription_client import TranscriptionClient
from aurascribe.tools.transcription_tool import TranscriptionTool
from aurascribe.utils.config import Settings
from aurascribe.utils.errors import (
    AudioValidationError,
    TranscriptionError,
    TranscriptValidationError,
)


class TestTranscriptionTool:
    """Tests for TranscriptionTool validation and execution."""

    def test_audio_validation_success(self, mock_audio_payload):
        settings = Settings(
            AURASCRIBE_ENV="testing",
            OPENAI_API_KEY="sk-test",
            AURASCRIBE_MAX_AUDIO_SIZE_BYTES=10000,
        )
        mock_client = MagicMock(spec=TranscriptionClient)
        tool = TranscriptionTool(client=mock_client, settings=settings)

        res = tool.validate_audio(
            audio_bytes=mock_audio_payload,
            filename="consultation.webm",
            media_type="audio/webm",
        )
        assert res.is_valid is True
        assert res.filename == "consultation.webm"
        assert res.size_bytes == len(mock_audio_payload)

    def test_audio_validation_oversized(self):
        settings = Settings(
            AURASCRIBE_ENV="testing",
            OPENAI_API_KEY="sk-test",
            AURASCRIBE_MAX_AUDIO_SIZE_BYTES=100,  # Strict limit for test
        )
        mock_client = MagicMock(spec=TranscriptionClient)
        tool = TranscriptionTool(client=mock_client, settings=settings)

        oversized_bytes = b"\x00" * 200
        with pytest.raises(AudioValidationError) as exc:
            tool.validate_audio(
                audio_bytes=oversized_bytes,
                filename="sample.wav",
                media_type="audio/wav",
            )
        assert "exceeds maximum configured limit" in str(exc.value)

    def test_execute_success(self, mock_audio_payload):
        settings = Settings(AURASCRIBE_ENV="testing", OPENAI_API_KEY="sk-test")
        mock_client = MagicMock(spec=TranscriptionClient)

        mock_transcript = MagicMock()
        mock_transcript.text = "Masakit po ang lalamunan ko dok."
        mock_transcript.metadata.model = "whisper-1"
        mock_client.transcribe.return_value = mock_transcript

        tool = TranscriptionTool(client=mock_client, settings=settings)
        result = tool.execute(
            audio_bytes=mock_audio_payload,
            filename="rec.webm",
            media_type="audio/webm",
        )

        assert result.text == "Masakit po ang lalamunan ko dok."
        mock_client.transcribe.assert_called_once()


class TestTranscriptionClientErrors:
    """Tests for external OpenAI API exception mappings."""

    def test_transcribe_auth_error(self, mock_audio_payload):
        mock_openai = MagicMock()
        mock_openai.audio.transcriptions.create.side_effect = AuthenticationError(
            message="Invalid API key",
            response=MagicMock(status_code=401),
            body=None,
        )

        settings = Settings(AURASCRIBE_ENV="testing", OPENAI_API_KEY="sk-test")
        client = TranscriptionClient(settings=settings, client=mock_openai)

        with pytest.raises(TranscriptionError) as exc:
            client.transcribe(
                audio_bytes=mock_audio_payload,
                filename="rec.webm",
                media_type="audio/webm",
            )
        assert exc.value.status_code == 502
        assert "Upstream transcription authentication failed" in exc.value.message

    def test_transcribe_rate_limit(self, mock_audio_payload):
        mock_openai = MagicMock()
        mock_openai.audio.transcriptions.create.side_effect = RateLimitError(
            message="Rate limit exceeded",
            response=MagicMock(status_code=429),
            body=None,
        )

        settings = Settings(AURASCRIBE_ENV="testing", OPENAI_API_KEY="sk-test")
        client = TranscriptionClient(settings=settings, client=mock_openai)

        with pytest.raises(TranscriptionError) as exc:
            client.transcribe(
                audio_bytes=mock_audio_payload,
                filename="rec.webm",
                media_type="audio/webm",
            )
        assert exc.value.status_code == 429
        assert "rate limit exceeded" in exc.value.message.lower()

    def test_transcribe_timeout(self, mock_audio_payload):
        mock_openai = MagicMock()
        mock_openai.audio.transcriptions.create.side_effect = APITimeoutError(
            request=MagicMock()
        )

        settings = Settings(AURASCRIBE_ENV="testing", OPENAI_API_KEY="sk-test")
        client = TranscriptionClient(settings=settings, client=mock_openai)

        with pytest.raises(TranscriptionError) as exc:
            client.transcribe(
                audio_bytes=mock_audio_payload,
                filename="rec.webm",
                media_type="audio/webm",
            )
        assert exc.value.status_code == 504
        assert "timed out" in exc.value.message.lower()

    def test_transcribe_bad_request(self, mock_audio_payload):
        mock_openai = MagicMock()
        mock_openai.audio.transcriptions.create.side_effect = BadRequestError(
            message="Corrupt audio file header",
            response=MagicMock(status_code=400),
            body=None,
        )

        settings = Settings(AURASCRIBE_ENV="testing", OPENAI_API_KEY="sk-test")
        client = TranscriptionClient(settings=settings, client=mock_openai)

        with pytest.raises(TranscriptionError) as exc:
            client.transcribe(
                audio_bytes=mock_audio_payload,
                filename="rec.webm",
                media_type="audio/webm",
            )
        assert exc.value.status_code == 400
        assert "rejected" in exc.value.message.lower()

