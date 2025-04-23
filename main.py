from argparse import ArgumentParser
from enum import Enum
from typing import Any
from app.signal_handler import SignalHandler_
from app.utils.prettyprint import PrettyPrinter_


class RunMode(Enum):
    FILE = "file"
    CREATE = "create"
    EDIT = "edit"
    REGISTER = "register"


parser = ArgumentParser(description="Communication Service Application")
parser.add_argument('--mode', '-m', choices=[mode.value for mode in RunMode.__members__.values()],
                    default='file', type=str, help='Running Mode')

parser.add_argument('--name','-m',required=True,type=str,help='The name of configuration to use')

parser.add_argument('--config', '-c', required=True, default=None,
                    type=str, help='Path to the config file')
args = parser.parse_args()

mode = RunMode(args.mode)
config_file = args.config
app_name = args.name

PrettyPrinter_.show(1, print_stack=False)
########################################################################
from app.container import build_container, Get
build_container()
########################################################################
from app.server.application import AppParameter, RESSOURCES
from app.server.apps_registration import createApps, editApps,bootstrap_fastapi_server
from app.server.access_registration import prompt_client_registration
from app.server.middleware import MIDDLEWARE
from app.utils.constant import ConfigAppConstant
from app.services.config_service import ConfigService
from app.utils.question import ask_question,ConfirmInputHandler
# from definition._ressource import DECORATOR_METADATA,METADATA_ROUTES,ROUTES,PROTECTED_ROUTES
########################################################################
configService:ConfigService = Get(ConfigService)
configService.load_configApp(config_file)
apps_data: dict[str, Any] = configService.config_json_app

valid = True
if not apps_data or ConfigAppConstant.META_KEY not in apps_data or ConfigAppConstant.APPS_KEY not in apps_data or not apps_data[ConfigAppConstant.APPS_KEY]:
    mode = RunMode.CREATE
    valid = False
    PrettyPrinter_.show(0, print_stack=False)
    PrettyPrinter_.warning(f"Invalid config file: {config_file} - No apps data found")
    PrettyPrinter_.info(f"Running on CREATING mode")

if app_name not in apps_data[ConfigAppConstant.APPS_KEY]:
    PrettyPrinter_.show(0, print_stack=False)
    PrettyPrinter_.error(f'The app configuration name: {app_name} does not exists in the provided file')


def app_params_to_json(params: dict[str, AppParameter], metadata={}): 
    return {
        ConfigAppConstant.META_KEY: metadata, 
        ConfigAppConstant.APPS_KEY: {key: param.toJSON() for key, param in params.items()}
    }


while True:
    match mode:
        case RunMode.CREATE:
            if configService.config_json_app.exists and valid:
                PrettyPrinter_.show(0, clear_stack=False, print_stack=False)
                PrettyPrinter_.warning(f"Config file {config_file} already exists", saveable=False)
                overwrite = ask_question([ConfirmInputHandler('Do you want to overwrite the file?', name='overwrite_config', default=True)])['overwrite_config']
                if not overwrite:
                    mode = RunMode.FILE
                    continue
            
            apps_data = createApps()
            configService.config_json_app.load(app_params_to_json(apps_data))
            PrettyPrinter_.success(f"Apps successfully created", position='left')
            break

        case RunMode.EDIT:
            PrettyPrinter_.error("{EDIT} mode disabled for now")
            exit(0)  # BUG DISABLED FOR NOW
            metadata = apps_data[ConfigAppConstant.META_KEY].copy()
            apps_data = editApps(apps_data[ConfigAppConstant.APPS_KEY])
            configService.config_json_app.load(app_params_to_json(apps_data, metadata))
            PrettyPrinter_.success(f"Apps successfully edited")
            break

        case RunMode.FILE:
            apps_data = {key: AppParameter.fromJSON(app, RESSOURCES, MIDDLEWARE) for key, app in apps_data[ConfigAppConstant.APPS_KEY].items()}
            PrettyPrinter_.show(0, clear_stack=True)
            PrettyPrinter_.success(f"Apps Config successfully loaded")
            break

        case RunMode.REGISTER:
            PrettyPrinter_.error("{EDIT} mode disabled for now")
            exit(0) # BUG DISABLED FOR
            raise NotImplementedError
            if valid:
                prompt_client_registration()
                mode = RunMode.FILE
                continue
            PrettyPrinter_.space_line()
            PrettyPrinter_.error("{REGISTER} mode cannot run if the config are not valid")
            exit(0)

        case _:
            PrettyPrinter_.error(f"Errors while load apps")
            exit(0)

########################################################################
if __name__ == '__main__':
    PrettyPrinter_.show(0, pause_before=1)
    PrettyPrinter_.info('Starting applications...')
    PrettyPrinter_.space_line()
    app_config = apps_data[ConfigAppConstant.APPS_KEY][app_name]
    server=bootstrap_fastapi_server(app_config)
########################################################################
