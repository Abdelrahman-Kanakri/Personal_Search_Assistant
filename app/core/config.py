"""Application settings loaded from ``.env`` via pydantic-settings.

Import the module-level ``settings`` singleton — never instantiate ``Settings``
directly elsewhere, as that would bypass the singleton and re-read the file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import os


class Settings(BaseSettings):
    """Typed application settings, loaded from ``.env`` at import time.

    Fields without a default (the API keys and model names) are *required* —
    pydantic raises a ``ValidationError`` on startup if any is missing from the
    environment, so the app fails loudly rather than running half-configured.
    Fields with a default (thresholds, chunk sizes, collection name) may be
    overridden via ``.env`` but are safe to omit. The module-level ``settings``
    singleton below is what the rest of the app imports.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    # ── LangSmith configurations ─────────────────────────────────────────────────────────────
    LANGSMITH_API_KEY: str = Field(..., env="LANGSMITH_API_KEY")
    LANGSMITH_ENDPOINT: str = Field(..., env="LANGSMITH_ENDPOINT")
    LANGSMITH_TRACING: bool = Field(..., env="LANGSMITH_TRACING")
    LANGSMITH_PROJECT: str = Field(..., env="LANGSMITH_PROJECT")

    # ── Mistral API & Models Names ─────────────────────────────────────────────────────────────

    MISTRAL_API_KEY: str = Field(..., env="MISTRAL_API_KEY")
    LARGE_MODEL_NAME: str = Field(..., env="LARGE_MODEL_NAME")
    MEDIUM_MODEL_NAME: str = Field(..., env="MEDIUM_MODEL_NAME")
    SMALL_MODEL_NAME: str = Field(..., env="SMALL_MODEL_NAME")
    MISTRAL_EMBEDDING_MODEL_NAME: str = Field(..., env="MISTRAL_EMBEDDING_MODEL_NAME")

    # ── Groq API & Models Names ─────────────────────────────────────────────────────────────
    GROQ_API_KEY: str = Field(..., env="GROQ_API_KEY")
    GROQ_MODEL_NAME: str = Field(..., env="GROQ_MODEL_NAME")

    # ── HF API & Model Names ─────────────────────────────────────────────────────────────
    HF_API_KEY: str = Field(..., env="HF_API_KEY")
    HF_EMBEDDING_MODEL_NAME: str = Field(..., env="HF_EMBEDDING_MODEL_NAME")

    # ── Google API & Model Names ─────────────────────────────────────────────────────────────
    GOOGLE_API_KEY: str = Field(..., env="GOOGLE_API_KEY")
    GOOGLE_MODEL_NAME: str = Field(..., env="GOOGLE_MODEL_NAME")

    # ── PostgresSQL db configurations ─────────────────────────────────────────────────────────────
    POSTGRES_PASSWORD: str = Field(..., env="POSTGRES_PASSWORD")
    POSTGRES_URI: str = Field(..., env="POSTGRES_URI")

    # Workaround for pyarrow/curl OpenSSL pkcs11-engine segfault on this host.
    # Forces Arrow's bundled OpenSSL to skip the system openssl.cnf (which loads
    # the broken engines-3/pkcs11.so). Picked up by scripts and the VS Code Python
    # extension (python.envFile). See Claude-Brain: rag-doc-qa-phase3-env-fixes.
    OPENSSL_CONF: str = Field(..., env="OPENSSL_CONF")

    # ── Tavily API Key ─────────────────────────────────────────────────────────────
    TAVILY_API_KEY: str = Field(..., env="TAVILY_API_KEY")

    # ── Sentry ─────────────────────────────────────────────────────────────
    # Optional: unset/empty leaves the SDK disabled (sentry_sdk.init(dsn=None)
    # is a documented no-op), so dev environments without a DSN work unchanged.
    SENTRY_DSN: str | None = Field(None, env="SENTRY_DSN")


settings = Settings()
os.environ["OPENSSL_CONF"] = settings.OPENSSL_CONF
os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
os.environ["LANGSMITH_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
os.environ["LANGSMITH_TRACING"] = str(settings.LANGSMITH_TRACING)
os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT
