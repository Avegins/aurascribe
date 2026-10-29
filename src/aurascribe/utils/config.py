"""Application configuration management for AuraScribe.

Provides strongly typed, validated settings with environment variable overrides
and explicit secret protection (no secrets printed in logs or string representations).
"""

import os
from functools import lru_cache
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from aurascribe.utils.errors import ConfigurationError


class Settings(BaseSettings):
    """AuraScribe runtime configuration."""

    # Environment
    aurascribe_env: str = Field(
        default="development",
        alias="AURASCRIBE_ENV",
        description="Application environment: development, testing, or production",
    )

    # Server Configuration
    host: str = Field(default="127.0.0.1", alias="HOST")
    port: int = Field(default=5000, alias="PORT")

    # API Keys & External Services
    openai_api_key: Optional[str] = Field(
        default=None,
        alias="OPENAI_API_KEY",
        description="OpenAI API key for transcription and LLM inference",
    )
    ollama_api_key: Optional[str] = Field(
        default=None,
        alias="OLLAMA_API_KEY",
        description="Optional API key or bearer token for secured Ollama endpoints",
    )

    # Models & Providers
    llm_provider: str = Field(
        default="openai",
        alias="AURASCRIBE_LLM_PROVIDER",
        description="LLM provider backend: 'openai', 'ollama', 'llama_cpp', or 'custom'",
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434/v1",
        alias="OLLAMA_BASE_URL",
        description="Base URL for Ollama service (e.g. http://localhost:11434/v1 or http://philgood:11434/v1)",
    )
    llama_cpp_base_url: str = Field(
        default="http://localhost:8080/v1",
        alias="LLAMA_CPP_BASE_URL",
        description="Base URL for llama.cpp server (e.g. http://localhost:8080/v1 or http://philgood:8080/v1)",
    )
    custom_base_url: Optional[str] = Field(
        default=None,
        alias="AURASCRIBE_CUSTOM_BASE_URL",
        description="Custom base URL for any OpenAI-compatible provider (e.g. OpenRouter, Groq, DashScope, vLLM)",
    )
    custom_api_key: Optional[str] = Field(
        default=None,
        alias="AURASCRIBE_CUSTOM_API_KEY",
        description="API key for custom OpenAI-compatible provider",
    )
    transcription_provider: str = Field(
        default="openai",
        alias="AURASCRIBE_TRANSCRIPTION_PROVIDER",
        description="Transcription provider: 'openai' or 'custom'",
    )
    transcription_base_url: Optional[str] = Field(
        default=None,
        alias="AURASCRIBE_TRANSCRIPTION_BASE_URL",
        description="Optional custom base URL for self-hosted Whisper transcription service",
    )
    transcription_model: str = Field(
        default="whisper-1",
        alias="AURASCRIBE_TRANSCRIPTION_MODEL",
        description="Audio transcription model identifier",
    )
    llm_model: str = Field(
        default="gpt-4o-mini",
        alias="AURASCRIBE_LLM_MODEL",
        description="Model identifier for clinical extraction agent",
    )

    # Multilingual & Translation Settings
    target_language: str = Field(
        default="English",
        alias="AURASCRIBE_TARGET_LANGUAGE",
        description="Standard target language for structured clinical SOAP notes (e.g. 'English', 'Spanish', 'Tagalog', 'Auto')",
    )
    default_language_hint: Optional[str] = Field(
        default=None,
        alias="AURASCRIBE_DEFAULT_LANGUAGE_HINT",
        description="Default audio language hint for speech transcription (e.g. 'tl', 'en', 'es', 'ceb', 'ja')",
    )
    transcription_prompt: str = Field(
        default=(
            "Clinical medical consultation in Tagalog, Taglish, and Bicolano (Central Bikol, Rinconada, Albay). "
            "Key terms: masakit (pain), ubo (cough), hilanat/lagnat (fever), alipunga, tyan (stomach), likod (back), "
            "nireseta (prescribed), mabalos (thank you), maray (good), dai (no), iyo (yes), tatlong araw (3 days), gamot (medicine)."
        ),
        alias="AURASCRIBE_TRANSCRIPTION_PROMPT",
        description="Regional vocabulary and dialect biasing prompt for Speech-to-Text (Tagalog, Taglish, Bicolano)",
    )

    # Limits & Constraints
    max_audio_size_bytes: int = Field(
        default=26_214_400,  # 25 MB
        alias="AURASCRIBE_MAX_AUDIO_SIZE_BYTES",
        description="Maximum allowed audio upload size in bytes",
    )
    request_timeout_seconds: float = Field(
        default=60.0,
        alias="AURASCRIBE_REQUEST_TIMEOUT_SECONDS",
        description="Timeout for external API calls in seconds",
    )
    agent_retry_limit: int = Field(
        default=2,
        alias="AURASCRIBE_AGENT_RETRY_LIMIT",
        description="Maximum retries for agent validation recovery",
    )

    # Logging & Observability
    log_level: str = Field(
        default="INFO",
        alias="AURASCRIBE_LOG_LEVEL",
        description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL",
    )

    # Clinical Prompt Version
    prompt_version: str = Field(
        default="1.0.0",
        alias="AURASCRIBE_PROMPT_VERSION",
        description="Version identifier for clinical extraction prompt",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("max_audio_size_bytes")
    @classmethod
    def validate_max_size(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("max_audio_size_bytes must be greater than 0")
        return v

    @field_validator("request_timeout_seconds")
    @classmethod
    def validate_timeout(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("request_timeout_seconds must be positive")
        return v

    @field_validator("agent_retry_limit")
    @classmethod
    def validate_retries(cls, v: int) -> int:
        if v < 0:
            raise ValueError("agent_retry_limit cannot be negative")
        return v

    def validate_for_production(self) -> None:
        """Fails fast if mandatory settings are missing for non-testing environments."""
        if self.aurascribe_env != "testing":
            if self.llm_provider.lower() == "openai" and not self.openai_api_key:
                raise ConfigurationError(
                    "OPENAI_API_KEY environment variable is required when AURASCRIBE_LLM_PROVIDER is 'openai'."
                )
            if (
                self.transcription_provider.lower() == "openai"
                and not self.openai_api_key
                and not self.transcription_base_url
            ):
                raise ConfigurationError(
                    "OPENAI_API_KEY or AURASCRIBE_TRANSCRIPTION_BASE_URL is required for transcription."
                )

    def __repr__(self) -> str:
        """Redacts sensitive credentials from string representations."""
        return (
            f"Settings(env={self.aurascribe_env!r}, "
            f"provider={self.llm_provider!r}, "
            f"llm_model={self.llm_model!r}, "
            f"ollama_base_url={self.ollama_base_url!r}, "
            f"target_language={self.target_language!r}, "
            f"transcription_model={self.transcription_model!r}, "
            f"transcription_provider={self.transcription_provider!r}, "
            f"max_audio_size_bytes={self.max_audio_size_bytes}, "
            f"prompt_version={self.prompt_version!r}, "
            f"openai_api_key={'***' if self.openai_api_key else None}, "
            f"ollama_api_key={'***' if self.ollama_api_key else None}, "
            f"custom_api_key={'***' if self.custom_api_key else None})"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Returns singleton settings instance with fail-fast validation."""
    try:
        settings = Settings()
        return settings
    except Exception as exc:
        raise ConfigurationError(f"Configuration initialization failed: {exc}") from exc

