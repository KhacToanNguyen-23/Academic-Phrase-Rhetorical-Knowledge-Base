FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 PYTHONPATH=/app/src
COPY pyproject.toml ./
RUN uv sync --no-install-project --no-dev
COPY src ./src
RUN uv sync --no-dev
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "aprkb.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
