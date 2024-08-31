"""
Generated from chat GPT, cause im too lazy
"""
from typing import Any
from InquirerPy import prompt
from InquirerPy.validator import NumberValidator


class InputHandler():

    def prompt(self):
        pass
    pass

class ChoiceHandler(InputHandler):
    def __init__(self) -> None:
        super().__init__()
        self.choices:list[Any] = []

    def addChoice(self,value:Any | list[Any]):
        if type(value) is Any:
            self.choices.append(value)
        else: 
            self.choices.extend(value)
        return self


class NumberInputHandler(InputHandler):
    def __init__(self, default=0, min_val=None, max_val=None):
        self.result = None
        self.default = default
        self.min_val = min_val
        self.max_val = max_val

    def number_input(self, message="Enter a number", ):
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

        if show_detail:
            detail = self.show_detail(answer["choice"])
            return self.result, detail

        return self.result

    def show_detail(self, choice):
        detail_mapping = {
            "Option 1": "Detail for Option 1",
            "Option 2": "Detail for Option 2",
            "Option 3": "Detail for Option 3",
        }
        detail = detail_mapping.get(choice, "No details available")
        print(detail)
        return detail


# Example usage
number_handler = NumberInputHandler()
choice_handler = ChoiceInputHandler()

# Number input with a range of 1 to 10
number = number_handler.number_input(
    message="Please enter a number between 1 and 10:", min_val=1, max_val=10)
print(f"Number entered: {number}")

# Choice input with the ability to show details based on the selection
choice, detail = choice_handler.choice_input(message="Select an option:", choices=[
                                             "Option 1", "Option 2", "Option 3"], show_detail=True)
print(f"Choice selected: {choice}")
print(f"Detail: {detail}")
