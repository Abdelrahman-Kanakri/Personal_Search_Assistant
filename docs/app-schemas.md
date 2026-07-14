# `app/schemas/` — Shared Pydantic Models

Request/response models used by the API layer, plus the event schema shared
with the CLI's streaming protocol. No LangGraph/LangChain imports — this
layer is pure data shape.

## `models.py`

### `class Event(BaseModel)`

The wire representation of one `(kind, payload)` tuple from
`app.streaming.events`.

| Field | Type | Description |
| --- | --- | --- |
| `type` | `Literal["token", "interrupt", "done", "error"]` | The event kind. `"error"` is added by `app/api/routes.py`'s `_sse_format` for mid-stream failures — `stream_events`/`resume_graph` themselves only ever yield the other three. |
| `content` | `str \| None` | The token text, interrupt prompt, error message, or `None` for `"done"`. |

Serialized via `.model_dump_json()` into each SSE frame's `data:` field.

### `class StartRunRequest(BaseModel)`

Body for `POST /runs/`.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `topic` | `str` | required | The research topic to investigate. |
| `user_id` | `str` | `"default_user"` | Scopes saved findings in the store. |

### `class ResumeRunRequest(BaseModel)`

Body for `POST /runs/{thread_id}/resume`.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `response` | `str` | required | `'yes'`/`'no'`/`'edit'` for the approve/reject/edit prompt, or the replacement text when resuming after an `'edit'` choice. |
| `user_id` | `str` | `"default_user"` | Must match the `user_id` the run was originally started with — `resume_run` (`app/api/routes.py`) enforces this with a `403` if it doesn't, derived from checkpoint metadata rather than trusted from the request (see `app-api.md`). |

## `__init__.py`

Re-exports `Event`, `StartRunRequest`, `ResumeRunRequest`.
