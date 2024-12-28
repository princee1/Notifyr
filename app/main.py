from server import AppParameter, start_applications, createApps, editApps, RESSOURCES, MIDDLEWARE
from utils.fileIO import ConfigFile, JSONFile, exist, inputFilePath
from argparse import ArgumentParser
from utils.prettyprint import printJSON, show, PrettyPrinter_
from enum import Enum


class RunMode(Enum):
    FILE = "file"
    CREATE = "create"
    EDIT = "edit"


parser = ArgumentParser(description="Communication Service Application")
parser.add_argument('--mode', '-m', choices=['file', 'create', 'edit'],
                    default='file', type=str, help='Running Mode')
parser.add_argument('--config', '-c', required=True, default=None,
                    type=str, help='Path to the config file')
args = parser.parse_args()

mode = RunMode(args.mode)
config_file = args.config

PrettyPrinter_.show(1, print_stack=False)
########################################################################

########################################################################

META_KEY = 'meta'
APPS_KEY = 'apps'

config_json_app = JSONFile(config_file)
config_file = config_file if config_json_app.exists else None
apps_data = config_json_app.data

# NOTE Keep this code for later use
# c_flag = True
# while c_flag:
#     config_json_app = JSONFile(config_file)
#     config_file = config_file if config_json_app.exists else None
#     if not config_file:
#         show(0.5)
#         print(f"Invalid config file: {config_file}")
#         config_file = inputFilePath("Enter a valid path to the config file",)
#     else:
#         c_flag = False


def app_params_to_json(params: list[AppParameter]): return {
    META_KEY: {}, APPS_KEY: [p.toJSON() for p in params]}


if not apps_data or APPS_KEY not in apps_data or not apps_data[APPS_KEY]:
    mode = RunMode.CREATE
    PrettyPrinter_.warning(
        f"Invalid config file: {config_file} - No apps data found")
    PrettyPrinter_.info(f"Running on CREATING mode")


match mode:
    case RunMode.CREATE:
        apps_data = createApps()
        config_json_app.load(app_params_to_json(apps_data))
        PrettyPrinter_.success(f"Apps successfully created")

    case RunMode.EDIT:
        apps_data = editApps(apps_data)
        config_json_app.load(app_params_to_json(apps_data))
        PrettyPrinter_.success(f"Apps successfully edited")
    case RunMode.FILE:
        apps_data = [AppParameter.fromJSON(
            app, RESSOURCES, MIDDLEWARE) for app in apps_data[APPS_KEY]]
        PrettyPrinter_.show(0, clear_stack=True)
        PrettyPrinter_.success(f"Apps Config successfully loaded")
    case _:
        PrettyPrinter_.error(f"Errors while load apps")
        exit(0)

PrettyPrinter_.show(0, pause_before=1)
PrettyPrinter_.info('Starting applications...')
PrettyPrinter_.space_line()
start_applications(apps_data)
########################################################################
