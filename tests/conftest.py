"""Pytest configuration and shared test fixtures for AuraScribe."""

import os
import pytest
from aurascribe.utils.config import Settings


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch):
    """Configures safe testing environment variables for every test."""
    monkeypatch.setenv("AURASCRIBE_ENV", "testing")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-mock-key-12345")
    monkeypatch.setenv("AURASCRIBE_TRANSCRIPTION_MODEL", "whisper-1")
    monkeypatch.setenv("AURASCRIBE_LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("AURASCRIBE_MAX_AUDIO_SIZE_BYTES", "10485760")  # 10 MB
    monkeypatch.setenv("AURASCRIBE_LOG_LEVEL", "DEBUG")
    from aurascribe.utils.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def mock_audio_payload():
    """Generates synthetic audio byte buffer representing a valid sample."""
    # 256 bytes of synthetic audio header/data
    return b"\x1aE\xdf\xa3" + b"\x00" * 252


@pytest.fixture
def mock_transcript_text():
    """Returns sample Tagalog/Taglish medical consultation dialogue."""
    return (
        "Doktor: Magandang umaga po, ano pong nararamdaman ninyo ngayon? "
        "Pasyente: Dok, three days na po akong nilalagnat at masakit ang lalamunan ko. "
        "Doktor: May ubo po ba o sipon? "
        "Pasyente: May konting ubo pero tuyo po, walang plema. "
        "Doktor: Sige, tingnan natin ang lalamunan mo. Medyo mamula-mula. Ang blood pressure mo ay 120/80, temperature ay 38.2 C. "
        "Magreseta ako ng Paracetamol 500mg every 4 hours for fever, at magpa-CBC tayo bukas."
    )
