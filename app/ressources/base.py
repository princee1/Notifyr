"""
# The `BaseResource` class initializes with a `container` attribute assigned from the `CONTAINER`
# instance imported from `container`.
"""
from typing import TypeVar
from container import CONTAINER, Container
from services._service import Service

T = TypeVar('T', bound=Service) 

class BaseRessource():
    def __init__(self) -> None:
        self.container: Container = CONTAINER

    def get(self, dep: type, scope=None, all=False) -> T:
        return self.container.get(dep, scope, all)

    def need(self, dep: type) -> T:
        return self.container.need(dep)
