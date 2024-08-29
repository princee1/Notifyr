from server import FastAPIServer
from services.security_service import SecurityService
from definition._ressource import Ressource
from container import InjectInFunction, Get
from services.config_service import ConfigService
import multiprocessing
import threading
from argparse import ArgumentParser
from utils.prettyprint import PrettyPrinter_
from utils.helper import issubclass_of
from inspect import signature
from starlette.middleware.base import BaseHTTPMiddleware

REDIRECT_INFO_APP = ""
COMMUNICATION_APP = ""
ALL_APP = ""

# # NOTE I wanted to put the args parsing here
# parser = ArgumentParser(description="", epilog="")
# parser.add_argument("--m", "mode", type=str, default=REDIRECT_INFO_APP,
#                     choices=[REDIRECT_INFO_APP, COMMUNICATION_APP, ALL_APP], help="")
# MODE = parser.parse_args().mode


class Application(threading.Thread):

    def __init__(self, threadName, title: str, summary: str, description: str, ressources: list[type[Ressource]], middlewares: list[type[BaseHTTPMiddleware]]) -> None:
        super().__init__(None, None, threadName, ..., ..., daemon=None)
        self.configService: ConfigService = Get(ConfigService, None, False)
        self.app = FastAPIServer(title,summary, description, ressources, middlewares)

    def run(self) -> None:
        self.app.start()
