"""Integration and route tests for Flask API endpoints."""

import io
from unittest.mock import MagicMock
import pytest
from aurascribe.agent.executor import ClinicalPipelineExecutor
from aurascribe.agent.state import ExecutionState, PipelineStage
from aurascribe.main import create_app
from aurascribe.schemas.soap import SOAPNote, Subjective
from aurascribe.schemas.transcript import TranscriptMetadata, ValidatedTranscript
from aurascribe.utils.config import Settings
from aurascribe.utils.errors import TranscriptionError


@pytest.fixture
def app():
    """Configures application with testing settings."""
    settings = Settings(
        AURASCRIBE_ENV="testing",
        OPENAI_API_KEY="sk-test-mock-key-12345",
        AURASCRIBE_MAX_AUDIO_SIZE_BYTES=10485760,
    )
    app = create_app(settings=settings)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Test client for HTTP requests."""
    return app.test_client()


class TestStaticAndHealthRoutes:
    """Test landing page and health endpoints."""

    def test_get_index(self, client):
        response = client.get("/")
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "AuraScribe" in html
        assert "Start Recording" in html
        assert "Mandatory Physician Verification Required" in html

    def test_get_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["environment"] == "testing"
        assert data["version"] == "0.1.0"


class TestApiProcessEndpoint:
    """Test /api/process validation, error handling, and end-to-end flow."""

    def test_process_missing_audio(self, client):
        response = client.post("/api/process", data={}, content_type="multipart/form-data")
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"]["category"] == "audio_validation_error"
        assert "Missing 'audio' file" in data["error"]["message"]

    def test_process_empty_audio(self, client):
        data = {
            "audio": (io.BytesIO(b""), "empty.wav", "audio/wav")
        }
        response = client.post("/api/process", data=data, content_type="multipart/form-data")
        assert response.status_code == 400
        res = response.get_json()
        assert res["error"]["category"] == "audio_validation_error"

    def test_process_invalid_file_extension(self, client):
        data = {
            "audio": (io.BytesIO(b"some fake content"), "document.txt", "text/plain")
        }
        response = client.post("/api/process", data=data, content_type="multipart/form-data")
        assert response.status_code == 400
        res = response.get_json()
        assert res["error"]["category"] == "audio_validation_error"

    def test_process_success_with_mocked_executor(self, app, client, mock_audio_payload):
        # Attach a mock executor to app
        mock_executor = MagicMock(spec=ClinicalPipelineExecutor)
        mock_transcript = ValidatedTranscript(
            text="Masakit po ang ulo ko dok.",
            metadata=TranscriptMetadata(model="whisper-1", detected_language="tl"),
        )
        mock_soap = SOAPNote(
            subjective=Subjective(chief_complaint="Headache"),
            review_required=True,
            validation_warnings=["Pending clinical correlation"],
        )
        mock_state = ExecutionState(
            request_id="test-req-123",
            stage=PipelineStage.COMPLETED,
            transcript=mock_transcript,
            soap_note=mock_soap,
            is_success=True,
            duration_ms=125.0,
        )
        mock_executor.process.return_value = mock_state
        app.pipeline_executor = mock_executor

        data = {
            "audio": (io.BytesIO(mock_audio_payload), "recording.webm", "audio/webm"),
            "language_hint": "tl",
        }
        response = client.post("/api/process", data=data, content_type="multipart/form-data")
        assert response.status_code == 200
        res = response.get_json()
        assert res["status"] == "success"
        assert res["request_id"] == "test-req-123"
        assert res["transcript"]["text"] == "Masakit po ang ulo ko dok."
        assert res["soap_note"]["subjective"]["chief_complaint"] == "Headache"
        assert res["review_required"] is True
        assert res["validation_warnings"] == ["Pending clinical correlation"]

    def test_process_upstream_transcription_error(self, app, client, mock_audio_payload):
        mock_executor = MagicMock(spec=ClinicalPipelineExecutor)
        mock_executor.process.side_effect = TranscriptionError(
            "Transcription rate limit reached.", status_code=429
        )
        app.pipeline_executor = mock_executor

        data = {
            "audio": (io.BytesIO(mock_audio_payload), "recording.webm", "audio/webm")
        }
        response = client.post("/api/process", data=data, content_type="multipart/form-data")
        assert response.status_code == 429
        res = response.get_json()
        assert res["error"]["category"] == "transcription_error"
        assert "rate limit" in res["error"]["message"].lower()

    def test_404_not_found(self, client):
        response = client.get("/non-existent-endpoint")
        assert response.status_code == 404
        res = response.get_json()
        assert res["error"]["category"] == "not_found"

    def test_405_method_not_allowed(self, client):
        response = client.get("/api/process")
        assert response.status_code == 405
        res = response.get_json()
        assert res["error"]["category"] == "method_not_allowed"


class TestTwoPhaseEndpoints:
    """Test /api/transcribe and /api/extract progressive endpoints."""

    def test_transcribe_missing_audio(self, client):
        response = client.post("/api/transcribe", data={}, content_type="multipart/form-data")
        assert response.status_code == 400
        res = response.get_json()
        assert res["error"]["category"] == "audio_validation_error"

    def test_transcribe_success(self, app, client, mock_audio_payload):
        mock_executor = MagicMock()
        mock_transcript = ValidatedTranscript(
            text="Sakit ang akong dughan dok.",
            metadata=TranscriptMetadata(model="whisper-1", detected_language="ceb"),
        )
        mock_executor.transcription_tool.execute.return_value = mock_transcript
        app.pipeline_executor = mock_executor

        data = {
            "audio": (io.BytesIO(mock_audio_payload), "recording.webm", "audio/webm")
        }
        response = client.post("/api/transcribe", data=data, content_type="multipart/form-data")
        assert response.status_code == 200
        res = response.get_json()
        assert res["status"] == "success"
        assert res["transcript"]["text"] == "Sakit ang akong dughan dok."
        assert res["transcript"]["metadata"]["detected_language"] == "ceb"

    def test_extract_missing_text(self, client):
        response = client.post("/api/extract", json={}, content_type="application/json")
        assert response.status_code == 400
        res = response.get_json()
        assert res["error"]["category"] == "transcript_validation_error"

    def test_extract_success(self, app, client):
        mock_executor = MagicMock()
        mock_soap = SOAPNote(
            subjective=Subjective(chief_complaint="Chest pain"),
            review_required=True,
        )
        mock_executor.extraction_agent.extract_soap_sync.return_value = mock_soap
        mock_executor.settings.transcription_model = "whisper-1"
        app.pipeline_executor = mock_executor

        payload = {"text": "Patient has chest pain.", "language": "en"}
        response = client.post("/api/extract", json=payload, content_type="application/json")
        assert response.status_code == 200
        res = response.get_json()
        assert res["status"] == "success"
        assert res["soap_note"]["subjective"]["chief_complaint"] == "Chest pain"
        assert res["review_required"] is True
        assert "cleaned_transcript" in res
        assert "form_schema" in res
        assert "extracted_data" in res


class TestDynamicFormEndpoints:
    """Test schema-driven form routes, v1 ingestion, and doctor sign-off."""

    def test_get_forms_catalog(self, client):
        response = client.get("/api/forms")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"
        form_ids = [f["form_id"] for f in data["forms"]]
        assert "soap_note" in form_ids

    def test_get_soap_note_schema(self, client):
        response = client.get("/api/forms/soap_note")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "success"
        schema = data["form_schema"]
        assert schema["form_id"] == "soap_note"
        assert len(schema["sections"]) == 4

        # Verify color themes for Indigo, Teal, Blue, Purple
        themes = [s["color_theme"] for s in schema["sections"]]
        assert "indigo" in themes
        assert "teal" in themes
        assert "blue" in themes
        assert "purple" in themes

    def test_v1_ingest_audio_missing_file(self, client):
        response = client.post("/api/v1/ingest-audio", data={}, content_type="multipart/form-data")
        assert response.status_code == 400
        res = response.get_json()
        assert res["error"]["category"] == "audio_validation_error"

    def test_v1_ingest_audio_success(self, app, client, mock_audio_payload):
        mock_executor = MagicMock()
        mock_transcript = ValidatedTranscript(
            text="Masakit po ang likod ko tatlong araw na.",
            metadata=TranscriptMetadata(model="whisper-1", detected_language="tl"),
        )
        mock_soap = SOAPNote(
            subjective=Subjective(chief_complaint="Masakit ang likod"),
            review_required=True,
        )
        mock_executor.transcription_tool.execute.return_value = mock_transcript
        mock_executor.extraction_agent.extract_soap_sync.return_value = mock_soap
        mock_executor.settings.transcription_model = "whisper-1"
        app.pipeline_executor = mock_executor

        data = {
            "audio": (io.BytesIO(mock_audio_payload), "recording.webm", "audio/webm"),
            "form_type": "soap_note",
            "language_hint": "tl",
        }
        response = client.post("/api/v1/ingest-audio", data=data, content_type="multipart/form-data")
        assert response.status_code == 200
        res = response.get_json()
        assert res["status"] == "success"
        assert res["form_type"] == "soap_note"
        assert "form_schema" in res
        assert "extracted_data" in res
        assert res["form_schema"]["form_id"] == "soap_note"

    def test_sign_off_clinical_note(self, client):
        payload = {
            "request_id": "test-req-12345",
            "form_type": "soap_note",
            "form_data": {
                "subjective": {
                    "chief_complaint": "Back pain",
                    "history_of_present_illness": "3 days duration",
                },
                "plan": {
                    "prescriptions": "Paracetamol 500mg TID",
                },
            },
            "physician_name": "Dr. Avegin Manaog, MD",
        }
        response = client.post("/api/sign-off", json=payload, content_type="application/json")
        assert response.status_code == 200
        res = response.get_json()
        assert res["status"] == "success"
        assert res["signed_off"] is True
        assert res["review_required"] is False
        assert "verified_at" in res
        assert res["physician"]["name"] == "Dr. Avegin Manaog, MD"



