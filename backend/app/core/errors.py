"""Domain exceptions. Each carries a user-safe message; technical detail goes to logs only."""


class PayFlowError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, *, details: object | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(PayFlowError):
    status_code = 404
    code = "not_found"


class ConflictError(PayFlowError):
    status_code = 409
    code = "conflict"


class ValidationFailure(PayFlowError):
    status_code = 422
    code = "validation_error"


class UnsupportedFileError(PayFlowError):
    status_code = 400
    code = "invalid_file"


class FileTooLargeError(PayFlowError):
    status_code = 413
    code = "file_too_large"


class ProcessingError(PayFlowError):
    """Permanent technical failure of a stage — the run is marked FAILED (never REJECTED)."""

    status_code = 422
    code = "processing_failed"

    def __init__(self, message: str, *, category: str = "UNEXPECTED", details: object | None = None):
        super().__init__(message, details=details)
        self.category = category


class TransientError(PayFlowError):
    """Temporary failure — the caller should retry; no state is changed."""

    status_code = 503
    code = "temporarily_unavailable"

    def __init__(self, message: str, *, category: str = "TRANSIENT"):
        super().__init__(message)
        self.category = category

