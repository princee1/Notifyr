from argparse import ArgumentParser
from enum import Enum
from app.utils.constant import RunModeConstant
from app.utils.prettyprint import PrettyPrinter_
import shutil
import sys

exe_path = shutil.which("uvicorn").replace(".EXE", "")

parser = ArgumentParser(description="Communication Service Application")
parser.add_argument('--mode', '-m', choices=[mode.value for mode in RunModeConstant.__members__.values()],
                        default='file', type=str, help='Running Mode')
parser.add_argument('--name', '-n', type=str, default='default', help='The name of configuration to use')
parser.add_argument('--config', '-c', default='./config.app.json',
                        type=str, help='Path to the config file')
parser.add_argument('--pool','-p',type=str,default='solo',choices=['solo','team'],help="Whether there's other instance running too")

uvicorn_parser = ArgumentParser(description="Run a Uvicorn server.")
uvicorn_parser.add_argument("app", help="App location in format module:app")
uvicorn_parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
uvicorn_parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
uvicorn_parser.add_argument("--reload", action="store_true", help="Enable auto-reload",default=False)
uvicorn_parser.add_argument("--workers", type=int, help="Number of workers",default=0)
uvicorn_parser.add_argument("--log-level", default="info", choices=["critical", "error", "warning", "info", "debug", "trace"])

#parser.add_argument('--server-context','-s', default='uvicorn',choices=['python-main','uvicorn','guvicorn'],help='The scripts that will start the server')
uvicorn_args = None

if sys.argv[0] == exe_path:
    args=None
    args = parser.parse_args(['-m=file','-n=default','-c=./config.app.json',])
    uvicorn_args = uvicorn_parser.parse_args()
    
else:
    args = parser.parse_args()

########################################################################

from app.container import build_container, Get
build_container()
from app.server.app_initialization import build_apps_data,AppParameter,bootstrap_fastapi_server

# Main entry point

PrettyPrinter_.show(1, print_stack=False)

mode = RunModeConstant(args.mode)
config_file:str = args.config 
app_name:str = args.name

apps_data = build_apps_data(config_file,app_name,uvicorn_args)

PrettyPrinter_.info('Starting applications...')
PrettyPrinter_.space_line()
app_parameter:AppParameter = apps_data[app_name]

if __name__ == '__main__':
    bootstrap_fastapi_server(app_parameter).start()
    
else:
    app = bootstrap_fastapi_server(app_parameter).app

