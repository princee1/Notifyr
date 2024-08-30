from utils.prettyprint import PrettyPrinter_
from pyfiglet import print_figlet,FigletFont,Figlet, figlet_format
import container
from server import Application
from ressources.email_ressource import EmailTemplateRessource


# # NOTE I wanted to put the args parsing here
# parser = ArgumentParser(description="", epilog="")
# parser.add_argument("--m", "mode", type=str, default=REDIRECT_INFO_APP,
#                     choices=[REDIRECT_INFO_APP, COMMUNICATION_APP, ALL_APP], help="")
# MODE = parser.parse_args().mode


Application("Email Temaplte","Email Temaplte","Email Templae", [EmailTemplateRessource],[]).start()