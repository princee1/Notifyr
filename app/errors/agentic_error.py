from app.definition._error import BaseError


class AgenticError(BaseError):
    """Base exception for agentic service errors."""
    pass


class AgenticServerDisconnectedError(AgenticError):
    """Agentic HTTP server is disconnected."""
    pass


class AgenticStreamDoneError(AgenticError):
    """Agentic HTTP stream ended unexpectedly."""
    pass


class AgenticBadResponseError(AgenticError):
    """Agentic server returned a bad HTTP response."""
    pass


class AgenticGrpcIdleError(AgenticError):
    """Agentic gRPC channel is in idle state."""
    pass


class AgenticGrpcShutdownError(AgenticError):
    """Agentic gRPC channel is shutdown."""
    pass


class AgenticClientError(AgenticError):
    """Generic 4xx error returned by agentic HTTP gateway."""
    def __init__(self, body: dict | str | None, status: int):
        super().__init__(f"Agentic client error: {status}")
        self.body = body
        self.status = status


class AgenticUnauthorizedError(AgenticClientError):
    """401 Unauthorized from agentic."""
    pass


class AgenticNotFoundError(AgenticClientError):
    """404 Not Found from agentic."""
    pass


class AgenticGatewayError(AgenticError):
    """Generic 5xx error returned by agentic HTTP gateway."""
    def __init__(self, body: dict | str | None, status: int):
        super().__init__(f"Agentic gateway error: {status}")
        self.body = body
        self.status = status


class AgenticTimeoutError(AgenticError):
    """Timeout while contacting agentic HTTP server."""
    pass


class AgenticConnectionError(AgenticError):
    """Network error while contacting agentic HTTP server."""
    pass


class AgenticResponseValidationError(AgenticError):
    """Failed to parse JSON or unexpected response format from agentic."""
    def __init__(self, body: str | None, status: int | None = None):
        super().__init__("Agentic response validation error")
        self.body = body
        self.status = status
