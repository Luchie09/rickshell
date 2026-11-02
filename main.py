"""Start the Rick Shell command loop."""

import os

from shell.context import ShellContext
from shell.repl import run


def main() -> None:
    os.system("")
    run(ShellContext())


if __name__ == "__main__":
    main()
