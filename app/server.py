"""
Contains the FastAPI app
"""

from definition._ressource import Ressource


class Server():
    
    def __init__(self,ressources:list[type[Ressource]]) -> None:
        pass

    def start(self):
        pass

    def stop(self):
        pass
    pass