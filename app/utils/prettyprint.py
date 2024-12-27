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


EmojiPosition = Literal['before', 'after', 'both', 'none']
# Initialize colorama
colorama.init(autoreset=True)

pprinter = pprint.PrettyPrinter()


def settitle(tilte: str):
    set_title(tilte)


def clearline(): clear_line()


def clearscreen(): os.system('cls')  # clear_screen()


def print_message(message, color=Fore.WHITE, background=Back.RESET, emoji_code=":speech_balloon:", emoji_position: EmojiPosition = 'both'):
    """
    Base function to print a personalized message with color and emoji.
    """
    print(color + background + (emoji.emojize(emoji_code) if emoji_position == "before" or emoji_position == "both" else "") + "  " +
          message + "  " + (emoji.emojize(emoji_code) if emoji_position == "after" or emoji_position == "both" else "") + Style.RESET_ALL)


def print_info(message,emoji_position:EmojiPosition='both'):
    """
    Print an info message.
    """
    print_message(message, color=Fore.BLUE, emoji_code=":information:",emoji_position=emoji_position)


def print_error(message,emoji_position:EmojiPosition='both'):
    """
    Print an error message.
    """
    print_message(message, color=Fore.RED, emoji_code=":x:",emoji_position=emoji_position)


def print_warning(message,emoji_position:EmojiPosition='both'):
    """
    Print a warning message.
    """
    print_message(message, color=Fore.YELLOW, emoji_code=":warning:",emoji_position=emoji_position)


def print_success(message,emoji_position:EmojiPosition='both'):
    """
    Print a success message.
    """
    print_message(message, color=Fore.GREEN, emoji_code=":white_check_mark:",emoji_position=emoji_position)


def printJSON(content: dict | Any, indent=1, width=80, depth=None, compact=False,):
    """Pretty-print a Python object to a stream [default is sys.stdout]."""
    pprint.pprint(content, indent=indent, width=width,
                  depth=depth, compact=compact)


def printBytes(): pass


def printBytesArray(): pass


def printDataClass(): pass


def printTuple(): pass


class PrettyPrinter:

    @staticmethod
    def cache(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            saveable =kwargs['saveable']
            self = args[0]
            if saveable:
                kwargs['saveable'] = False
                self.buffer.append({'func': func, 'args': args, 'kwargs': kwargs})
            func(*args, **kwargs)
        return wrapper

    def __init__(self):
        self.buffer: list[Callable] = []

    @cache
    def warning(self, message,saveable =False,emoji_position:EmojiPosition='both'):
        print_warning(message,emoji_position)

    @cache
    def error(self, message,saveable =False,emoji_position:EmojiPosition='both'):
        print_error(message,emoji_position)

    @cache
    def info(self, message,saveable =False,emoji_position:EmojiPosition='both'):
        print_info(message,emoji_position)

    @cache
    def success(self, message,saveable =False,emoji_position:EmojiPosition='both'):
        print_success(message,emoji_position)

    @cache
    def custom_message(self, message, color=Fore.WHITE, background=Back.RESET, emoji_code=":speech_balloon:",saveable =False, emoji_position: EmojiPosition = 'both'):
        print_message(message, color, background, emoji_code, emoji_position)

    @cache
    def json(self, content, indent=1, width=80, depth=None, compact=False,saveable =False,):
        printJSON(content, indent, width, depth, compact)

    def clearScreen(self):
        clearscreen()

    def clearline(self):
        clearline()

    def show(self):
        ...

    def print_stack_buffer(self):
        for item in self.buffer:
            item['func'](*item['args'], **item['kwargs'])

    def clear_buffer(self):
        self.buffer = []


PrettyPrinter_: PrettyPrinter = PrettyPrinter()

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
    print_message(ascii_art, color=color, emoji_code='')
    time.sleep(t)
    # clearscreen()
