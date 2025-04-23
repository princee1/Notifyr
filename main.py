from argparse import ArgumentParser
from enum import Enum
from typing import Any
from app.container import Get
from app.utils.prettyprint import PrettyPrinter_

# Define RunMode Enum
class RunMode(Enum):
    FILE = "file"
    CREATE = "create"
    EDIT = "edit"
    REGISTER = "register"

parser = ArgumentParser(description="Communication Service Application")
parser.add_argument('--mode', '-m', choices=[mode.value for mode in RunMode.__members__.values()],
                        default='file', type=str, help='Running Mode')
parser.add_argument('--name', '-n', required=True, type=str, help='The name of configuration to use')
parser.add_argument('--config', '-c', required=True, default=None,
                        type=str, help='Path to the config file')
args = parser.parse_args()

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
import uvicorn


# Initialize configuration service and load configuration
def initialize_config_service(config_file):
    config_service = Get(ConfigService)
    config_service.load_configApp(config_file)
    return config_service

# Validate configuration and determine initial mode
def validate_config(config_service:ConfigService, config_file, app_name):
    apps_data = config_service.config_json_app.data
    valid = True

    if not apps_data or ConfigAppConstant.META_KEY not in apps_data or ConfigAppConstant.APPS_KEY not in apps_data or not apps_data[ConfigAppConstant.APPS_KEY]:
        PrettyPrinter_.warning(f"Invalid config file: {config_file} - No apps data found")
        PrettyPrinter_.info(f"Running on CREATING mode")
        return RunMode.CREATE, apps_data, False

    if app_name not in apps_data[ConfigAppConstant.APPS_KEY]:
        PrettyPrinter_.error(f'The app configuration name: {app_name} does not exist in the provided file')

    return RunMode.FILE, apps_data, valid

# Handle different run modes
def handle_run_mode(mode, config_service:ConfigService, apps_data, config_file, valid):
    while True:
        match mode:
            case RunMode.CREATE:
                if config_service.config_json_app.exists and valid:
                    PrettyPrinter_.warning(f"Config file {config_file} already exists", saveable=False)
                    overwrite = ask_question([ConfirmInputHandler('Do you want to overwrite the file?', name='overwrite_config', default=True)])['overwrite_config']
                    if not overwrite:
                        mode = RunMode.FILE
                        continue

                apps_data = createApps()
                config_service.config_json_app.load(app_params_to_json(apps_data))
                PrettyPrinter_.success(f"Apps successfully created", position='left')
                break

            case RunMode.EDIT:
                PrettyPrinter_.error("{EDIT} mode disabled for now")
                exit(0)  # BUG DISABLED FOR NOW

            case RunMode.FILE:
                from app.server.application import AppParameter, RESSOURCES
                from app.server.middleware import MIDDLEWARE
                apps_data = {key: AppParameter.fromJSON(app, RESSOURCES, MIDDLEWARE) for key, app in apps_data[ConfigAppConstant.APPS_KEY].items()}
                PrettyPrinter_.success(f"Apps Config successfully loaded")
                break

            case RunMode.REGISTER:
                PrettyPrinter_.error("{EDIT} mode disabled for now")
                exit(0)  # BUG DISABLED FOR NOW

            case _:
                PrettyPrinter_.error(f"Errors while loading apps")
                exit(0)

    return apps_data

# Convert app parameters to JSON
def app_params_to_json(params: dict[str, Any], metadata={}):
    from app.utils.constant import ConfigAppConstant
    return {
        ConfigAppConstant.META_KEY: metadata,
        ConfigAppConstant.APPS_KEY: {key: param.toJSON() for key, param in params.items()}
    }

# Main entry point
if __name__ == '__main__':
    PrettyPrinter_.show(1, print_stack=False)
    mode = RunMode(args.mode)
    config_file = args.config
    app_name = args.name

    config_service = initialize_config_service(config_file)
    mode, apps_data, valid = validate_config(config_service, config_file, app_name)
    apps_data = handle_run_mode(mode, config_service, apps_data, config_file, valid)

    PrettyPrinter_.info('Starting applications...')
    PrettyPrinter_.space_line()
    app_parameter:AppParameter = apps_data[app_name]
    bootstrap_fastapi_server(app_parameter).start()

    # uvicorn.run('main:server',port = app_parameter.port,loop='asyncio')