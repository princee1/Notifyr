"""
# The `BaseResource` class initializes with a `container` attribute assigned from the `CONTAINER`
# instance imported from `container`.
"""
from typing import TypeVar
from services.assets import AssetService
from container import CONTAINER, Container
from app.definition._service import Service
from fastapi import APIRouter,HTTPException
from implements import Interface

T = TypeVar('T', bound=Service) 

class Ressource():
    def __init__(self,prefix) -> None:
        self.container: Container = CONTAINER
        self.router = APIRouter(prefix)

    def get(self, dep: type, scope=None, all=False) -> T:
        return self.container.get(dep, scope, all)

    def need(self, dep: type) -> T:
        return self.container.need(dep)
    
    def on_startup(self):
        pass

    def on_shutdown(self):
        pass

    def on_event(self):
        pass
    
class AssetRessource(Ressource):
    """
    Ressource with a direct reference to the AssetService
    """
    def __init__(self,prefix) -> None:
        super().__init__(prefix)
        self.assetService:AssetService = self.container.get(AssetService)