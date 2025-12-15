from argparse import ArgumentParser
from app.utils.constant import RunModeConstant
from app.utils.prettyprint import PrettyPrinter_
import shutil
import sys
import warnings
import gc

warnings.filterwarnings("ignore",category=UserWarning,)

from app.utils.validation import host_validator, port_validator

exe_path = shutil.which("uvicorn").replace(".EXE", "")

parser = ArgumentParser(description="Notifyr")

parser.add_argument('--mode', '-m', choices=[mode.value for mode in RunModeConstant.__members__.values()],
                        default='server', type=str, help='Running Mode')

parser.add_argument("--host", '-H',type=host_validator, default="127.0.0.1", help="Host to bind to")
parser.add_argument('--port','-p',default=8088,type=port_validator,help='Specify the port, if not it will run using the port set a the env variable')
parser.add_argument("--log-level", '-l',default="info", choices=["critical", "error", "warning", "info", "debug", "trace"])
parser.add_argument('--team','-t',type=str,default='solo',choices=['solo','team'],help="Whether there's other instance running too")
parser.add_argument('--workers','-w',type=int,default=1,help="Specify the number of workers")

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
    args = parser.parse_args(['-m=server',f'-p={uvicorn_args.port}',f'-l={uvicorn_args.log_level}','-t=team',f'-H={uvicorn_args.host}',f'-w={uvicorn_args.workers}'])
    setattr(args,'reload',uvicorn_args.reload)
else:
    args = parser.parse_args()
    setattr(args,'reload',False)
    setattr(args,'workers',1)

########################################################################

from app.container import build_container
build_container()
gc.collect()
########################################################################

from app.server.app_initialization import bootstrap_fastapi_server,initialize_config_service
from app.services import ConfigService
configService:ConfigService = initialize_config_service(args)

gc.collect()
########################################################################


# Main entry point
PrettyPrinter_.show(1, print_stack=False)
PrettyPrinter_.info('Starting applications...')
PrettyPrinter_.space_line()

if __name__ == '__main__':
    bootstrap_fastapi_server(args.port,args.log_level,args.host).start()
else:
    app = bootstrap_fastapi_server()

########################################################################
