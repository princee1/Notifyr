from argparse import ArgumentParser
from utils.prettyprint import printJSON, show

parser = ArgumentParser(description="Communication Service Application")
parser.add_argument('--mode', '-m', choices=['file', 'create', 'edit'],
                    default='file', type=str, help='Running Mode')
parser.add_argument('--config', '-c', required=True,
                    type=str, help='Path to the config file')
args = parser.parse_args()

mode = args.mode
config_file = args.config

show(1)
########################################################################

from utils.fileIO import ConfigFile, JSONFile, exist
from server import AppParameter, Application, AppParameterKey
########################################################################


META_KEY = 'meta'
APPS_KEY = 'apps'

config_json_app = JSONFile(config_file)

# App1 = Application('Application 1 ', 'Direct communication using with a user using its email or phone number', 'djfkdfsdfds',
#                    [EmailTemplateRessource])
# App1.start()
########################################################################
