from definition import _service


@_service.ServiceClass
class SupportService(_service.Service):
    def __init__(self) -> None:
        super().__init__()
    pass


@_service.ServiceClass
class ChatService(_service.Service):
    def __init__(self) -> None:
        super().__init__()
    pass
