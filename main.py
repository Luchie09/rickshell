"""Start the Rick Shell command loop."""

from shell.context import ShellContext
from shell.repl import run


def main() -> None:
    run(ShellContext())


if __name__ == "__main__":
    main()
