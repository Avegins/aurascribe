"""Unit and integration tests for the Bicolano, Tagalog, and Taglish multilingual pipeline."""

import json
from unittest.mock import MagicMock, patch
import pytest

from aurascribe.pipeline.bicolano_pipeline import (
    preprocess_audio,
    transcribe_audio,
    clean_transcript,
    generate_soap_note,
    _heuristic_clean_transcript,
    BICOLANO_TAGLISH_PROMPT,
)
from aurascribe.utils.config import Settings
from aurascribe.utils.errors import ClinicalExtractionError, TranscriptionError


class TestAudioPreprocessing:
    """Test STEP 1: Audio noise reduction."""

    def test_preprocess_non_existent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            preprocess_audio("non_existent_path.wav")

    def test_preprocess_fallback_when_libraries_mocked(self, tmp_path):
        # Create dummy wav
        test_file = tmp_path / "sample.wav"
        test_file.write_bytes(b"RIFFdummydata")

        # Call preprocess_audio
        output_file = preprocess_audio(str(test_file))
        assert output_file is not None


class TestSTTTranscription:
    """Test STEP 2: STT with regional Bicolano/Taglish language hints."""

    def test_prompt_contains_bicolano_terms(self):
        assert "Bicolano" in BICOLANO_TAGLISH_PROMPT
        assert "hilanat" in BICOLANO_TAGLISH_PROMPT
        assert "mabalos" in BICOLANO_TAGLISH_PROMPT
        assert "dai" in BICOLANO_TAGLISH_PROMPT
        assert "iyo" in BICOLANO_TAGLISH_PROMPT

    def test_transcribe_audio_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            transcribe_audio("non_existent_file.wav")

    @patch("aurascribe.pipeline.bicolano_pipeline.OpenAI")
    def test_transcribe_audio_passes_prompt_and_temp_zero(self, mock_openai_cls, tmp_path):
        test_file = tmp_path / "consultation.wav"
        test_file.write_bytes(b"RIFF1234")

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Dok, masakit po an sakuyang tyan."
        mock_client.audio.transcriptions.create.return_value = mock_response
        mock_openai_cls.return_value = mock_client

        settings = Settings(
            AURASCRIBE_ENV="testing",
            OPENAI_API_KEY="test-key",
            AURASCRIBE_TRANSCRIPTION_MODEL="whisper-1",
        )

        res = transcribe_audio(str(test_file), settings=settings)
        assert res == "Dok, masakit po an sakuyang tyan."

        # Verify temperature is 0.0 and prompt is passed
        call_kwargs = mock_client.audio.transcriptions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.0
        assert "Bicolano" in call_kwargs["prompt"]


class TestTranscriptCleaningAgent:
    """Test STEP 3: LLM Transcript Cleaning Agent."""

    def test_heuristic_cleaning_fallback(self):
        raw = "dok masakat po an tyan ko tatmong araw na daa tabi"
        cleaned = _heuristic_clean_transcript(raw)
        # Verify misspellings fixed
        assert "masakit" in cleaned
        assert "tatlong" in cleaned
        # Verify fillers removed
        assert "po" not in cleaned
        assert "tabi" not in cleaned

    @patch("aurascribe.pipeline.bicolano_pipeline.OpenAI")
    def test_clean_transcript_llm_execution(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Doctor: Ano ang nararamdaman mo?\nPatient: Masakit ang tiyan ko."
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
        mock_openai_cls.return_value = mock_client

        settings = Settings(AURASCRIBE_ENV="testing", OPENAI_API_KEY="test-key")
        result = clean_transcript("dok masakat an tyan ko", settings=settings)
        assert "Doctor:" in result
        assert "Patient:" in result


class TestStructuredSOAPExtractionAgent:
    """Test STEP 4: Structured SOAP Note Extraction Agent."""

    def test_empty_transcript_raises(self):
        with pytest.raises(ClinicalExtractionError):
            generate_soap_note("")

    @patch("aurascribe.pipeline.bicolano_pipeline.OpenAI")
    def test_generate_soap_note_clean_json(self, mock_openai_cls):
        mock_client = MagicMock()
        expected_json = {
            "subjective": {
                "chief_complaint": "Abdominal pain (Masakit an tyan)",
                "history_of_present_illness": "3-day duration of epigastric pain",
                "current_medications": "None reported",
            },
            "objective": "Patient appears in mild distress",
            "assessment": "Acute Gastritis",
            "plan": "Prescribe antacids, diet modification",
        }
        mock_choice = MagicMock()
        # Test LLM response wrapped in markdown code fence
        mock_choice.message.content = f"```json\n{json.dumps(expected_json)}\n```"
        mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
        mock_openai_cls.return_value = mock_client

        settings = Settings(AURASCRIBE_ENV="testing", OPENAI_API_KEY="test-key")
        soap = generate_soap_note("Doctor: Ano po ang sakit? Patient: Masakit po an tyan ko.", settings=settings)

        assert soap["subjective"]["chief_complaint"] == "Abdominal pain (Masakit an tyan)"
        assert soap["assessment"] == "Acute Gastritis"
        assert "antacids" in soap["plan"]
        assert soap["objective"] == "Patient appears in mild distress"

