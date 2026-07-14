FROM python:3.14-slim

# Copying uv from its own published image avoids installing pip/curl into the
# runtime image just to bootstrap uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Dependencies first so the (expensive) sync layer stays cached across code
# changes that don't touch pyproject.toml/uv.lock.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY . .
RUN uv sync --frozen

# main() itself sets OPENSSL_CONF for the pyarrow/curl segfault workaround
# (see app/core/config.py) — nothing extra needed here for that.
EXPOSE 8000

# No --loop override: loop_factory() only special-cases Windows and the
# container is always Linux, so uvicorn's normal loop selection applies.
CMD ["uv", "run", "uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
