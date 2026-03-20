"""Unit tests for error classes."""

from matrix_nio_mcp.errors import (
    MatrixAuthError,
    MatrixEncryptionError,
    MatrixPermissionError,
    MatrixRateLimitError,
    MatrixRoomNotFound,
)


def test_error_to_dict():
    err = MatrixAuthError("token expired")
    d = err.to_dict()
    assert d["error"] == "auth_error"
    assert d["message"] == "token expired"


def test_rate_limit_includes_retry_after():
    err = MatrixRateLimitError("rate limited", retry_after_ms=5000)
    d = err.to_dict()
    assert d["error"] == "rate_limit"
    assert d["retry_after_ms"] == 5000


def test_rate_limit_no_retry_after():
    err = MatrixRateLimitError("rate limited")
    d = err.to_dict()
    assert "retry_after_ms" not in d


def test_error_codes():
    assert MatrixPermissionError.code == "permission_error"
    assert MatrixRoomNotFound.code == "room_not_found"
    assert MatrixEncryptionError.code == "encryption_error"


from matrix_nio_mcp.errors import (
    MatrixFileTooLarge,
    MatrixRoomInUse,
    MatrixValidationError,
)


def test_room_in_use_code():
    err = MatrixRoomInUse("alias taken")
    assert err.code == "room_in_use"
    assert err.to_dict()["error"] == "room_in_use"


def test_file_too_large_code():
    err = MatrixFileTooLarge("file exceeds limit")
    assert err.code == "file_too_large"


def test_raise_for_nio_room_in_use():
    """raise_for_nio_response maps M_ROOM_IN_USE → MatrixRoomInUse."""
    import pytest

    class FakeResp:
        status_code = "M_ROOM_IN_USE"
        message = "Room alias already in use"

    import nio  # type: ignore[import-untyped]

    # Monkey-patch ErrorResponse check
    original = nio.ErrorResponse
    try:
        nio.ErrorResponse = FakeResp  # type: ignore[attr-defined]
        from matrix_nio_mcp.errors import raise_for_nio_response

        with pytest.raises(MatrixRoomInUse):
            raise_for_nio_response(FakeResp())
    finally:
        nio.ErrorResponse = original


def test_raise_for_nio_too_large():
    """raise_for_nio_response maps M_TOO_LARGE → MatrixFileTooLarge."""
    import pytest

    class FakeResp:
        status_code = "M_TOO_LARGE"
        message = "File too large"

    import nio  # type: ignore[import-untyped]

    original = nio.ErrorResponse
    try:
        nio.ErrorResponse = FakeResp  # type: ignore[attr-defined]
        from matrix_nio_mcp.errors import raise_for_nio_response

        with pytest.raises(MatrixFileTooLarge):
            raise_for_nio_response(FakeResp())
    finally:
        nio.ErrorResponse = original
