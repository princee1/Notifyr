from app.definition._interface import Interface, IsInterface
from app.definition._service import BaseService

@IsInterface
class ProfileInterface(Interface):
    
    def __init__(self):
        super().__init__()
        self.profiles: dict[str,BaseService]= {}
    
    def check_capabilities(self):
        ...