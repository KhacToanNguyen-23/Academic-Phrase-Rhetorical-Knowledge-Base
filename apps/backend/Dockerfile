FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 PYTHONPATH=/app/src
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
RUN uv sync --locked --no-dev
ENV PATH="/app/.venv/bin:$PATH"
RUN groupadd --system aprkb && useradd --system --gid aprkb --home-dir /app --no-create-home aprkb \
    && mkdir -p /app/data/blobs \
    && chown -R aprkb:aprkb /app/data
USER aprkb
EXPOSE 8000
CMD ["uvicorn", "aprkb.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
