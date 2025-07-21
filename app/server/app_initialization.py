from typing import Any
from app.container import Get
from app.server.application import AppParameter, RESSOURCES
from app.server.apps_registration import createApps, editApps,bootstrap_fastapi_server
from app.server.access_registration import prompt_client_registration
from app.server.middleware import MIDDLEWARE
from app.utils.constant import ConfigAppConstant, RunModeConstant
from app.services.config_service import ConfigService
from app.utils.prettyprint import PrettyPrinter_
from app.utils.question import ask_question,ConfirmInputHandler



# Initialize configuration service and load configuration
def initialize_config_service(config_file,uvicorn_args):
    config_service = Get(ConfigService)
    config_service.set_server_config(uvicorn_args)
    config_service.load_configApp(config_file)
    return config_service

# Validate configuration and determine initial mode
def validate_config(config_service:ConfigService, config_file, app_name):
    apps_data = config_service.config_json_app.data
    valid = True

    if not apps_data or ConfigAppConstant.META_KEY not in apps_data or ConfigAppConstant.APPS_KEY not in apps_data or not apps_data[ConfigAppConstant.APPS_KEY]:
        PrettyPrinter_.warning(f"Invalid config file: {config_file} - No apps data found")
        PrettyPrinter_.info(f"Running on CREATING mode")
        return RunModeConstant.CREATE, apps_data, False

    if app_name not in apps_data[ConfigAppConstant.APPS_KEY]:
        PrettyPrinter_.error(f'The app configuration name: {app_name} does not exist in the provided file')

    return RunModeConstant.FILE, apps_data, valid

# Handle different run modes
def handle_run_mode(mode, config_service:ConfigService, apps_data, config_file, valid):
    while True:
        match mode:
            case RunModeConstant.CREATE:
                if config_service.config_json_app.exists and valid:
                    PrettyPrinter_.warning(f"Config file {config_file} already exists", saveable=False)
                    overwrite = ask_question([ConfirmInputHandler('Do you want to overwrite the file?', name='overwrite_config', default=True)])['overwrite_config']
                    if not overwrite:
                        mode = RunModeConstant.FILE
                        continue

                apps_data = createApps()
                config_service.config_json_app.load(app_params_to_json(apps_data))
                PrettyPrinter_.success(f"Apps successfully created", position='left')
                break

            case RunModeConstant.EDIT:
                PrettyPrinter_.error("{EDIT} mode disabled for now")
                exit(0)  # BUG DISABLED FOR NOW

            case RunModeConstant.FILE:
                from app.server.application import AppParameter, RESSOURCES
                from app.server.middleware import MIDDLEWARE
                apps_data = {key: AppParameter.fromJSON(app, RESSOURCES, MIDDLEWARE) for key, app in apps_data[ConfigAppConstant.APPS_KEY].items()}
                PrettyPrinter_.success(f"Apps Config successfully loaded")
                break

            case RunModeConstant.REGISTER:
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


def build_apps_data(config_file,app_name,uvicorn_args):
    config_service = initialize_config_service(config_file,uvicorn_args)
    mode, apps_data, valid = validate_config(config_service, config_file, app_name)
    return handle_run_mode(mode, config_service, apps_data, config_file, valid)