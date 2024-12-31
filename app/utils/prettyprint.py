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


########################################################################


def settitle(tilte: str):
    set_title(tilte)


def clearline(): clear_line()


def clearscreen(): 
    if os.name == 'nt':
        os.system('cls')  # clear_screen()
    else:
        os.system('clear')


def print_message(message, color=Fore.WHITE, background=Back.RESET, emoji_code=":speech_balloon:", position: EmojiPosition = 'both'):
    """
    Base function to print a personalized message with color and emoji.
    """
    is_emojized = emoji_code.startswith(':')
    print(color + background + ((emoji.emojize(emoji_code) if is_emojized else emoji_code)if position == "before" or position == "both" else "") + "  " +
          message + "  " + ((emoji.emojize(emoji_code) if is_emojized else emoji_code) if position == "after" or position == "both" else "") + Style.RESET_ALL)


def print_info(message, position: EmojiPosition = 'both'):
    """
    Print an info message.
    """
    print_message(message, color=Fore.BLUE,
                  emoji_code=":information:", position=position)


def print_error(message, position: EmojiPosition = 'both'):
    """
    Print an error message.
    """
    print_message(message, color=Fore.RED, emoji_code=":x:",
                  position=position)


def print_warning(message, position: EmojiPosition = 'both'):
    """
    Print a warning message.
    """
    print_message(message, color=Fore.YELLOW,
                  emoji_code=":warning:", position=position)


def print_success(message, position: EmojiPosition = 'both'):
    """
    Print a success message.
    """
    print_message(message, color=Fore.GREEN, emoji_code="\u2705",
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


class PrettyPrinter:

    @staticmethod
    def cache(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if 'saveable' not in kwargs:
                saveable = True
            else:
                saveable = kwargs['saveable']
            self: PrettyPrinter = args[0]
            if saveable:
                kwargs['saveable'] = False
                self.buffer.append(
                    {'func': func, 'args': args, 'kwargs': kwargs})
            func(*args, **kwargs)
        return wrapper

    def __init__(self):
        self.buffer: list[Callable] = []

    @cache
    def warning(self, message, saveable=True, position: EmojiPosition = 'both'):
        print_warning(message, position)

    @cache
    def error(self, message, saveable=True, position: EmojiPosition = 'both'):
        print_error(message, position)

    @cache
    def info(self, message, saveable=True, position: EmojiPosition = 'both'):
        print_info(message, position)

    @cache
    def success(self, message, saveable=True, position: EmojiPosition = 'both'):
        print_success(message, position)

    @cache
    def custom_message(self, message, color=Fore.WHITE, background=Back.RESET, emoji_code=":speech_balloon:", saveable=True, position: EmojiPosition = 'both'):
        print_message(message, color, background, emoji_code, position)

    @cache
    def json(self, content, indent=1, width=80, depth=None, compact=False, saveable=True,):
        printJSON(content, indent, width, depth, compact)

    @cache
    def space_line(self, saveable=True):
        print()

    def clearScreen(self):
        clearscreen()

    def clearline(self):
        clearline()

    def show(self, pause_after=1, title='Communication - Service', pause_before=0, color=Fore.WHITE, clear_screen_after=False, print_stack=True, clear_stack=False, space_line=False):
        time.sleep(pause_before)
        self.clearScreen()
        settitle(title)
        print_message(ascii_art, color=color, emoji_code='')
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
    
    def wait(self, timeout:float,press_to_continue:bool = True):
        time.sleep(timeout)
        if press_to_continue:
            self.warning('Press to continue',saveable=False,position ='left')
            input('')
        clear_line()


PrettyPrinter_: PrettyPrinter = PrettyPrinter()

########################################################################
