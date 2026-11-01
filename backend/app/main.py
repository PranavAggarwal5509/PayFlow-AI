from contextlib import asynccontextmanager
import logging
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text

from app.api.routes import invoices, master_data, reviews, runs, system
from app.core.config import get_settings
from app.core.errors import PayFlowError, TransientError
from app.core.logging import configure_logging, request_id_var
from app.database.session import get_engine, get_session_factory
from app.services.recovery_service import recover_interrupted_runs

logger = logging.getLogger("payflow")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup phase: recover interrupted runs from previous process
    try:
        with get_session_factory()() as db:
            recovered = recover_interrupted_runs(db)
            if recovered > 0:
                logger.info("Startup recovery completed: recovered %d interrupted run(s)", recovered)
            else:
                logger.info("Startup recovery check: no interrupted runs found")
    except Exception as exc:
        logger.error("Startup recovery error (non-fatal, continuing startup): %s", exc)
    yield
    # Shutdown phase (if any cleanups needed)


def _error(status: int, code: str, message: str, details: object | None = None) -> JSONResponse:
    body = {"data": None, "meta": None, "error": {"code": code, "message": message, "details": details}}
    return JSONResponse(status_code=status, content=body)


def create_app() -> FastAPI:
    settings = get_settings()  # fails fast with a clear message if required env vars are missing
    configure_logging(settings.log_level)
    if not settings.gemini_api_key:
        logger.warning("GEMINI_API_KEY is not set: AI extraction will fail until it is configured")

    app = FastAPI(
        title="PayFlow AI API",
        version="1.0.0",
        description="Invoice processing and decision support. Public API under /api/v1.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_base_url, "http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request_id_var.set(rid)
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

    @app.exception_handler(PayFlowError)
    async def domain_error(_: Request, exc: PayFlowError) -> JSONResponse:
        if isinstance(exc, TransientError):
            logger.warning("Transient error: %s", exc.message)
        return _error(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return _error(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]}
            for e in exc.errors()
        ]
        return _error(422, "validation_error", "The request is invalid.", details)

    @app.exception_handler(Exception)
    async def unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error")  # stack trace stays in the log, never in the response
        return _error(500, "internal_error", "Something went wrong. Please try again.")

    @app.get("/health", tags=["System"])
    def health() -> dict[str, str]:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok"}

    for router in (
        invoices.router, runs.router, reviews.dashboard, reviews.router,
        master_data.vendors, master_data.purchase_orders, system.router,
    ):  # fmt: skip
        app.include_router(router, prefix="/api/v1")
    return app


app = create_app()
