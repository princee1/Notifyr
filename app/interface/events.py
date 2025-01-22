

from app.definition._interface import Interface,IsInterface

@IsInterface
class EventInterface(Interface):

    def on_startup(self):
        pass

    def on_shutdown(self):
        pass
    