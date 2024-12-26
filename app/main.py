########################################################################
import pyfiglet
import time
from enum import Enum
import sys
from utils.prettyprint import PrettyPrinter_, clearscreen, printJSON, settitle
from utils.question import ListInputHandler, ask_question, SimpleInputHandler, NumberInputHandler, ConfirmInputHandler, CheckboxInputHandler
########################################################################

text = 'Communication - Service'
justify = 'left'

figlet = pyfiglet.Figlet(font='standard')
ascii_art = figlet.renderText(text)

if justify == 'center':
    ascii_art = '\n'.join(line.center(80) for line in ascii_art.splitlines())
elif justify == 'right':
    ascii_art = '\n'.join(line.rjust(80) for line in ascii_art.splitlines())


def show(t=10, title='Communication - Service', t1=0):
    time.sleep(t1)
    clearscreen()
    settitle(title)
    print(ascii_art)
    time.sleep(t)
    # clearscreen()


show(1)

########################################################################
import container
from utils.fileIO import ConfigFile, JSONFile, exist
from argparse import ArgumentParser
from middleware import MIDDLEWARE
from definition._ressource import RESSOURCES
from ressources import *
from server import AppParameter, Application, AppParameterKey
########################################################################

ressources_key: set = set(RESSOURCES.keys())
middlewares_key = list(MIDDLEWARE.keys())

app_titles = []
available_ports = []
show(2)


def more_than_one(result): return len(result) >= 1
invalid_message = 'Should be at least 1 selection'
instruction = '(Press space to select, enter to continue)'


def createApps() -> AppParameter:

    _results = []

    apps_counts = ask_question([NumberInputHandler('Enter the number of applications: ',
                               name='apps_counts', default=1, min_allowed=1, max_allowed=10)])['apps_counts']
    show(1)
    print(f'Creating {apps_counts} applications')
    print()
    for i in range(int(apps_counts)):

        result = ask_question([SimpleInputHandler(f'Enter the title of application {i+1} : ', name='title', default=''),
                               SimpleInputHandler(
            f'Enter the summary of application {i} : ', name='summary', default=''),
            SimpleInputHandler(
            f'Enter the description of application {i} : ', name='description', default=''),
            CheckboxInputHandler(
            f'Select the ressources of application {i} that will be used once per application: ', choices=ressources_key, name='ressources', validate=more_than_one, invalid_message=invalid_message, instruction=instruction
        ),
            CheckboxInputHandler(
            f'Select the middlewares of application {i} : ', choices=middlewares_key, name='middlewares', validate=more_than_one, invalid_message=invalid_message, instruction=instruction),
            NumberInputHandler(
            f'Enter the port of application {i} : ', name='port', default=8080, min_allowed=4000, max_allowed=65535),
            SimpleInputHandler(
            f'Enter the log level of application {i} : ', name='log_level', default='debug'),
        ],)
        ressources_key.difference_update(result['ressources'])
        _results.append(result)
        show(1)
        printJSON(_results)
    
    return _results


result_apps = createApps()
exit(0)

META_KEY = 'meta'
APPS_KEY = 'apps'

parser = ArgumentParser(description="Communication Service Application")
parser.add_argument('--mode', '-m', choices=['file', 'create', 'edit'],
                    default='file', type=str, help='Running Mode')
parser.add_argument('--config', '-c', required=True,
                    type=str, help='Path to the config file')
args = parser.parse_args()

mode = args.mode
config_file = args.config

config_json_app = JSONFile(config_file)


App1 = Application('Application 1 ', 'Direct communication using with a user using its email or phone number', 'djfkdfsdfds',
                   [EmailTemplateRessource])
App1.start()
########################################################################
