from typing import TypedDict, Literal, Any
import asyncio

Status=Literal['start','running', 'done']

class Step(TypedDict):
    current_step: str
    steps: dict[str, Any]
    status: Status
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

    def __init__(self, state: Step, step_name: str, params: Any = None,status:Status=None):
        self.state = state
        self.step_name = step_name
        self.params = params
        self.status = status

    async def __aenter__(self):
        self.state['current_step'] = self.step_name
        self.state['current_params'] = self.params
        
        if self.step_name in self.state['steps']:
            return SkipStepObj(True)
        
        return SkipStepObj(False)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.state['steps'][self.step_name] = True
        elif exc_type == SkipStep:
            return
        else:
            raise exc_val
        self.state['current_params'] = None