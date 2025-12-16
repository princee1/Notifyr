import os
import colorama
from colorama import Fore, Back, Style
from colorama.ansi import clear_line, set_title 
import emoji
from typing import Any, Callable, List, Literal, Optional, Dict
import pprint
import time
from functools import wraps
import datetime as dt

# --- Type Aliases ---
EmojiPosition = Literal['left', 'right', 'both', 'none']

# Initialize colorama
colorama.init(autoreset=True)

pprinter = pprint.PrettyPrinter()

########################################################################
custom_ascii_art = r"""
  ___     _   __          __     _     ____                            ___                     ___ 
 /__ \   / | / /  ____   / /_   (_)   / __/   __  __   _____          /   |    ____     ____  /__ \
  / _/  /  |/ /  / __ \ / __/  / /   / /_    / / / /  / ___/         / /| |   / __ \   / __ \  / _/
 /_/   / /|  /  / /_/ // /_   / /   / __/   / /_/ /  / /            / ___ |  / /_/ /  / /_/ / /_/  
(_)   /_/ |_/   \____/ \__/  /_/   /_/      \__, /  /_/            /_/  |_| / .___/  / .___/ (_)   
                                           /____/                          /_/      /_/            
"""

justify = 'left'
ascii_art = custom_ascii_art

def justify_ascii_art(art: str, justify: str, width: int = 80) -> str:
    lines = art.splitlines()
    if justify == 'center':
        return '\n'.join(line.center(width) for line in lines)
    elif justify == 'right':
        return '\n'.join(line.rjust(width) for line in lines)
    return art # 'left' or 'none'

ascii_art = justify_ascii_art(ascii_art, justify, width=80)


def show(t: float = 10, title: str = 'Communication - Service', t1: float = 0, color: str = Fore.WHITE):
    """
    Displays the ASCII art title for a specified duration.
    """
    time.sleep(t1)
    clearscreen()
    settitle(title)
    base_print(ascii_art, color=color, emoji_code='', position='none') # position='none' is more appropriate for a banner
    time.sleep(t)


class SkipInputException(Exception):
    """Exception raised when an input is skipped."""
    ...

########################################################################
# --- Utility Functions ---

def settitle(title: str):
    """Set the console window title."""
    set_title(title)


def clearline(): 
    """Clear the current line in the console."""
    clear_line()


def clearscreen():
    """Clear the entire console screen."""
    # Note: clear_screen() from colorama is often less reliable than os.system
    if os.name == 'nt':
        os.system('cls')  
    else:
        os.system('clear')


def base_message(message: str, color: str = Fore.WHITE, background: str = Back.RESET, emoji_code: str = ":speech_balloon:", position: EmojiPosition = 'both') -> str:
    """
    Base function to return a personalized message string with color and emoji.
    """
    # Check if we are using an emojize shortcut (e.g., :smile:) or a direct character (e.g., \u2705)
    is_emojized = emoji_code.startswith(':') and emoji_code.endswith(':')
    _emoji = emoji.emojize(emoji_code, language='en') if is_emojized else emoji_code
    
    # Construct the message parts
    left_emoji = _emoji + "  " if (position == "left" or position == "both") and _emoji else ""
    right_emoji = "  " + _emoji if (position == "right" or position == "both") and _emoji else ""

    return color + background + left_emoji + message + right_emoji + Style.RESET_ALL


def base_print(message: str, color: str = Fore.WHITE, background: str = Back.RESET, emoji_code: str = ":speech_balloon:", position: EmojiPosition = 'both'):
    """
    Base function to print a personalized message with color and emoji.
    """
    print(base_message(message, color, background, emoji_code, position))

# --- Standard Print Functions ---

def print_info(message: str, position: EmojiPosition = 'both'):
    """Print an info message."""
    base_print(message, color=Fore.BLUE, emoji_code=":information:", position=position)


def print_message(message: str, position: EmojiPosition = 'both'):
    """Print a general message."""
    # Using the unicode character directly for consistency, or standard shortcut
    base_print(message, color=Fore.WHITE, emoji_code='\U0001F4AC', position=position)


def print_error(message: str, position: EmojiPosition = 'both'):
    """Print an error message."""
    base_print(message, color=Fore.RED, emoji_code="\u274C", position=position)


def print_warning(message: str, position: EmojiPosition = 'both'):
    """Print a warning message."""
    base_print(message, color=Fore.YELLOW, emoji_code=":warning:", position=position)


def print_success(message: str, position: EmojiPosition = 'both'):
    """Print a success message."""
    base_print(message, color=Fore.GREEN, emoji_code="\u2705", position=position)

########################################################################
# --- Data Printing Functions ---

def printJSON(content: Dict[str, Any] | Any, indent: int = 1, width: int = 80, depth: Optional[int] = None, compact: bool = False):
    """Pretty-print a Python object to a stream [default is sys.stdout]."""
    pprint.pprint(content, indent=indent, width=width, depth=depth, compact=compact)


# Functions that were placeholders, kept as is
def printBytes(): pass
def printBytesArray(): pass
def printDataClass(): pass
def printTuple(): pass


########################################################################
# --- PrettyPrinter Class ---

def get_toggle_kwargs(key: str, kwargs: Dict[str, Any], default_value: bool = True) -> bool:
    """Helper to safely extract a boolean toggle from kwargs."""
    return kwargs.get(key, default_value)


class PrettyPrinter:
    
    @staticmethod
    def cache(func: Callable) -> Callable:
        """Decorator to cache print calls into the buffer."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            # args[0] is 'self' instance
            self: PrettyPrinter = args[0]
            saveable = get_toggle_kwargs('saveable', kwargs)

            # Ensure 'show' is in kwargs for the cache logic (default True)
            if 'show' not in kwargs:
                kwargs['show'] = True

            if saveable:
                # Store a copy of the arguments/kwargs to be used later
                kwargs_prime = kwargs.copy()
                kwargs_prime['saveable'] = False # Prevent recursive caching
                kwargs_prime['show'] = True # Always show when re-printing the stack
                 
                self.buffer.append(
                    {'func': func, 
                     'args': args, # store original args including self
                     'kwargs': kwargs_prime, 
                     'now': dt.datetime.now()
                    }
                )
            
            return func(*args, **kwargs)
        return wrapper

    @staticmethod
    def if_show(func: Callable) -> Callable:
        """Decorator to skip execution if 'show' is False in kwargs."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            show = get_toggle_kwargs('show', kwargs)
            if show:
                return func(*args, **kwargs)
            return

        return wrapper

    def __init__(self):
        """Initialize the buffer and quiet state."""
        # The buffer stores Dicts, not just Callables, so the type hint is updated
        self.buffer: List[Dict[str, Any]] = [] 
        self.quiet: bool = False

    # --- Print Methods (Decorated) ---
    @if_show
    @cache
    def warning(self, message: str, show: bool = True, saveable: bool = False, position: EmojiPosition = 'both'):
        if not self.quiet:
            print_warning(message, position)
            
    @if_show
    @cache
    def error(self, message: str, show: bool = True, saveable: bool = False, position: EmojiPosition = 'both'):
        if not self.quiet:
            print_error(message, position)

    @if_show
    @cache
    def message(self, message: str, show: bool = True, saveable: bool = False, position: EmojiPosition = 'both'):
        if not self.quiet:
            print_message(message, position)

    @if_show
    @cache
    def info(self, message: str, show: bool = True, saveable: bool = False, position: EmojiPosition = 'both'):
        if not self.quiet:
            print_info(message, position)

    @if_show
    @cache
    def success(self, message: str, show: bool = True, saveable: bool = False, position: EmojiPosition = 'both'):
        if not self.quiet:
            print_success(message, position)

    @if_show
    @cache
    def custom_message(self, message:str, color:str=Fore.WHITE, background:str=Back.RESET, emoji_code:str=":speech_balloon:", show:bool=True, saveable:bool=True, position: EmojiPosition = 'both'):
        if not self.quiet:
            base_print(message, color, background, emoji_code, position)
            
    @if_show
    @cache
    def json(self, content:Any, indent:int=1, width:int=80, depth:Optional[int]=None, compact:bool=False, show:bool=True, saveable:bool=True,):
        if not self.quiet:
            printJSON(content, indent, width, depth, compact)

    @if_show
    @cache
    def space_line(self, show: bool = True, saveable: bool = False):
        if not self.quiet:
            print()

    # --- Control Methods ---
    def clearScreen(self):
        """Wrapper for clearscreen utility function."""
        clearscreen()

    def clearline(self):
        """Wrapper for clearline utility function."""
        clear_line()

    def show(self, pause_after: float = 1, title: str = 'Communication - Service', pause_before: float = 0, color: str = Fore.WHITE, clear_screen_after: bool = False, print_stack: bool = False, clear_stack: bool = True, space_line: bool = False):
        """
        Display the ASCII art title and optionally print the stack buffer.
        """
        time.sleep(pause_before)
        self.clearScreen()
        settitle(title)
        # Use position='none' for the banner title
        base_print(ascii_art, color=color, emoji_code='', position='none') 
        
        if print_stack:
            self.print_stack_buffer()
        
        if clear_stack:
            self.clear_buffer()
            
        if space_line:
            self.space_line(saveable=False, show=True) # Not added to the cache

        time.sleep(pause_after)
        
        if clear_screen_after:
            self.clearScreen()

    def print_stack_buffer(self):
        """Replay all saved print calls in the buffer."""
        for item in self.buffer:
            # Replay the function call with original args (including self) and modified kwargs
            item['func'](*item['args'], **item['kwargs'])

    def clear_buffer(self):
        """Clear the cache buffer."""
        self.buffer = []

    def setLayout(self):
        """Placeholder for layout function."""
        ...

    def wait(self, timeout: float, press_to_continue: bool = True):
        """Wait for a timeout or a user input."""
        time.sleep(timeout)
        if press_to_continue:
            # Pass saveable=False so this wait message isn't cached/reprinted
            self.warning('Press Enter to continue...', saveable=False, position='both')
            try:
                # Use standard input for non-cached interaction
                input('') 
            except (KeyboardInterrupt, EOFError):
                self.info(message='Exiting gracefully')
                exit(0)
        clear_line()

    def input(self, message: str, color: str = Fore.WHITE, emoji_code: str = '', position: EmojiPosition = 'none') -> Optional[str]:
        """Custom input function with color and emoji support."""
        try:
            # Generate the colored/emojized prompt string
            prompt_message = base_message(message, color, emoji_code=emoji_code, position=position)
            return input(prompt_message)

        except KeyboardInterrupt:
            # Handle Ctrl+C
            return None

        except EOFError:
            # Handle Ctrl+D (or equivalent)
            raise SkipInputException


PrettyPrinter_: PrettyPrinter = PrettyPrinter()


def TemporaryPrint(func: Callable):
    """
    Decorator to wrap a function call with a screen-clear, 
    show the banner, run the function, and then show the banner 
    again with the restored stack.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # 1. Show banner without printing the cached stack
        PrettyPrinter_.show(print_stack=False) 
        
        # 2. Execute the wrapped function
        result = func(*args, **kwargs)
        
        # 3. Show banner *with* the cached stack
        PrettyPrinter_.show(print_stack=False) 
        return result
    return wrapper

########################################################################