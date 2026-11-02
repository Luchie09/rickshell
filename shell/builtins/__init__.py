"""Built-in command registry."""

from collections.abc import Callable
from typing import TextIO

from shell.context import ShellContext

Command = Callable[[list[str], TextIO, TextIO, TextIO, ShellContext], int]
REGISTRY: dict[str, Command] = {}


def register(name: str) -> Callable[[Command], Command]:
    """Register a command function under the given command name."""

    def decorator(command: Command) -> Command:
        REGISTRY[name] = command
        return command

    return decorator


# Import built-ins after register is defined so their decorators can populate the registry.
from shell.builtins import files as _files
from shell.builtins import perms as _perms
from shell.builtins import search as _search
