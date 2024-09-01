"""
Generated from chat GPT, cause im too lazy
"""
from typing import Any
from InquirerPy import prompt
from InquirerPy.validator import NumberValidator


class InputHandler():

    def prompt(self,message:str):
        pass
    pass

class ChoiceHandler(InputHandler):
    def __init__(self,message,name,baseChoice=[]) -> None:
        super().__init__(message,name)
        self.choices:list[Any] = baseChoice

    def addChoice(self,value:Any | list[Any]):
        if type(value) is Any:
            self.choices.append(value)
        else: 
            self.choices.extend(value)
        return self


class NumberInputHandler(InputHandler):
    def __init__(self, default=0, min_val=None, max_val=None):
        super().__init__()
        self.result = None
        self.default = default
        self.min_val = min_val
        self.max_val = max_val

    def number_input(self, message="Enter a number",):
        question = {
            "type": "input",
            "name": "number",
            "message": message,
            "default": str(self.default),
            "validate": NumberValidator(),
            "filter": lambda val: int(val)
        }
        if self.min_val is not None or self.max_val is not None:
            question["validate"] = NumberValidator(
                min_value=self.min_val, max_value=self.max_val)

        answer = prompt(question)
        self.result = answer["number"]
        return self.result

    def prompt(self, message: str = "Enter a number"):
        return self.number_input(message)


class ChoiceInputHandler(ChoiceHandler):
    def __init__(self,choices=[],default=None):
        super().__init__()
        self.result = None
        self.choices = choices
        if default is not None and default not in self.choices:
            raise ValueError
        
        self.default = default

    def choice_input(self, message="Choose an option",show_detail=False):
        
        question = {
            "type": "list",
            "name": "choice",
            "message": message,
            "choices": self.choices,
            "default": self.default
        }

        answer = prompt(question)
        self.result = answer["choice"]
        return self.result
    
    def prompt(self, message: str = "Enter a number"):
        return self.choice_input(message)



# Example usage
number_handler = NumberInputHandler()
choice_handler = ChoiceInputHandler()