import rich
from time import sleep
import os
import sys
import colorama
from colorama import Fore, Back, Style
from colorama.ansi import clear_line, clear_screen,set_title
import emoji
from typing import Any
import pprint

# Initialize colorama
colorama.init(autoreset=True)

pprinter = pprint.PrettyPrinter()


def settitle(tilte:str):
    set_title(tilte)

def clearline(): clear_line()


def clearscreen(): clear_screen()


def print_message(message, color=Fore.WHITE, background=Back.RESET, emoji_code=":speech_balloon:"):
    """
    Base function to print a personalized message with color and emoji.
    """
    print(color + background + emoji.emojize(emoji_code) + " " +
          message + " " + emoji.emojize(emoji_code) + Style.RESET_ALL)


def print_info(message):
    """
    Print an info message.
    """
    print_message(message, color=Fore.BLUE, emoji_code=":information_source:")


def print_error(message):
    """
    Print an error message.
    """
    print_message(message, color=Fore.RED, emoji_code=":x:")


def print_warning(message):
    """
    Print a warning message.
    """
    print_message(message, color=Fore.YELLOW, emoji_code=":warning:")


def print_success(message):
    """
    Print a success message.
    """
    print_message(message, color=Fore.GREEN, emoji_code=":white_check_mark:")


def printJSON(content: dict | Any, indent=1, width=80, depth=None, compact=False,):
    """Pretty-print a Python object to a stream [default is sys.stdout]."""
    pprint.pprint(content, indent=indent, width=width,
                  depth=depth, compact=compact)


def printBytes(): pass


def printBytesArray(): pass


def printDataClass(): pass


def printTuple(): pass


class PrettyPrinter:

    def warning(self, message):
        print_warning(message)

    def error(self, message):
        print_error(message)

    def info(self, message):
        print_info(message)

    def success(self, message):
        print_success(message)

    def custom_message(self, message, color=Fore.WHITE, background=Back.RESET, emoji_code=":speech_balloon:"):
        print_message(message, color, background, emoji_code)

    def json(self, content, indent=1, width=80, depth=None, compact=False):
        printJSON(content, indent, width, depth, compact)

    def clearScreen(self):
        clearscreen()

    def clearline(self):
        clearline()

PrettyPrinter_:PrettyPrinter = PrettyPrinter()