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
