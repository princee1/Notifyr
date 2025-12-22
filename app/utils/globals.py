import os 
import sys
from typing import Literal, TypedDict
from enum import Enum
import shutil
from .fileIO import JSONFile


CELERY_EXE_PATH = shutil.which("celery").replace(".EXE", "")


DIRECTORY_SEPARATOR = '/' if os.name != 'nt' else '\\'
ASSET_SEPARATOR = '/'
CWD = os.getcwd() + DIRECTORY_SEPARATOR
RENAME:Literal['windows', 'linux', 'mac'] = 'windows' if os.name == 'nt' else 'linux' if sys.platform.startswith('linux') else 'mac' if sys.platform == 'darwin' else 'unknown'
LINE_ENDING = '\r\n' if RENAME == 'windows' else '\n'

PROCESS_PID = str(os.getpid())
PARENT_PID = str(os.getppid())

class ApplicationMode(Enum):
    worker = 'worker'
    beat = 'beat'
    server = 'server'
    agentic ='agentic'
    gunicorn = 'gunicorn'

class ServerCapabilities(TypedDict):
    email:bool
    twilio:bool
    notification:bool
    message:bool
    agent:bool
    webhook:bool
    object:bool
    workflow:bool

class AgenticServerCapabilities(TypedDict):
    knowledge_graph:bool
    vector:bool

if sys.argv[0] == CELERY_EXE_PATH:
    if sys.argv[3] == 'beat':
        APP_MODE = ApplicationMode.beat
    else:
        APP_MODE = ApplicationMode.worker
elif 'agentic_main.py' in sys.argv[0]:
    APP_MODE = ApplicationMode.agentic
else:
    APP_MODE = ApplicationMode.server

_deployment=JSONFile('/run/secrets/deploy.json',os_link=False,from_data=None)


CAPABILITIES:ServerCapabilities = _deployment['capabilities']
AGENTIC_CAPABILITIES:AgenticServerCapabilities = _deployment['agentic']