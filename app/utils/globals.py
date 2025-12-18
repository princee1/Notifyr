import os 
import sys
from typing import Literal
from enum import Enum
import shutil


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

APP_MODE:ApplicationMode = ApplicationMode.server

if sys.argv[0] == CELERY_EXE_PATH:
    if sys.argv[3] == 'beat':
        APP_MODE = ApplicationMode.beat
    else:
        APP_MODE = ApplicationMode.worker
else:
    ...
