"""Error classes for matrix-nio-mcp tools."""

from __future__ import annotations


class MatrixError(Exception):
    """Base for all Matrix tool errors."""

    code: str = "matrix_error"

    def to_dict(self) -> dict:
        return {"error": self.code, "message": str(self)}


class MatrixAuthError(MatrixError):
    code = "auth_error"


class MatrixPermissionError(MatrixError):
    code = "permission_error"


class MatrixRoomNotFound(MatrixError):
    code = "room_not_found"


class MatrixUserNotFound(MatrixError):
    code = "user_not_found"


class MatrixEncryptionError(MatrixError):
    code = "encryption_error"


class MatrixRateLimitError(MatrixError):
    code = "rate_limit"

    def __init__(self, message: str, retry_after_ms: int | None = None) -> None:
        super().__init__(message)
        self.retry_after_ms = retry_after_ms

    def to_dict(self) -> dict:
        d = super().to_dict()
        if self.retry_after_ms is not None:
            d["retry_after_ms"] = self.retry_after_ms
        return d


class MatrixNetworkError(MatrixError):
    code = "network_error"


class MatrixValidationError(MatrixError):
    code = "validation_error"


class MatrixRoomInUse(MatrixError):
    code = "room_in_use"


class MatrixFileTooLarge(MatrixError):
    code = "file_too_large"


def raise_for_nio_response(resp: object) -> None:
    """Raise a typed MatrixError for nio error responses."""
    import nio  # type: ignore[import-untyped]

    if isinstance(resp, nio.ErrorResponse):
        code = getattr(resp, "status_code", "") or ""
        msg = getattr(resp, "message", str(resp))
        if code == "M_FORBIDDEN":
            raise MatrixPermissionError(msg)
        if code in ("M_NOT_FOUND",):
            raise MatrixRoomNotFound(msg)
        if code == "M_UNKNOWN_TOKEN":
            raise MatrixAuthError(msg)
        if code in ("M_MISSING_TOKEN", "M_USER_DEACTIVATED"):
            raise MatrixAuthError(msg)
        if code == "M_USER_IN_USE":
            raise MatrixValidationError(msg)
        if code == "M_ROOM_IN_USE":
            raise MatrixRoomInUse(msg)
        if code == "M_TOO_LARGE":
            raise MatrixFileTooLarge(msg)
        if code in ("M_BAD_JSON", "M_NOT_JSON", "M_MISSING_PARAM", "M_INVALID_PARAM", "M_BAD_ALIAS"):
            raise MatrixValidationError(msg)
        if code in ("M_UNKNOWN", "M_UNRECOGNIZED"):
            raise MatrixError(msg)
        if code == "M_LIMIT_EXCEEDED":
            retry = getattr(resp, "retry_after_ms", None)
            raise MatrixRateLimitError(msg, retry)
        if code == "M_UNSUPPORTED_ROOM_VERSION":
            raise MatrixValidationError(msg)
        if code == "M_INCOMPATIBLE_ROOM_VERSION":
            raise MatrixValidationError(msg)
        if code == "M_SERVER_NOT_TRUSTED":
            raise MatrixNetworkError(msg)
        if code == "M_GUEST_ACCESS_FORBIDDEN":
            raise MatrixPermissionError(msg)
        if code in ("M_EXCLUSIVE",):
            raise MatrixPermissionError(msg)
        raise MatrixError(f"[{code}] {msg}")
