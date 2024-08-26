
from typing import overload


class Interface:

    def __init_subclass__(cls) -> None:
        if "Interface" in cls.__name__:
            return
        # compare attributes and methods

