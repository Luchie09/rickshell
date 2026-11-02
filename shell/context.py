"""State shared by the shell and its commands."""

import os


class ShellContext:
    """Stores the current state of a shell session."""

    def __init__(self) -> None:
        self.cwd: str = os.path.abspath(os.getcwd())
        self.start_dir: str = self.cwd
        self.variables: dict[str, str] = {}
        self.permissions: dict[str, int] = {}
        self.last_exit_code: int = 0
        self.easter_eggs: bool = True
        self.running: bool = True
