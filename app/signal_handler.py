import signal
import sys
from typing import Any, Callable, Iterable
from app.utils.question import ask_question, ConfirmInputHandler
from app.utils.prettyprint import PrettyPrinter_

def default_term_handler(signal,frame):
    PrettyPrinter_.warning('Termination signal Detected...',saveable = False)
    result = ask_question([ConfirmInputHandler('Do you want to terminate the process','term',False,)])['term']
    result = bool(result)
    if result:
        sys.exit(0)
    
class SignalHandler:
    
    ValidSignal= signal.valid_signals()

    def __init__(self):
        # self.signal:dict[str, Callable] = {}

        self.register_signal(signal.SIGINT,default_term_handler)
        self.register_signal(signal.SIGTERM,default_term_handler)
        self.register_signal(signal.CTRL_C_EVENT,default_term_handler)


    def register_signal(self, signal_val:signal.Signals,handler:Callable[[signal.Signals,Any],None | Exception]):
        ...
    
    def raise_signal(self, signal_val:signal.Signals):
       ... 

    def get_signal(self, signal_val:signal.Signals):
        ...


SignalHandler_: SignalHandler = SignalHandler()
