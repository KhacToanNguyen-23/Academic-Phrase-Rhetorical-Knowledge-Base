"""FastAPI application factory with validated policies and request envelopes."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.exceptions import HTTPException as StarletteHTTPException

from aprkb.api.routes import api_router
from aprkb.core.config import settings
from aprkb.core.deps import get_db_session
from aprkb.policies.loader import load_policy_bundle

logger = logging.getLogger(__name__)


def _error_code(status_code: int) -> str:
    return {
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        422: "VALIDATION_ERROR",
    }.get(status_code, "HTTP_ERROR")


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", str(uuid4()))


def create_app(policy_dir: Path | str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.policy_bundle = load_policy_bundle(policy_dir)
        engine = create_async_engine(settings.database_url, pool_pre_ping=True)
        application.state.engine = engine
        application.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
        application.state.settings = settings
        application.state.local_demo_client_id = None
        application.state.local_demo_lock = asyncio.Lock()
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title="AP-RKB API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.include_router(api_router)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next: Any) -> Any:
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail
        message = detail if isinstance(detail, str) else "Request failed"
        details = detail if isinstance(detail, dict) else None
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": _error_code(exc.status_code),
                    "message": message,
                    "details": details,
                },
                "request_id": _request_id(request),
            },
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            {
                "loc": error.get("loc", ()),
                "msg": error.get("msg", "Invalid input"),
                "type": error.get("type"),
            }
            for error in exc.errors()
        ]
        request_id = _request_id(request)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": {"errors": errors},
                },
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id},
        )

    @app.exception_handler(Exception)
    async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = _request_id(request)
        logger.error(
            "Unhandled API exception request_id=%s exception_type=%s method=%s path=%s",
            request_id,
            type(exc).__name__,
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Internal server error",
                    "details": None,
                },
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id},
        )

    @app.get("/v1/health", tags=["system"])
    async def health(
        session: Annotated[AsyncSession, Depends(get_db_session)],
    ) -> dict[str, str]:
        try:
            await session.execute(text("SELECT 1"))
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database unavailable",
            ) from error
        return {"status": "ok", "database": "ok"}

    return app


app = create_app()
