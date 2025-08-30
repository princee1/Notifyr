from argparse import ArgumentParser
from enum import Enum
from app.utils.constant import RunModeConstant
from app.utils.prettyprint import PrettyPrinter_
import shutil
import sys

from app.utils.validation import host_validator

exe_path = shutil.which("uvicorn").replace(".EXE", "")

parser = ArgumentParser(description="Notifyr")

parser.add_argument('--mode', '-m', choices=[mode.value for mode in RunModeConstant.__members__.values()],
                        default='file', type=str, help='Running Mode')

parser.add_argument("--host", '-H',type=host_validator, default="127.0.0.1", help="Host to bind to")
parser.add_argument('--port','-p',default=-1,type=int,help='Specify the port, if not it will run using the port set a the env variable')
parser.add_argument("--log-level", '-l',default="info", choices=["critical", "error", "warning", "info", "debug", "trace"])
parser.add_argument('--config', '-c', default='./config.app.json',
                        type=str, help='Path to the config file')
parser.add_argument('--team','-t',type=str,default='solo',choices=['solo','team'],help="Whether there's other instance running too")


uvicorn_parser = ArgumentParser(description="Run a Uvicorn server.")
uvicorn_parser.add_argument("app", help="App location in format module:app")
uvicorn_parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
uvicorn_parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
uvicorn_parser.add_argument("--reload", action="store_true", help="Enable auto-reload",default=False)
uvicorn_parser.add_argument("--workers", type=int, help="Number of workers",default=4)
uvicorn_parser.add_argument("--log-level", default="info", choices=["critical", "error", "warning", "info", "debug", "trace"])

#parser.add_argument('--server-context','-s', default='uvicorn',choices=['python-main','uvicorn','guvicorn'],help='The scripts that will start the server')
uvicorn_args = None

if sys.argv[0] == exe_path:
    args=None
    uvicorn_args = uvicorn_parser.parse_args()
    args = parser.parse_args(['-m=file',f'-p={uvicorn_args.port}',f'-l={uvicorn_args.log_level}','-c=./config.app.json','-t=team',f'-H={uvicorn_args.host}'])
    
    
else:
    args = parser.parse_args()

########################################################################
from app.container import build_container, Get
build_container()
########################################################################

from app.server.app_initialization import bootstrap_fastapi_server,build_apps_data
build_apps_data(args.config,uvicorn_args)

# Main entry point

PrettyPrinter_.show(1, print_stack=False)
PrettyPrinter_.info('Starting applications...')
PrettyPrinter_.space_line()

if __name__ == '__main__':
    bootstrap_fastapi_server(args.port,args.log_level,args.host).start()
    
else:
    app = bootstrap_fastapi_server(args.port,args.log_level,args.host).app

