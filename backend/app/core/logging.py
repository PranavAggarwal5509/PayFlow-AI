"""Structured JSON logging with request / invoice / run correlation."""

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
invoice_id_var: ContextVar[str | None] = ContextVar("invoice_id", default=None)
run_id_var: ContextVar[str | None] = ContextVar("run_id", default=None)
stage_var: ContextVar[str | None] = ContextVar("stage", default=None)

_SENSITIVE_KEYS = ("api_key", "secret", "authorization", "password")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
            "invoice_id": invoice_id_var.get(),
            "run_id": run_id_var.get(),
            "stage": stage_var.get(),
        }
        category = getattr(record, "error_category", None)
        if category:
            payload["error_category"] = category
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps({k: v for k, v in payload.items() if v is not None})


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    logging.getLogger("httpx").setLevel(logging.WARNING)  # httpx URLs may carry API keys


def bind_context(
    invoice_id: object | None = None, run_id: object | None = None, stage: str | None = None
) -> None:
    if invoice_id is not None:
        invoice_id_var.set(str(invoice_id))
    if run_id is not None:
        run_id_var.set(str(run_id))
    if stage is not None:
        stage_var.set(stage)

