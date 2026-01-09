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
        self.step_index = step_index
        self.params = params

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
            self.state['steps'][self.step_index] = True
            self.state['current_params'] = None
            self.state['current_step'] = self.step_index
            return True  # nothing to propagate

        if exc_type is SkipStep:
            self.state['current_params'] = None
            return True  # suppress SkipStep

        return False
        