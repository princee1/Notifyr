from argparse import ArgumentParser
from enum import Enum
from app.signal_handler import SignalHandler_
from app.utils.prettyprint import PrettyPrinter_


class RunMode(Enum):
    FILE = "file"
    CREATE = "create"
    EDIT = "edit"
    REGISTER = "register"


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
from app.container import build_container, Get
build_container()

from app.server.application import AppParameter, RESSOURCES
from app.server.apps_registration import createApps, editApps,start_applications
from app.server.access_registration import prompt_client_registration
from app.server.middleware import MIDDLEWARE
from app.utils.constant import ConfigAppConstant
from app.services.config_service import ConfigService
from app.utils.question import ask_question,ConfirmInputHandler
# from definition._ressource import DECORATOR_METADATA,METADATA_ROUTES,ROUTES,PROTECTED_ROUTES
########################################################################

configService:ConfigService = Get(ConfigService)
configService.load_configApp(config_file)
apps_data = configService.config_json_app.data
#TODO modify the metadata


# NOTE Keep this code for later use
# c_flag = True
# while c_flag:
#     config_json_app = JSONFile(config_file)
#     config_file = config_file if config_json_exists else None
#     if not config_file:
#         show(0.5)
#         print(f"Invalid config file: {config_file}")
#         config_file = inputFilePath("Enter a valid path to the config file",)
#     else:
#         c_flag = False
valid = True
if not apps_data or ConfigAppConstant.META_KEY not in apps_data or ConfigAppConstant.APPS_KEY not in apps_data or not apps_data[ConfigAppConstant.APPS_KEY]:
    mode = RunMode.CREATE
    valid = False
    PrettyPrinter_.show(0, )
    PrettyPrinter_.warning(
        f"Invalid config file: {config_file} - No apps data found")
    PrettyPrinter_.info(f"Running on CREATING mode")

def app_params_to_json(params: list[AppParameter],metadata={}): return {
    ConfigAppConstant.META_KEY: metadata, ConfigAppConstant.APPS_KEY: [p.toJSON() for p in params]}

while True:
    match mode:
        case RunMode.CREATE:
            if configService.config_json_app.exists and valid:
                PrettyPrinter_.show(0, clear_stack=False,print_stack=False)
                PrettyPrinter_.warning(
                    f"Config file {config_file} already exists",saveable=False)
                overwrite = ask_question([ConfirmInputHandler('Do you want to overwrite the file?', name='overwrite_config',default=True)],)['overwrite_config']
                if not overwrite:
                    mode = RunMode.FILE
                    continue
            
            apps_data = createApps()
            configService.config_json_app.load(app_params_to_json(apps_data))
            PrettyPrinter_.success(f"Apps successfully created",position='left')
            prompt_client_registration()
            break

        case RunMode.EDIT:
            PrettyPrinter_.error("{EDIT} mode disabled for now")
            exit(0) # BUG DISABLED FOR NOW
            metadata = apps_data[ConfigAppConstant.META_KEY].copy()
            apps_data = editApps(apps_data[ConfigAppConstant.APPS_KEY])
            configService.config_json_app.load(app_params_to_json(apps_data,metadata))
            PrettyPrinter_.success(f"Apps successfully edited")
            prompt_client_registration()
            break

        case RunMode.FILE:
            apps_data = [AppParameter.fromJSON(
                app, RESSOURCES, MIDDLEWARE) for app in apps_data[ConfigAppConstant.APPS_KEY]]
            PrettyPrinter_.show(0, clear_stack=True)
            PrettyPrinter_.success(f"Apps Config successfully loaded")
            break

        case RunMode.REGISTER:
            PrettyPrinter_.error("{EDIT} mode disabled for now")
            exit(0) # BUG DISABLED FOR NOW
            prompt_client_registration()
            if valid:
                mode = RunMode.FILE
                continue
            exit(0)

        case _:
            PrettyPrinter_.error(f"Errors while load apps")
            exit(0)


PrettyPrinter_.show(0, pause_before=1)
PrettyPrinter_.info('Starting applications...')
PrettyPrinter_.space_line()
start_applications(apps_data)
########################################################################
