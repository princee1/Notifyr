"""
https://inquirerpy.readthedocs.io/en/latest/
"""
from enum import Enum
from typing import overload  # TODO add multiple definition
from InquirerPy import prompt
from InquirerPy.separator import Separator
from InquirerPy.base import Choice
from InquirerPy.prompts.expand import ExpandChoice
import pprint as pp
from InquirerPy.validator import *
from prompt_toolkit.styles import Style
from .prettyprint import printJSON

one_or_more_invalid_message = 'Should be at least 1 selection'
instruction = '(Press space to select, enter to continue)'

def one_or_more(result): return len(result) >= 1


def exactly_one(result): return len(result) == 1


class InputKeyAlreadyExistsError(BaseException):
    pass


class InputHandler:
    def __init__(self, inputType: str, message: str, default, name: str, when, validate, filter=None,invalid_message=None,instruction=None) -> None:
        self.type = inputType
        self.message = message
        self.default = default
        self.name = name
        self.when = when
        self.validate = validate
        self.filter = filter
        self.invalid_message = invalid_message
        self.instruction = instruction

    def clone(self, message):
        return

    @property
    def question(self) -> dict:
        # TODO check all valid attributes and add them in the dict
        return {
            "type": self.type,
            "message": self.message,
            "default": self.default,
            "name": self.name,
            # "qmark": self.qMark,
            "when": self.when,
            "validate": self.validate,
            "filter": self.filter,
            "invalid_message": self.invalid_message,
            "instruction": self.instruction
        }

        return self.__dict__
    
    


class ChoiceInterface:
    def __init__(self, choices) -> None:
        self.choices: list = choices
        pass

    def addChoices(self):
        return self

    def addValue(self, value):
        self.choices.append(value)
        return self

    def addSeparator(self, title=None):
        self.choices.append(Separator(title))
        return self

    def toDict(self) -> dict:
        return {
            "choices": self.choices
        }


class CheckboxInputHandler(InputHandler, ChoiceInterface):
    def __init__(self, message, name, choices=[], qMark=None, validate=None, filter=None, when=None,invalid_message=None,instruction=instruction) -> None:
        InputHandler.__init__(self, "checkbox",
                              message, None, name, when, validate, filter,invalid_message,instruction)
        ChoiceInterface.__init__(self, choices)

    def addChoices(self, value, name, checked=False, disabled=None):
        self.choices.append(Choice(value, name, checked))
        return super().addChoices()

    @property
    def question(self) -> dict:
        value = super().question
        value.update(ChoiceInterface.toDict(self))
        return value


class SimpleInputHandler(InputHandler):
    def __init__(self, message: str, default, name: str, validate=None, filter=None, when=None, completer=None, transformer=None,invalid_message=None,instruction=None) -> None:
        super().__init__("input", message, default, name, when, validate, filter,invalid_message,instruction)
        self.completer = completer
        self.transformer = transformer
        # NOTE multicolumn_completer = True

    pass


class NumberInputHandler(InputHandler):
    def __init__(self, message: str, default: int, name: str, min_allowed, max_allowed, float_allowed=False,  when=None, filter=None,invalid_message=None,instruction=None) -> None:
        super().__init__("number", message, default, name,
                         when, EmptyInputValidator(), filter,invalid_message,instruction)
        self.min_allowed = min_allowed
        self.max_allowed = max_allowed
        self.float_allowed = float_allowed


class ConfirmInputHandler(InputHandler):
    def __init__(self, message: str, name: str, default: bool, validate=None, filter=None, when=None,invalid_message=None,instruction=None) -> None:
        super().__init__("confirm", message, default, name, when, validate, filter,invalid_message,instruction)

    @property
    def question(self):
        value = super().question
        value.pop('validate')
        value.pop('invalid_message')
        value.pop('instruction')
        return value

class PasswordInputHandler(InputHandler):
    def __init__(self, message: str, name: str, instruction: str, invalidMessage=None, validate=None, filter=None, when=None, transformer=None) -> None:
        super().__init__("password", message, None, name, when, validate, filter,invalidMessage,instruction)
        self.transformer = transformer
        self.long_instruction = instruction


class ListInputHandler(InputHandler, ChoiceInterface):
    class ListTypeQuestion(Enum):
        RAW_LIST = "rawlist"
        LIST = "list"
        pass

    def __init__(self, message: str, default: int, name: str, choices=[], inputType: ListTypeQuestion = ListTypeQuestion.LIST ,multiselect=False, validate=None, filter=None, when=None, transformer=None,invalid_message=None,instruction=None) -> None:
        super().__init__(
            inputType.value, message, default, name, when, validate, filter,invalid_message,instruction)
        ChoiceInterface.__init__(self, choices)
        self.multiselect = multiselect
        self.transformer = transformer

    def addChoices(self, name, value):
        self.choices.append(Choice(value, name))
        return super().addChoices()

    @property
    def question(self) -> dict:
        value = super().question
        value.update(ChoiceInterface.toDict(self))
        value["multiselect"] = self.multiselect
        value["transformer"] = self.transformer
        #value['required'] = True
        return value


class ExpandInputHandler(InputHandler, ChoiceInterface):
    def __init__(self, message: str, default: str, name: str, choices=[], qMark=None, when=None, validate=None, filter=None,invalid_message=None,instruction=None) -> None:
        super().__init__("expand", message, default, name, qMark, when, validate, filter,invalid_message,instruction)
        ChoiceInterface.__init__(self, choices)

    def addChoices(self, key, name, value, checked=False):
        self.choices.append(ExpandChoice(value, name, checked, key))
        return super().addChoices()

    @property
    def question(self) -> dict:
        value = super().question
        value.update(ChoiceInterface.toDict(self))
        return value

    def addValue(self):
        raise NotImplementedError("Should be used in this context")


class FileInputHandler(InputHandler):
    def __init__(self, message: str, name: str, errorMessage: str, filter=None, when=None, isDir=False,invalid_message=None,instruction=None) -> None:
        super().__init__("filepath", message, './', name, when, PathValidator(
            message=errorMessage, is_dir=isDir, is_file=not isDir), filter,invalid_message,instruction)
        self.only_files = not isDir
        self.only_directories = isDir


class FuzzyInputHandler(InputHandler,ChoiceInterface):
    
    def __init__(self,message,name, when, validate,choices=[], filter=None, invalid_message=None, instruction=None):
        super().__init__('fuzzy', message, '', name, when, validate, filter, invalid_message, instruction)
        ChoiceInterface.__init__(self, choices)

    def addChoices(self, name, value):
        self.choices.append(Choice(value, name))
        return super().addChoices()
    
    @property
    def question(self) -> dict:
        value = super().question
        value.update(ChoiceInterface.toDict(self))
        value.update({'multiselect':True,'max_height':'70%'})
        return value



custom_style = Style.from_dict({
    "question": "bold #ansiblue",        # Question text
    "answer": "#ffcc00",                 # Answer text
    "pointer": "fg:#ansiyellow bold",    # Pointer (arrow)
    "checkbox": "fg:#ffcc00 bold",       # Checkbox selection
    "separator": "fg:#cc0000",           # Separator line
    # Instruction (e.g., "(use arrow keys)")
    "instruction": "fg:#ansigreen italic",
    "text": "#ffffff",                   # General text
    "selected": "fg:#000000 bg:#ffcc00",  # Selected item
    "pointer-marker": "fg:#ffcc00",      # Pointer marker for list options
})


def ask_question(questions: list[InputHandler], style=None,vi_mode=False,key_bindings=None) -> dict:
    names_error:set = set()
    questions_list = [q.question for q in questions]
    for q in questions:
        if q.name in names_error:
            raise InputKeyAlreadyExistsError()
        names_error.add(q.name)
        
    answers = prompt(questions_list, style, vi_mode=vi_mode, keybindings=key_bindings)
    return answers
