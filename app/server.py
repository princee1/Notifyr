"""
Contains the FastAPI app
"""

from definition._ressource import Ressource,MiddleWare


class FastAPIServer():
    
    def __init__(self,ressources:list[type[Ressource]],middlewares:list[type[MiddleWare]]) -> None:
        self.ressources = ressources
        self.middlewares = middlewares
        pass

    def start(self):
        pass

    def stop(self):
        pass

    def buildRessources(self):
        pass
        
    pass