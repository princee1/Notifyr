from app.definition._error import BaseError


class DeliveryError(BaseError):
    """Raised for retryable delivery failures."""
    pass

class NonRetryableError(BaseError):
    """Raised for non-retryable delivery failures."""
    pass
