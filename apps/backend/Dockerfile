# syntax=docker/dockerfile:1
#
# One image, two commands: API (default CMD) and worker (`python -m aprkb.worker.runner`).
# Deployment must run both from the same digest; only the container command differs.
# Base images are pinned by digest for build provenance, not claimed cross-platform
# bit-for-bit reproducibility. Update pins only through a reviewed dependency PR that
# rebuilds, scans, and runs both entrypoint smokes (see doc/runbooks/ci.md).

FROM python:3.12-slim@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30 AS build
COPY --from=ghcr.io/astral-sh/uv@sha256:0ac957607303916420297a4c9c213bb33fbd3c888f9cd7f4f7273596ebf42b85 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_PROJECT_ENVIRONMENT=/app/.venv

# Install locked, non-dev dependencies before copying source so dependency layers
# only rebuild when pyproject.toml/uv.lock change.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

COPY src ./src
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations
RUN uv sync --locked --no-dev

FROM python:3.12-slim@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30 AS runtime
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH="/app/src" PYTHONUNBUFFERED=1

# Non-root runtime user; no shell, no home-directory writes needed beyond /app.
RUN groupadd --system aprkb \
  && useradd --system --gid aprkb --home-dir /app --shell /usr/sbin/nologin aprkb

COPY --from=build --chown=aprkb:aprkb /app /app

# Safe release metadata only: the commit this image was built from. Never a
# self-asserted image digest; deployment verification compares the registry-resolved
# digest against what each workload is actually running.
ARG GIT_COMMIT_SHA=unknown
ENV BUILD_COMMIT_SHA=${GIT_COMMIT_SHA}

USER aprkb
EXPOSE 8000
CMD ["uvicorn", "aprkb.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
