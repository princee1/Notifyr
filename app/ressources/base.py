"""
# The `BaseResource` class initializes with a `container` attribute assigned from the `CONTAINER`
# instance imported from `app.container`.
"""

from app.container import CONTAINER, Container

class BaseRessource():
    def __init__(self) -> None:
        self.container: Container = CONTAINER
