# Rule: Python

- Use full **type hints** on every function signature. Prefer `pydantic` v2 models
  over loose dicts for structured data.
- Manage everything with **`uv`**: `uv add`, `uv run`, `uv sync`. Never `pip install`
  into the system; never edit `requirements.txt` by hand if a `pyproject.toml` exists.
- Format/lint with **ruff** (`ruff format`, `ruff check --fix`). Tests with **pytest**.
- No bare `except:`. Catch specific exceptions; let unexpected ones surface.
- Prefer pure functions and dependency injection so things stay testable.
- f-strings for formatting; `pathlib.Path` over `os.path`; `logging` over `print` in
  anything that isn't a quick script.
- When you add a non-stdlib import, mention the install command in your explanation.
