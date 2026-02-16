"""
Production-ready multi-agent API using ADK (Agent Development Kit).

All user communication goes through the Supervisor; sub-agents (Weather, Finance) never interact with the user directly.
"""

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root so GOOGLE_API_KEY is available to ADK/genai
load_dotenv(Path(__file__).resolve().parent / ".env")

# Use certifi's CA bundle for SSL (fixes CERTIFICATE_VERIFY_FAILED with Atlas on macOS;
# mem0's PyMongo client doesn't accept tlsCAFile, so we set the default env).
import os
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except ImportError:
    pass

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import get_settings
from app.exceptions import AppException
from app.memory.memory_manager import MemoryManager

settings = get_settings()
# Ensure Gemini/ADK can see the API key
if settings.google_api_key:
    import os
    os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
    os.environ.setdefault("GOOGLE_GENAI_API_KEY", settings.google_api_key)

# File logging: write to logs/app.log (and console) when LOG_FILE is set
_log_file_handle = None
if getattr(settings, "log_file", None) and settings.log_file.strip():
    log_path = Path(__file__).resolve().parent / settings.log_file.strip()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    _log_file_handle = open(log_path, "a", encoding="utf-8")

class _DualOutputLogger:
    """Writes log lines to both stdout and the log file (if open)."""
    def msg(self, message: str) -> None:
        print(message, flush=True)
        if _log_file_handle:
            _log_file_handle.write(message + "\n")
            _log_file_handle.flush()

    def err(self, message: str) -> None:
        print(message, file=sys.stderr, flush=True)
        if _log_file_handle:
            _log_file_handle.write(message + "\n")
            _log_file_handle.flush()

    def debug(self, message: str) -> None:
        self.msg(message)

    def info(self, message: str) -> None:
        self.msg(message)

    def warning(self, message: str) -> None:
        self.err(message)

    def error(self, message: str) -> None:
        self.err(message)

    def critical(self, message: str) -> None:
        self.err(message)

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        getattr(logging, settings.log_level.upper(), logging.INFO),
    ),
    logger_factory=lambda *args: _DualOutputLogger(),
)
log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Connect memory on startup, close on shutdown."""
    memory = MemoryManager()
    try:
        await memory.connect()
        log.info("memory_connected")
    except Exception as e:
        log.warning("memory_connect_failed", error=str(e))
    yield
    await memory.close()
    log.info("memory_closed")
    if _log_file_handle:
        try:
            _log_file_handle.close()
        except OSError:
            pass


app = FastAPI(
    title="ADK Multi-Agent API",
    description="Supervisor + Weather + Finance agents with memory (Redis + MongoDB)",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Log request and response status."""
    log.info("request_start", method=request.method, path=request.url.path)
    response = await call_next(request)
    log.info("request_end", status_code=response.status_code)
    return response


app.include_router(router, prefix="", tags=["chat", "memory", "health"])


@app.exception_handler(AppException)
async def app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
    """Return consistent JSON for application exceptions (memory, agent, etc.)."""
    log.warning(
        "app_exception",
        status_code=exc.status_code,
        detail=exc.detail,
        internal_message=getattr(exc, "internal_message", None),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return 422 with validation error details."""
    log.warning("validation_error", errors=exc.errors())
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "message": "Validation error"},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions; avoid leaking internals."""
    log.exception("unhandled_exception", path=request.url.path, error=str(exc))
    err_str = str(exc).lower()
    if "429" in err_str or "resource_exhausted" in err_str or "quota exceeded" in err_str:
        status_code, detail = 429, (
            "Service is temporarily at capacity due to rate limits. "
            "Please wait a minute and try again, or check your API quota at https://ai.google.dev/gemini-api/docs/rate-limits."
        )
    else:
        status_code, detail = 500, "An unexpected error occurred. Please try again later."
    return JSONResponse(status_code=status_code, content={"detail": detail})


# Optional: OpenTelemetry tracing (set OTEL_ENABLED=true and configure exporter)
if getattr(settings, "otel_enabled", False):
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except ImportError:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=True,
    )
