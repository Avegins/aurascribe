"""Unit tests for AuraScribe Pydantic schemas (audio, transcript, and SOAP notes)."""

import pytest
from pydantic import ValidationError
from aurascribe.schemas.audio import AudioValidationInput, AudioValidationResult
from aurascribe.schemas.transcript import TranscriptMetadata, ValidatedTranscript
from aurascribe.schemas.soap import (
    SOAPNote,
    Subjective,
    Objective,
    Assessment,
    Plan,
    VitalSigns,
    Medication,
    DiagnosticTest,
)


class TestAudioSchemas:
    """Tests for AudioValidationInput and AudioValidationResult."""

    def test_valid_audio_input(self):
        data = AudioValidationInput(
            filename="consultation.webm",
            media_type="audio/webm",
            size_bytes=1024,
            language_hint="tl",
        )
        assert data.filename == "consultation.webm"
        assert data.media_type == "audio/webm"
        assert data.size_bytes == 1024
        assert data.language_hint == "tl"

    def test_valid_audio_codecs_mime(self):
        data = AudioValidationInput(
            filename="audio.webm",
            media_type="audio/webm;codecs=opus",
            size_bytes=512,
        )
        assert data.media_type == "audio/webm;codecs=opus"

    def test_invalid_mime_type(self):
        with pytest.raises(ValidationError) as exc:
            AudioValidationInput(
                filename="doc.pdf",
                media_type="application/pdf",
                size_bytes=1024,
            )
        assert "Unsupported audio MIME type" in str(exc.value)

    def test_invalid_file_extension(self):
        with pytest.raises(ValidationError) as exc:
            AudioValidationInput(
                filename="script.exe",
                media_type="audio/wav",
                size_bytes=1024,
            )
        assert "Unsupported file extension" in str(exc.value)

    def test_empty_audio_bytes(self):
        with pytest.raises(ValidationError) as exc:
            AudioValidationInput(
                filename="empty.wav",
                media_type="audio/wav",
                size_bytes=0,
            )
        assert "Audio payload cannot be empty" in str(exc.value)

    def test_too_small_audio_bytes(self):
        with pytest.raises(ValidationError) as exc:
            AudioValidationInput(
                filename="tiny.wav",
                media_type="audio/wav",
                size_bytes=10,
            )
        assert "Audio payload is too small" in str(exc.value)


class TestTranscriptSchemas:
    """Tests for ValidatedTranscript and TranscriptMetadata."""

    def test_valid_transcript(self):
        meta = TranscriptMetadata(model="whisper-1", detected_language="tl", duration_seconds=12.5)
        transcript = ValidatedTranscript(
            text="Masakit po ang ulo ko dok.",
            metadata=meta,
        )
        assert transcript.text == "Masakit po ang ulo ko dok."
        assert transcript.metadata.detected_language == "tl"

    def test_empty_transcript_fails(self):
        meta = TranscriptMetadata(model="whisper-1")
        with pytest.raises(ValidationError) as exc:
            ValidatedTranscript(text="   ", metadata=meta)
        assert "Transcript text cannot be empty" in str(exc.value)

    def test_too_short_transcript_fails(self):
        meta = TranscriptMetadata(model="whisper-1")
        with pytest.raises(ValidationError) as exc:
            ValidatedTranscript(text="hi", metadata=meta)
        assert "Transcript is too short" in str(exc.value)


class TestSOAPSchemas:
    """Tests for SOAPNote and sub-models."""

    def test_soap_note_defaults(self):
        note = SOAPNote()
        assert note.review_required is True
        assert note.validation_warnings == []
        assert note.subjective.chief_complaint is None
        assert note.subjective.symptoms == []
        assert note.objective.vital_signs is None
        assert note.objective.observations == []
        assert note.assessment.clinical_impression is None
        assert note.assessment.uncertainties == []
        assert note.plan.medications == []
        assert note.plan.tests == []

    def test_full_structured_soap_note(self):
        note = SOAPNote(
            subjective=Subjective(
                chief_complaint="Fever and sore throat for 3 days",
                symptoms=["Lagnat (fever)", "Masakit ang lalamunan (sore throat)"],
                history="Started 3 days ago, dry cough with no phlegm.",
                associated_symptoms=["Dry cough"],
            ),
            objective=Objective(
                vital_signs=VitalSigns(
                    blood_pressure="120/80 mmHg",
                    temperature="38.2 C",
                    heart_rate="82 bpm",
                ),
                examination_findings="Erythematous posterior pharyngeal wall.",
                observations=["Patient looks fatigued"],
            ),
            assessment=Assessment(
                clinical_impression="Acute Pharyngitis",
                supporting_evidence=["Fever 38.2 C", "Sore throat", "Pharyngeal erythema"],
                uncertainties=["Viral vs bacterial etiology pending CBC"],
            ),
            plan=Plan(
                medications=[
                    Medication(
                        name="Paracetamol",
                        dosage="500 mg",
                        frequency="Every 4 hours as needed for fever",
                        route="Oral",
                    )
                ],
                tests=[
                    DiagnosticTest(
                        name="Complete Blood Count (CBC)",
                        reason="Evaluate for leukocytosis / bacterial infection",
                    )
                ],
                treatment="Increase oral fluid intake, warm saline gargles.",
                follow_up="Return in 3 days if fever persists or symptoms worsen.",
            ),
            review_required=True,
            validation_warnings=["Pending lab confirmation"],
        )

        assert note.review_required is True
        assert len(note.plan.medications) == 1
        assert note.plan.medications[0].name == "Paracetamol"
        assert note.objective.vital_signs.temperature == "38.2 C"

        # Check JSON exportability
        dumped = note.model_dump()
        assert dumped["subjective"]["chief_complaint"] == "Fever and sore throat for 3 days"
        assert dumped["review_required"] is True


class TestSettingsValidation:
    """Tests for environment settings and multilingual/security configurations."""

    def test_settings_multilingual_and_ollama_defaults(self):
        from aurascribe.utils.config import Settings

        settings = Settings(
            AURASCRIBE_ENV="testing",
            AURASCRIBE_TARGET_LANGUAGE="Spanish",
            AURASCRIBE_DEFAULT_LANGUAGE_HINT="es",
            AURASCRIBE_TRANSCRIPTION_BASE_URL="http://philgood:8000/v1",
            OLLAMA_API_KEY="secret-token-123",
        )
        assert settings.target_language == "Spanish"
        assert settings.default_language_hint == "es"
        assert settings.transcription_base_url == "http://philgood:8000/v1"
        assert settings.ollama_api_key == "secret-token-123"

        # Verify secret redaction in __repr__
        repr_str = repr(settings)
        assert "secret-token-123" not in repr_str
        assert "***" in repr_str

    def test_production_validation_rules(self):
        from aurascribe.utils.config import Settings
        from aurascribe.utils.errors import ConfigurationError

        # In production with Ollama and custom transcription, OpenAI key is not required
        valid_prod = Settings(
            AURASCRIBE_ENV="production",
            AURASCRIBE_LLM_PROVIDER="ollama",
            AURASCRIBE_TRANSCRIPTION_PROVIDER="custom",
            AURASCRIBE_TRANSCRIPTION_BASE_URL="http://philgood:8000/v1",
        )
        # Should not raise
        valid_prod.validate_for_production()

        # In production with OpenAI LLM but no key, raises ConfigurationError
        invalid_prod = Settings(
            AURASCRIBE_ENV="production",
            AURASCRIBE_LLM_PROVIDER="openai",
            OPENAI_API_KEY=None,
        )
        with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
            invalid_prod.validate_for_production()


