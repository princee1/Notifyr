import rich
import os
import colorama
from colorama import Fore, Back, Style
from colorama.ansi import clear_line, clear_screen, set_title
import emoji
from typing import Any, Callable, List, Literal
import pprint
import pyfiglet
import time
import sys
from functools import wraps
import datetime as dt


EmojiPosition = Literal['left', 'right', 'both', 'none']
# Initialize colorama
colorama.init(autoreset=True)

pprinter = pprint.PrettyPrinter()

########################################################################

text = 'Communication - Service'
justify = 'left'

figlet = pyfiglet.Figlet(font='standard')
ascii_art = figlet.renderText(text)

if justify == 'center':
    ascii_art = '\n'.join(line.center(80) for line in ascii_art.splitlines())
elif justify == 'right':
    ascii_art = '\n'.join(line.rjust(80) for line in ascii_art.splitlines())


def show(t=10, title='Communication - Service', t1=0, color=Fore.WHITE):
    time.sleep(t1)
    clearscreen()
    settitle(title)
    base_print(ascii_art, color=color, emoji_code='')
    time.sleep(t)


class SkipInputException(Exception):
    ...

########################################################################


def settitle(tilte: str):
    set_title(tilte)


def clearline(): clear_line()


def clearscreen():
    if os.name == 'nt':
        os.system('cls')  # clear_screen()
    else:
        os.system('clear')


def base_message(message, color=Fore.WHITE, background=Back.RESET, emoji_code=":speech_balloon:", position: EmojiPosition = 'both'):
    """
    Base function to return a personalized message with color and emoji.
    """
    is_emojized = emoji_code.startswith(':')
    _emoji = emoji.emojize(emoji_code) if is_emojized else emoji_code

    return color + background + (_emoji + "  " if (position == "left" or position == "both") else "") + message + ("  "+_emoji if (position == "right" or position == "both") else "") + Style.RESET_ALL


def base_print(message, color=Fore.WHITE, background=Back.RESET, emoji_code=":speech_balloon:", position: EmojiPosition = 'both'):
    """
    Base function to print a personalized message with color and emoji.
    """
    print(base_message(message, color, background, emoji_code, position))


def print_info(message, position: EmojiPosition = 'both'):
    """
    Print an info message.
    """
    base_print(message, color=Fore.BLUE,
               emoji_code=":information:", position=position)


def print_message(message, position: EmojiPosition = 'both'):
    base_print(message, color=Fore.WHITE,
               emoji_code='\U0001F4AC', position=position)


def print_error(message, position: EmojiPosition = 'both'):
    """
    Print an error message.
    """
    base_print(message, color=Fore.RED, emoji_code="\u274C",
               position=position)


def print_warning(message, position: EmojiPosition = 'both'):
    """
    Print a warning message.
    """
    base_print(message, color=Fore.YELLOW,
               emoji_code=":warning:", position=position)


def print_success(message, position: EmojiPosition = 'both'):
    """
    Print a success message.
    """
    base_print(message, color=Fore.GREEN, emoji_code="\u2705",
               position=position)

########################################################################


def printJSON(content: dict | Any, indent=1, width=80, depth=None, compact=False,):
    """Pretty-print a Python object to a stream [default is sys.stdout]."""
    pprint.pprint(content, indent=indent, width=width,
                  depth=depth, compact=compact)


def printBytes(): pass


def printBytesArray(): pass


def printDataClass(): pass


def printTuple(): pass


########################################################################

def get_toggle_kwargs(key: str, kwargs: dict,):
    if key not in kwargs:
        return True
    else:
        return kwargs[key]


class PrettyPrinter:

    @staticmethod
    def cache(func: Callable) -> Callable:

        @wraps(func)
        def wrapper(*args, **kwargs):
            saveable = get_toggle_kwargs('saveable', kwargs)

            if 'show' not in kwargs:
                kwargs['show'] = True

            self: PrettyPrinter = args[0]
            if saveable:
                kwargs_prime = kwargs.copy()
                kwargs_prime['saveable'] = False
                kwargs_prime['show'] = True
                self.buffer.append(
                    {'func': func, 'args': args, 'kwargs': kwargs_prime,'now':dt.datetime.now()})
            return func(*args, **kwargs)
        return wrapper

    @staticmethod
    def if_show(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            show = get_toggle_kwargs('show', kwargs)
            if show:
                return func(*args, **kwargs)
            return

        return wrapper

    def __init__(self):
        self.buffer: list[Callable] = []

    @if_show
    @cache
    def warning(self, message: str, show: bool = True, saveable: bool = True, position: EmojiPosition = 'both'):
        print_warning(message, position)
    @if_show
    @cache
    def error(self, message: str, show: bool = True, saveable: bool = True, position: EmojiPosition = 'both'):
        print_error(message, position)

    @if_show
    @cache
    def message(self, message: str, show: bool = True, saveable: bool = True, position: EmojiPosition = 'both'):
        print_message(message, position)

    @if_show
    @cache
    def info(self, message: str, show: bool = True, saveable: bool = True, position: EmojiPosition = 'both'):
        print_info(message, position)

    @if_show
    @cache
    def success(self, message: str, show: bool = True, saveable: bool = True, position: EmojiPosition = 'both'):
        print_success(message, position)

    @if_show
    @cache
    def custom_message(self, message:str, color:str=Fore.WHITE, background:str=Back.RESET, emoji_code=":speech_balloon:", show=True, saveable=True, position: EmojiPosition = 'both'):
            base_print(message, color, background, emoji_code, position)
    @if_show
    @cache
    def json(self, content:Any, indent=1, width=80, depth=None, compact=False, show:bool=True, saveable:bool=True,):
        printJSON(content, indent, width, depth, compact)

    @if_show
    @cache
    def space_line(self, show: bool = True, saveable: bool = True):
        print()

    def clearScreen(self):
        clearscreen()

    def clearline(self):
        clearline()

    def show(self, pause_after=1, title='Communication - Service', pause_before=0, color=Fore.WHITE, clear_screen_after=False, print_stack=True, clear_stack=False, space_line=False):
        """
        Display the ASCII art title and optionally print the stack buffer.

        This function clears the screen, sets a title, displays ASCII art, and can print
        the contents of the stack buffer. It also provides options for pausing, clearing
        the stack, and adding space lines.

        Parameters:
        `pause_after` (float): Time to pause after displaying content (default: 1 second)
        `title` (str): The title to set for the console window (default: 'Communication - Service')
        `pause_before` (float): Time to pause before displaying content (default: 0 seconds)
        `color` (str): The color to use for the ASCII art (default: Fore.WHITE)
        `clear_screen_afte`r (bool): Whether to clear the screen after displaying (default: False)
        `print_stack` (bool): Whether to print the contents of the stack buffer (default: True)
        `clear_stack `(bool): Whether to clear the stack buffer after printing (default: False)
        `space_line` (bool): Whether to add a space line after printing (default: False)

        Returns:
        None
        """
        time.sleep(pause_before)
        self.clearScreen()
        settitle(title)
        base_print(ascii_art, color=color, emoji_code='')
        if clear_stack:
            self.clear_buffer()
        if print_stack:
            self.print_stack_buffer()
        if space_line:
            self.space_line()
        time.sleep(pause_after)
        if clear_screen_after:
            self.clearScreen()

    def print_stack_buffer(self):
        for item in self.buffer:
            item['func'](*item['args'], **item['kwargs'])

    def clear_buffer(self):
        self.buffer = []

    def setLayout(self):
        ...

    def wait(self, timeout: float, press_to_continue: bool = True):
        time.sleep(timeout)
        if press_to_continue:
            self.warning('Press to continue', saveable=False, position='both')
            input('')
        clear_line()

    def input(self, message: str, color=Fore.WHITE, emoji_code: str = '', position: EmojiPosition = 'none') -> None | str:
        try:
            message = base_message(
                message, color, emoji_code=emoji_code, position=position,)
            return input(message)

        except KeyboardInterrupt:
            return None

        except EOFError:
            raise SkipInputException


PrettyPrinter_: PrettyPrinter = PrettyPrinter()


def TemporaryPrint(func: Callable):

    @wraps(func)
    def wrapper(*args, **kwargs):
        PrettyPrinter_.show(print_stack=False)
        result = func(*args, **kwargs)
        PrettyPrinter_.show(print_stack=True)
        return result
    return wrapper

########################################################################
