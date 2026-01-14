from typing import TypedDict, Literal, Any
from random import randint
import asyncio
from time import time
from datetime import datetime


Status=Literal['start','running', 'done']

class StepMeta(TypedDict):
    success:Literal[True]
    time:int
    date:str

class Step(TypedDict):
    current_step: int
    steps: dict[int, StepMeta]
    current_params: Any

class SkipStep(Exception):
    """Internal exception to bypass the block."""
    pass

class SkipStepObj:
        
    def __init__(self,_raise:bool):
        self._raise = _raise

    def __call__(self):
        if self._raise:
            raise SkipStep()
            
class StepRunner:

    def __init__(self, state: Step, step_index: int, params: Any = None):
        self.state = state
        self.step_index = step_index
        self.params = params
        self.start_time = time()


    async def __aenter__(self):
        if self.params != None:
            self.state['current_params'] = self.params
        
        if self.step_index in self.state['steps']:
            return SkipStepObj(True)
        
        if self.state['current_step'] >= self.step_index:
            return SkipStepObj(True)
        
        return SkipStepObj(False)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            now = datetime.now().isoformat()
            meta =  StepMeta(success=True,time=time()-self.start_time,date=now)
            self.state['steps'][self.step_index] =meta
            self.state['current_params'] = None
            self.state['current_step'] = self.step_index
            return True  # nothing to propagate

        if exc_type is SkipStep:
            self.state['current_params'] = None
            return True  # suppress SkipStep

        return False
        