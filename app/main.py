from argparse import ArgumentParser
from utils.fileIO import ConfigFile
from utils.prettyprint import PrettyPrinter_
from pyfiglet import print_figlet, FigletFont, Figlet, figlet_format
from enum import Enum
import container
from definition._ressource import RESSOURCES
from server import Application
from ressources.email_ressource import EmailTemplateRessource


class RunType(Enum):
    DEFAULT = "default"
    CUSTOM = "custom"
    ALL = "all"


########################################################################

parser = ArgumentParser(description="", epilog="")
parser.add_argument("--mode", type=str, default=RunType.DEFAULT.value,
                    choices=[RunType.DEFAULT.value, RunType.CUSTOM.value, RunType.ALL.value], help="")
parser.add_argument("--set-default", type=bool, default=True, help="")
args = parser.parse_args()

MODE = RunType(args.mode.lower())
SET_DEFAULT: bool = args.set_default

#APPLICATION_LIST: list[Application]= []

########################################################################
# TODO print the Python figlet




########################################################################





match MODE:
    case RunType.DEFAULT:
        # TODO: load from the properties
        ...
    case RunType.CUSTOM:
        # TODO: run the interactive mode
        ...
    case RunType.ALL:
        # TODO: put all ressource into a single application
        ...
        
    case _:
        pass

########################################################################


########################################################################

#for app in APPLICATION_LIST: app.start()

########################################################################

Application("adsd","adsad","fsd",ressources=[EmailTemplateRessource],middlewares=[]).start()