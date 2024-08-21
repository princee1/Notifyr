"""
# The `BaseResource` class initializes with a `container` attribute assigned from the `CONTAINER`
# instance imported from `container`.
"""
from typing import TypeVar
from services.assets import AssetService
from container import CONTAINER, Container
from app.interface._service import Service

T = TypeVar('T', bound=Service) 

class Ressource():
    def __init__(self) -> None:
        self.container: Container = CONTAINER

    def get(self, dep: type, scope=None, all=False) -> T:
        return self.container.get(dep, scope, all)

    def need(self, dep: type) -> T:
        return self.container.need(dep)

class AssetRessource(Ressource):
    """
    Ressource with a direct reference to the AssetService
    """
    def __init__(self) -> None:
        super().__init__()
        self.assetService:AssetService = self.container.get(AssetService)