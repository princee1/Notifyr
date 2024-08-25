from services.security import SecurityService
from definition._ressource import Ressource
from container import CONTAINER, InjectInFunction
from services.config import ConfigService
import multiprocessing
import threading
from argparse import ArgumentParser
from utils.prettyprint import PrettyPrinter_
from utils.helper import issubclass_of
from inspect import signature

REDIRECT_INFO_APP = ""
COMMUNICATION_APP = ""
ALL_APP = ""

# # NOTE I wanted to put the args parsing here
# parser = ArgumentParser(description="", epilog="")
# parser.add_argument("--m", "mode", type=str, default=REDIRECT_INFO_APP,
#                     choices=[REDIRECT_INFO_APP, COMMUNICATION_APP, ALL_APP], help="")
# MODE = parser.parse_args().mode


@InjectInFunction
def SecurityMiddleWare(securityService:SecurityService):
    pass


class Application():
    def __init__(self,ressources:list[type[Ressource]]):
        self.configService: ConfigService = CONTAINER.get(ConfigService)
    pass

    def buildRessources(self):
        pass

