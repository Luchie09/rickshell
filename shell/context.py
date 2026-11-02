"""State shared by the shell and its commands."""

import os


class ShellContext:
    """Stores the current state of a shell session."""

    def __init__(self) -> None:
        self.cwd: str = os.getcwd()
        self.variables: dict[str, str] = {}
        self.last_exit_code: int = 0
        self.easter_eggs: bool = True
        self.running: bool = True
