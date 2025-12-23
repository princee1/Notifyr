from app.definition._error import BaseError


class MaxFileLimitError(BaseError):
    """Raised when the number of uploaded files exceeds the allowed limit."""
    pass


class FileTooLargeError(BaseError):
    """Raised when a single uploaded file exceeds the configured per-file size."""
    def __init__(self, filename: str, size: int, max_size: int):
        super().__init__(f"File '{filename}' is too large ({size} bytes). Max allowed is {max_size} bytes.")


class TotalFilesSizeExceededError(BaseError):
    """Raised when the combined size of uploaded files exceeds the allowed total."""
    def __init__(self, total: int, max_total: int):
        super().__init__(f"Total upload size {total} bytes exceeds limit of {max_total} bytes.")


class DuplicateFileNameError(BaseError):
    """Raised when multiple uploaded files share the same filename."""
    def __init__(self, filename: str):
        super().__init__(f"Duplicate filename detected: '{filename}'")


class InvalidExtensionError(BaseError):
    """Raised when a file's extension is not allowed."""
    def __init__(self, filename: str, allowed: list[str] | None):
        allowed_str = ",".join(allowed) if allowed else "<none>"
        super().__init__(f"File '{filename}' has an invalid extension. Allowed: {allowed_str}")

