from app.definition import _service


@_service.ServiceClass
class RateLimiterService(_service.Service): # TODO 
    def __init__(self) -> None:
        super().__init__()
    pass


@_service.ServiceClass
class PriorityQueueService(_service.Service):
    def __init__(self) -> None:
        super().__init__()
    pass
