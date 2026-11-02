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
from shell.builtins import system as _system
from sim.commands import cmd_sched
from sim.commands import cmd_deadlock
from compare.compare import cmd_compare

REGISTRY["sched"] = cmd_sched
REGISTRY["deadlock"] = cmd_deadlock
REGISTRY["compare"] = cmd_compare
