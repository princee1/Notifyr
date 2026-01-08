from typing import TypedDict, Literal, Any
from random import randint
import asyncio

Status=Literal['start','running', 'done']

class Step(TypedDict):
    current_step: int
    steps: dict[int, Any]
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
        print(self.state)
        self.step_index = step_index
        self.params = params

    async def __aenter__(self):
        self.state['current_step'] = self.step_index
        if self.params != None:
            self.state['current_params'] = self.params
        
        if self.step_index in self.state['steps']:
            return SkipStepObj(True)
        
        if self.step_index >= self.state['current_step']:
            return SkipStepObj(True)
        
        return SkipStepObj(False)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        print(exc_type,exc_val)
        if exc_type is None:
            self.state['steps'][self.step_index] = True
        elif exc_type == SkipStep:
            return
        else:
            raise exc_val
        self.state['current_params'] = None