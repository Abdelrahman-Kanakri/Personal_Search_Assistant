# `app/core/` — Settings and Logging

Foundational utilities imported by every other package: a typed settings
singleton loaded from `.env`, and structured JSON logging. Nothing here
depends on LangGraph or LangChain — this layer is pure infrastructure.

## `config.py`

Application settings loaded from `.env` via `pydantic-settings`. Import the
module-level `settings` singleton — never instantiate `Settings` directly
elsewhere, as that would bypass the singleton and re-read the file.

### `class Settings(BaseSettings)`

Typed application settings, loaded from `.env` at import time. Fields
without a default (all fields below) are *required* — pydantic raises a
`ValidationError` on startup if any is missing from the environment, so the
app fails loudly rather than running half-configured.

`model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")`

| Field | Type | Env var | Purpose |
| --- | --- | --- | --- |
| `LANGSMITH_API_KEY` | `str` | `LANGSMITH_API_KEY` | LangSmith tracing auth |
| `LANGSMITH_ENDPOINT` | `str` | `LANGSMITH_ENDPOINT` | LangSmith API endpoint |
| `LANGSMITH_TRACING` | `bool` | `LANGSMITH_TRACING` | Enable/disable tracing |
| `LANGSMITH_PROJECT` | `str` | `LANGSMITH_PROJECT` | LangSmith project name |
| `MISTRAL_API_KEY` | `str` | `MISTRAL_API_KEY` | Mistral API auth |
| `LARGE_MODEL_NAME` | `str` | `LARGE_MODEL_NAME` | Mistral large model id |
| `MEDIUM_MODEL_NAME` | `str` | `MEDIUM_MODEL_NAME` | Mistral medium model id — used by `researcher_node` |
| `SMALL_MODEL_NAME` | `str` | `SMALL_MODEL_NAME` | Mistral small model id |
| `MISTRAL_EMBEDDING_MODEL_NAME` | `str` | `MISTRAL_EMBEDDING_MODEL_NAME` | Mistral embedding model id |
| `GROQ_API_KEY` | `str` | `GROQ_API_KEY` | Groq API auth |
| `GROQ_MODEL_NAME` | `str` | `GROQ_MODEL_NAME` | Groq model id |
| `HF_API_KEY` | `str` | `HF_API_KEY` | Hugging Face API auth |
| `HF_EMBEDDING_MODEL_NAME` | `str` | `HF_EMBEDDING_MODEL_NAME` | HF embedding model id |
| `GOOGLE_API_KEY` | `str` | `GOOGLE_API_KEY` | Google API auth |
| `GOOGLE_MODEL_NAME` | `str` | `GOOGLE_MODEL_NAME` | Google model id |
| `POSTGRES_PASSWORD` | `str` | `POSTGRES_PASSWORD` | Postgres auth |
| `POSTGRES_URI` | `str` | `POSTGRES_URI` | Connection string for the LangGraph store + checkpointer |
| `OPENSSL_CONF` | `str` | `OPENSSL_CONF` | Workaround for a pyarrow/curl OpenSSL pkcs11-engine segfault on this host — forces Arrow's bundled OpenSSL to skip the system `openssl.cnf` |
| `TAVILY_API_KEY` | `str` | `TAVILY_API_KEY` | Tavily web-search API auth |

### `settings`

Module-level singleton: `settings = Settings()`. Constructed once at import
time. Importing this module also has the side effect of copying
`OPENSSL_CONF` and the four `LANGSMITH_*` values into `os.environ` — those
libraries (`pyarrow`, LangSmith's tracing client) only read env vars, not
`pydantic-settings` objects. `pydantic-settings` does **not** set
`os.environ` on its own, so the values have to be pushed in explicitly.

## `logging.py`

Structured JSON logging configuration using `structlog`, layered on top of
the stdlib `logging` module.

### `LOG_DIR`

Module-level constant, `Path("logs")`. Created (`mkdir(exist_ok=True)`) at
import time if it doesn't already exist.

### `_json_formatter`, `_root_handler`

Module-private. `_json_formatter` is a passthrough `logging.Formatter`
(`"%(message)s"`) — it does **not** convert records to JSON itself;
`structlog`'s `JSONRenderer` processor does that upstream, and the
formatter just passes the already-rendered string through. `_root_handler`
is a `FileHandler` writing to `logs/log.log`, registered as the sole
handler via `logging.basicConfig(level=logging.INFO, handlers=[_root_handler])`.

### `structlog.configure(...)` (module-level call)

Configures the global structlog pipeline, run once at import time:

1. `structlog.contextvars.merge_contextvars` — merges any bound context
   vars (useful for tagging logs within a request/run).
2. `structlog.processors.add_log_level` — adds the level (`"info"`,
   `"error"`, …) to the JSON payload.
3. `structlog.stdlib.add_logger_name` — adds the logger's name.
4. `structlog.processors.StackInfoRenderer()` + `structlog.dev.set_exc_info`
   — capture stack traces / exception info when present.
5. `structlog.processors.TimeStamper(fmt="iso", utc=True)` — ISO 8601 UTC
   timestamps (log-aggregator friendly, e.g. ELK/Splunk).
6. `structlog.processors.JSONRenderer()` — renders the final event as a
   JSON string.

`wrapper_class=structlog.stdlib.BoundLogger`, `logger_factory=structlog.stdlib.LoggerFactory()`,
`cache_logger_on_first_use=True`.

### `def get_logger(name: str | None = None) -> FilteringBoundLogger`

Get a JSON-structured logger, optionally isolated to its own file.

- **Args:**
  - `name`: logical channel, often `__name__`, but any string works. If
    given, this channel's logs go **only** to `logs/<name>.log`, never to
    the shared file — a dedicated `FileHandler` is lazily attached to the
    stdlib logger the first time that name is requested, and
    `propagate = False` is set to prevent the same record from also landing
    in the shared root log. If omitted, logs go to the shared
    `logs/log.log`.
- **Returns:** a `structlog` `BoundLogger` — calling `.info()` / `.error()`
  / etc. on it renders JSON per the pipeline above.

## `__init__.py`

Re-exports `settings` (from `config`) and `get_logger` (from `logging`) —
the two names the rest of the app imports: `from app.core import settings,
get_logger`.
