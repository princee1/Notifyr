from argparse import ArgumentParser
from utils.fileIO import ConfigFile
from utils.prettyprint import PrettyPrinter_
from pyfiglet import print_figlet, FigletFont, Figlet, figlet_format
# import container
# from definition._ressource import RESSOURCES
# from server import Application
# from ressources.email_ressource import EmailTemplateRessource


########################################################################
########################################################################


parser = ArgumentParser(description="", epilog="")
parser.add_argument("--mode", type=str, default="last",
                    choices=["last", "custom", "all"], help="")
parser.add_argument("--default", type=bool, default=True, help="")
args = parser.parse_args()

MODE = args.mode
DEFAULT = args.default

config: ConfigFile = ConfigFile()

