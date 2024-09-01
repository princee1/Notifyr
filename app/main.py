########################################################################
from argparse import ArgumentParser
from utils.fileIO import ConfigFile,JSONFile
import pyfiglet
import time
from enum import Enum
from utils.prettyprint import PrettyPrinter_,clearscreen
########################################################################

class RunType(Enum):
    DEFAULT = "default"
    CUSTOM = "custom"
    ALL = "all"


parser = ArgumentParser(description="", epilog="")
parser.add_argument("--mode", type=str, default=RunType.DEFAULT.value,
                    choices=[RunType.DEFAULT.value, RunType.CUSTOM.value, RunType.ALL.value], help="")
parser.add_argument("--set-default", type=bool, default=True, help="")
args = parser.parse_args()

MODE = RunType(args.mode.lower())
SET_DEFAULT: bool = args.set_default


text='Communication - Service'
justify='left'

figlet = pyfiglet.Figlet(font='standard')
ascii_art = figlet.renderText(text)

if justify == 'center':
    ascii_art = '\n'.join(line.center(80) for line in ascii_art.splitlines())
elif justify == 'right':
    ascii_art = '\n'.join(line.rjust(80) for line in ascii_art.splitlines())

print(ascii_art)
time.sleep(10)
clearscreen()

########################################################################

import container
from definition._ressource import RESSOURCES
from server import Application
from ressources.email_ressource import EmailTemplateRessource
from ressources.sms_ressource import IncomingSMSRessource,OnGoingSMSRessource
from ressources.voice_ressource import IncomingCallRessources,OnGoingCallRessources
from ressources.fax_ressource import IngoingFaxRessource,OutgoingFaxRessource


########################################################################

APPLICATION_LIST: list[Application]= []

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
