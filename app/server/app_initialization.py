from app.container import Get
from app.server.application import Application
from app.services.config_service import ConfigService,UvicornWorkerService
from app.utils.prettyprint import PrettyPrinter_

# Initialize configuration service and load configuration
def initialize_config_service(server_args):
    config_service = Get(ConfigService)
    workerService = Get(UvicornWorkerService)
    workerService.set_server_config(server_args)
    return config_service
    
def bootstrap_fastapi_server(port:int=None,log_level:str=None,host:str=None):
    return Application(port,log_level,host)