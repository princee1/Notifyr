from app.container import Get
from app.server.application import Application
from app.utils.constant import ConfigAppConstant, RunModeConstant
from app.services.config_service import ConfigService
from app.utils.prettyprint import PrettyPrinter_

# Initialize configuration service and load configuration
def initialize_config_service(config_file,uvicorn_args):
    config_service = Get(ConfigService)
    config_service.set_server_config(uvicorn_args)
    config_service.load_configApp(config_file)
    return config_service

# Validate configuration and determine initial mode
def validate_config(config_service:ConfigService, config_file):
    apps_data = config_service.config_json_app.data

    if not apps_data or ConfigAppConstant.META_KEY not in apps_data:
        PrettyPrinter_.warning(f"Invalid config file: {config_file} - No apps data found")
        PrettyPrinter_.info(f"Running on CREATING mode")
        return False

    return True


def build_apps_data(config_file,uvicorn_args):
    config_service = initialize_config_service(config_file,uvicorn_args)
    if not validate_config(config_service, config_file):
        exit(-1)
    
def bootstrap_fastapi_server(port:int,log_level:str):
    return Application(port,log_level)