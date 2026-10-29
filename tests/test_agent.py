"""Unit tests for ClinicalExtractionAgent, guardrails, and pipeline execution."""

from unittest.mock import MagicMock
import pytest
from pydantic_ai.models.test import TestModel
from aurascribe.agent.clinical_agent import ClinicalExtractionAgent, load_system_prompt
from aurascribe.agent.executor import ClinicalPipelineExecutor
from aurascribe.agent.state import PipelineStage
from aurascribe.schemas.soap import (
    SOAPNote,
    Subjective,
    Objective,
    Assessment,
    Plan,
    VitalSigns,
    Medication,
)
from aurascribe.schemas.transcript import TranscriptMetadata, ValidatedTranscript
from aurascribe.tools.transcription_tool import TranscriptionTool
from aurascribe.utils.config import Settings
from aurascribe.models.llm_client import get_llm_model, get_openai_model
from aurascribe.utils.errors import ClinicalExtractionError, ConfigurationError


class TestClinicalPrompt:
    """Verify prompt file integrity and versioning."""

    def test_load_system_prompt(self):
        prompt = load_system_prompt()
        assert "Version" in prompt
        assert "1.0.0" in prompt
        assert "Tagalog" in prompt
        assert "Taglish" in prompt
        assert "review_required" in prompt
        assert "Zero Fabrication Policy" in prompt
        assert "Multilingual" in prompt

    def test_load_system_prompt_with_target_language(self):
        prompt_spanish = load_system_prompt(target_language="Spanish")
        assert "Target Output Language Directive" in prompt_spanish
        assert "Spanish" in prompt_spanish

        prompt_english = load_system_prompt(target_language="English")
        assert "Target Output Language Directive" not in prompt_english


class TestClinicalGuardrails:
    """Tests for anti-hallucination and safety guardrails."""

    def test_review_required_always_forced_true(self):
        settings = Settings(AURASCRIBE_ENV="testing")
        agent = ClinicalExtractionAgent(settings=settings, model=TestModel())

        # Create note with review_required explicitly set to False
        note = SOAPNote(review_required=False)
        guarded = agent.apply_clinical_guardrails(note, transcript_text="test transcript")
        assert guarded.review_required is True

    def test_uncertainties_trigger_validation_warning(self):
        settings = Settings(AURASCRIBE_ENV="testing")
        agent = ClinicalExtractionAgent(settings=settings, model=TestModel())

        note = SOAPNote(
            assessment=Assessment(
                uncertainties=["Patient unsure whether pain began 3 or 5 days ago"]
            )
        )
        guarded = agent.apply_clinical_guardrails(note, transcript_text="sample transcript")
        assert len(guarded.validation_warnings) == 1
        assert "Patient unsure whether pain began" in guarded.validation_warnings[0]

    def test_impression_without_evidence_warning(self):
        settings = Settings(AURASCRIBE_ENV="testing")
        agent = ClinicalExtractionAgent(settings=settings, model=TestModel())

        note = SOAPNote(
            assessment=Assessment(
                clinical_impression="Dengue Fever",
                supporting_evidence=[],  # Missing supporting evidence
            )
        )
        guarded = agent.apply_clinical_guardrails(note, transcript_text="sample transcript")
        assert any("documented without explicit supporting evidence" in w for w in guarded.validation_warnings)

    def test_vitals_without_numbers_in_transcript_warning(self):
        settings = Settings(AURASCRIBE_ENV="testing")
        agent = ClinicalExtractionAgent(settings=settings, model=TestModel())

        note = SOAPNote(
            objective=Objective(
                vital_signs=VitalSigns(blood_pressure="120/80 mmHg", temperature="37.5 C")
            )
        )
        # Transcript with no numbers
        transcript_no_nums = "Patient says they feel sick and tired today."
        guarded = agent.apply_clinical_guardrails(note, transcript_text=transcript_no_nums)
        assert any("no numerical data found in transcript" in w for w in guarded.validation_warnings)


class TestClinicalAgentExecution:
    """Tests for agent extraction flow with TestModel."""

    def test_agent_extract_soap_sync(self):
        settings = Settings(AURASCRIBE_ENV="testing")

        expected_note = SOAPNote(
            subjective=Subjective(
                chief_complaint="Masakit ang tiyan (Abdominal pain)",
                symptoms=["Pananakit ng tiyan"],
            ),
            plan=Plan(
                medications=[Medication(name="Antacid", dosage="1 tablet")]
            ),
            review_required=True,
        )

        test_model = TestModel(custom_output_args=expected_note.model_dump())
        agent = ClinicalExtractionAgent(settings=settings, model=test_model)

        transcript = ValidatedTranscript(
            text="Masakit po ang tiyan ko dok simula kahapon.",
            metadata=TranscriptMetadata(model="whisper-1", detected_language="tl"),
        )

        res = agent.extract_soap_sync(transcript)
        assert res.review_required is True
        assert res.subjective.chief_complaint == "Masakit ang tiyan (Abdominal pain)"
        assert len(res.plan.medications) == 1
        assert res.plan.medications[0].name == "Antacid"

    def test_agent_run_failure_raises_clinical_extraction_error(self):
        settings = Settings(AURASCRIBE_ENV="testing")
        agent = ClinicalExtractionAgent(settings=settings, model=TestModel())

        # Mock agent.run_sync to raise an exception
        agent.agent.run_sync = MagicMock(side_effect=RuntimeError("Model unreachable"))

        transcript = ValidatedTranscript(
            text="Test transcript",
            metadata=TranscriptMetadata(model="whisper-1"),
        )

        with pytest.raises(ClinicalExtractionError) as exc:
            agent.extract_soap_sync(transcript)
        assert "failed to produce a valid SOAP note" in str(exc.value)


class TestClinicalPipelineExecutor:
    """End-to-end executor tests."""

    def test_executor_success(self, mock_audio_payload):
        settings = Settings(AURASCRIBE_ENV="testing")

        # Mock tool
        mock_tool = MagicMock(spec=TranscriptionTool)
        mock_transcript = ValidatedTranscript(
            text="Masakit ang lalamunan ko dok.",
            metadata=TranscriptMetadata(model="whisper-1", detected_language="tl"),
        )
        mock_tool.execute.return_value = mock_transcript

        # Mock agent
        mock_note = SOAPNote(
            subjective=Subjective(chief_complaint="Sore throat"),
            review_required=True,
        )
        test_model = TestModel(custom_output_args=mock_note.model_dump())
        agent = ClinicalExtractionAgent(settings=settings, model=test_model)

        executor = ClinicalPipelineExecutor(
            transcription_tool=mock_tool,
            extraction_agent=agent,
            settings=settings,
        )

        state = executor.process(
            audio_bytes=mock_audio_payload,
            filename="rec.webm",
            media_type="audio/webm",
        )

        assert state.stage == PipelineStage.COMPLETED
        assert state.is_success is True
        assert state.transcript.text == "Masakit ang lalamunan ko dok."
        assert state.soap_note.subjective.chief_complaint == "Sore throat"
        assert state.duration_ms is not None


class TestLLMClientProvider:
    """Verify provider initialization for OpenAI and Ollama."""

    def test_ollama_provider_initialization(self):
        settings = Settings(
            AURASCRIBE_ENV="testing",
            AURASCRIBE_LLM_PROVIDER="ollama",
            AURASCRIBE_LLM_MODEL="qwen3.5:9b-q8_0",
            OLLAMA_BASE_URL="http://philgood:11434/v1",
        )
        model = get_llm_model(settings=settings)
        assert model.model_name == "qwen3.5:9b-q8_0"
        assert model._provider.name == "ollama"
        assert "http://philgood:11434/v1" in model._provider.base_url

    def test_ollama_provider_normalizes_url(self):
        settings = Settings(
            AURASCRIBE_ENV="testing",
            AURASCRIBE_LLM_PROVIDER="ollama",
            AURASCRIBE_LLM_MODEL="gemma4:12b-it-q4_K_M",
            OLLAMA_BASE_URL="http://philgood:11434",
        )
        model = get_llm_model(settings=settings)
        assert model.model_name == "gemma4:12b-it-q4_K_M"
        assert "http://philgood:11434/v1" in model._provider.base_url

    def test_ollama_agent_initialization_without_openai_key(self):
        settings = Settings(
            AURASCRIBE_ENV="testing",
            AURASCRIBE_LLM_PROVIDER="ollama",
            AURASCRIBE_LLM_MODEL="qwen3.5:9b-q8_0",
            OLLAMA_BASE_URL="http://localhost:11434/v1",
        )
        agent = ClinicalExtractionAgent(settings=settings)
        assert agent.agent is not None

    def test_openai_missing_key_raises(self):
        settings = Settings(
            AURASCRIBE_ENV="testing",
            AURASCRIBE_LLM_PROVIDER="openai",
            OPENAI_API_KEY=None,
        )
        with pytest.raises(ConfigurationError, match="OPENAI_API_KEY must be configured"):
            get_llm_model(settings=settings)

    def test_llama_cpp_provider_initialization(self):
        settings = Settings(
            AURASCRIBE_ENV="testing",
            AURASCRIBE_LLM_PROVIDER="llama_cpp",
            AURASCRIBE_LLM_MODEL="qwen2.5-7b-instruct",
            LLAMA_CPP_BASE_URL="http://philgood:8080",
        )
        model = get_llm_model(settings=settings)
        assert model.model_name == "qwen2.5-7b-instruct"
        assert "http://philgood:8080/v1" in str(model._provider.client.base_url)

    def test_custom_provider_initialization(self):
        settings = Settings(
            AURASCRIBE_ENV="testing",
            AURASCRIBE_LLM_PROVIDER="custom",
            AURASCRIBE_LLM_MODEL="qwen-2.5-72b-instruct",
            AURASCRIBE_CUSTOM_BASE_URL="https://openrouter.ai/api/v1",
            AURASCRIBE_CUSTOM_API_KEY="sk-or-test",
        )
        model = get_llm_model(settings=settings)
        assert model.model_name == "qwen-2.5-72b-instruct"
        assert "openrouter.ai" in str(model._provider.client.base_url)

    def test_custom_provider_missing_base_url_raises(self):
        settings = Settings(
            AURASCRIBE_ENV="testing",
            AURASCRIBE_LLM_PROVIDER="custom",
            AURASCRIBE_CUSTOM_BASE_URL=None,
        )
        with pytest.raises(ConfigurationError, match="AURASCRIBE_CUSTOM_BASE_URL must be configured"):
            get_llm_model(settings=settings)

