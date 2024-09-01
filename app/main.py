########################################################################
from argparse import ArgumentParser
from utils.fileIO import ConfigFile,JSONFile, exist
import pyfiglet
import time
from enum import Enum
from utils.prettyprint import PrettyPrinter_,clearscreen,printJSON,settitle
from utils.question import ask_question,SimpleInputHandler,NumberInputHandler,ConfirmInputHandler,CheckboxInputHandler
########################################################################

text='Communication - Service'
justify='left'

figlet = pyfiglet.Figlet(font='standard')
ascii_art = figlet.renderText(text)

if justify == 'center':
    ascii_art = '\n'.join(line.center(80) for line in ascii_art.splitlines())
elif justify == 'right':
    ascii_art = '\n'.join(line.rjust(80) for line in ascii_art.splitlines())

clearscreen()
settitle('Communication - Service')
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

App1 = Application('Application 1 ', 'Direct communication using with a user using its email or phone number','djfkdfsdfds',
                   [EmailTemplateRessource])
App1.start()
########################################################################
