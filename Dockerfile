# The FastAPI app, built with uv. The React dashboard is already compiled into
# app/static/dashboard (committed), so this image serves the API and the UI
# from one process - no Node in the runtime image.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

# ffmpeg for pulling audio out of interview recordings; libgomp1 for the
# whisper runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# The uv binary, pinned to match the build-system requirement in pyproject.
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /bin/uv

WORKDIR /app

# Install dependencies first (cached unless the lock changes), then the app.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
