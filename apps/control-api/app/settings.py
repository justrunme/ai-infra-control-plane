"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

try:
    from pydantic import Field
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):
        """Runtime configuration for the control API."""

        model_config = SettingsConfigDict(
            extra="ignore",
            populate_by_name=True,
        )

        database_url: str = Field(
            default="sqlite:///./data/control-plane.db",
            validation_alias="DATABASE_URL",
        )
        approval_ttl_seconds: int = Field(
            default=3600,
            validation_alias="APPROVAL_TTL_SECONDS",
        )
        probe_cache_ttl_seconds: int = Field(
            default=5,
            validation_alias="PROBE_CACHE_TTL_SECONDS",
        )
        http_trust_env: bool = Field(
            default=False,
            validation_alias="HTTP_TRUST_ENV",
        )
        ollama_base_url: str | None = Field(
            default=None,
            validation_alias="OLLAMA_BASE_URL",
        )
        vllm_base_url: str | None = Field(
            default=None,
            validation_alias="VLLM_BASE_URL",
        )
        governance_root: str | None = Field(
            default=None,
            validation_alias="GOVERNANCE_ROOT",
        )

except ImportError:  # pragma: no cover - exercised when pydantic-settings missing
    import os
    from dataclasses import dataclass

    def _env_bool(name: str, default: bool) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    def _env_int(name: str, default: int) -> int:
        raw = os.getenv(name)
        if raw is None or not raw.strip():
            return default
        return int(raw)

    def _env_optional(name: str) -> str | None:
        raw = os.getenv(name)
        if raw is None or not raw.strip():
            return None
        return raw.strip()

    @dataclass(frozen=True)
    class Settings:  # type: ignore[no-redef]
        """Runtime configuration for the control API."""

        database_url: str = "sqlite:///./data/control-plane.db"
        approval_ttl_seconds: int = 3600
        probe_cache_ttl_seconds: int = 5
        http_trust_env: bool = False
        ollama_base_url: str | None = None
        vllm_base_url: str | None = None
        governance_root: str | None = None

        @classmethod
        def from_env(cls) -> Settings:
            return cls(
                database_url=os.getenv(
                    "DATABASE_URL", "sqlite:///./data/control-plane.db"
                ),
                approval_ttl_seconds=_env_int("APPROVAL_TTL_SECONDS", 3600),
                probe_cache_ttl_seconds=_env_int("PROBE_CACHE_TTL_SECONDS", 5),
                http_trust_env=_env_bool("HTTP_TRUST_ENV", False),
                ollama_base_url=_env_optional("OLLAMA_BASE_URL"),
                vllm_base_url=_env_optional("VLLM_BASE_URL"),
                governance_root=_env_optional("GOVERNANCE_ROOT"),
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""
    if hasattr(Settings, "from_env"):
        return Settings.from_env()  # type: ignore[attr-defined]
    return Settings()  # type: ignore[call-arg]


def clear_settings_cache() -> None:
    """Drop cached settings (tests/ops)."""
    get_settings.cache_clear()
