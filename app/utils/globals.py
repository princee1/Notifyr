import os 
import sys
from typing import Literal

DIRECTORY_SEPARATOR = '/' if os.name != 'nt' else '\\'
ASSET_SEPARATOR = '/'
CWD = os.getcwd() + DIRECTORY_SEPARATOR
RENAME:Literal['windows', 'linux', 'mac'] = 'windows' if os.name == 'nt' else 'linux' if sys.platform.startswith('linux') else 'mac' if sys.platform == 'darwin' else 'unknown'
LINE_ENDING = '\r\n' if RENAME == 'windows' else '\n'

PROCESS_PID = str(os.getpid())
PARENT_PID = str(os.getppid())