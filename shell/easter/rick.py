"""Render the live Rick animation in a terminal."""

import re
import shutil
import time
import urllib.request
from typing import Callable, TextIO

LIVE_URL = "https://ascii.live/rick"
ENTER_ANIMATION = "\x1b[?1049h\x1b[2J\x1b[H\x1b[?25l"
RESTORE_TERMINAL = "\x1b[0m\x1b[?25h\x1b[?1049l"
_ANSI_ESCAPE = re.compile(
    r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\)|[@-_])"
)
_CURSOR_HOME = b"\x1b[H"
_CLEAR_SCREEN = b"\x1b[2J"


def is_terminal(stream: TextIO) -> bool:
    """Return whether a stream is a terminal, treating missing checks as false."""
    try:
        return stream.isatty()
    except Exception:
        return False


def _write_frame(stdout: TextIO, frame: str) -> None:
    """Strip controls, scale a frame to the current terminal, and draw it."""
    frame = _ANSI_ESCAPE.sub("", frame)
    lines = frame.splitlines()
    if not lines:
        return

    size = shutil.get_terminal_size()
    available_rows = max(1, size.lines - 1)
    available_columns = max(1, size.columns)
    width = max(len(line) for line in lines)
    scale = max(
        (len(lines) + available_rows - 1) // available_rows,
        (width + available_columns - 1) // available_columns,
    )
    if scale > 1:
        lines = [
            line[::scale]
            for line in lines[::scale]
        ]
    stdout.write("\x1b[H" + "\n".join(lines))
    stdout.flush()


def _stream_live(
    stdout: TextIO,
    duration: float | None = None,
    timeout: float = 3,
    on_start: Callable[[], None] | None = None,
) -> None:
    """Buffer and draw complete cursor-home-delimited live frames."""
    received_data = False
    deadline = None if duration is None else time.monotonic() + duration
    pending = bytearray()
    request = urllib.request.Request(
        LIVE_URL,
        headers={"User-Agent": "curl/8.0", "Accept": "*/*"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        status = getattr(response, "status", 200)
        if status < 200 or status >= 300:
            raise OSError("bad response")

        started = False
        while deadline is None or time.monotonic() < deadline:
            chunk = response.read(4096)
            if not chunk:
                break
            if deadline is not None and time.monotonic() >= deadline:
                break
            received_data = True
            if isinstance(chunk, bytes):
                pending.extend(chunk)
            elif isinstance(chunk, str):
                pending.extend(chunk.encode("utf-8", errors="replace"))
            else:
                raise OSError("bad response")

            pending = bytearray(bytes(pending).replace(_CLEAR_SCREEN, b""))
            while True:
                marker = pending.find(_CURSOR_HOME)
                if marker < 0:
                    break
                if marker:
                    del pending[:marker]
                next_marker = pending.find(_CURSOR_HOME, len(_CURSOR_HOME))
                if next_marker < 0:
                    break
                frame_bytes = pending[len(_CURSOR_HOME):next_marker]
                frame = frame_bytes.decode("utf-8", errors="replace")
                if not frame.strip() or not _ANSI_ESCAPE.sub("", frame).strip():
                    del pending[:next_marker]
                    continue
                if not started:
                    if on_start is None:
                        raise OSError("animation start handler is missing")
                    on_start()
                    started = True
                _write_frame(stdout, frame)
                del pending[:next_marker]

        if not received_data or not started:
            raise OSError("empty or invalid stream")


def _play(
    stdout: TextIO,
    duration: float | None,
    stream_timeout: float = 3,
    show_hint: bool = False,
) -> None:
    """Stream on a TTY and restore the screen only after playback starts."""
    if not is_terminal(stdout):
        return

    screen_started = False

    def start_animation() -> None:
        nonlocal screen_started
        if show_hint:
            stdout.write("Press Ctrl+C to stop\n")
            stdout.flush()
        screen_started = True
        stdout.write(ENTER_ANIMATION)
        stdout.flush()

    try:
        _stream_live(stdout, duration, stream_timeout, start_animation)
    except KeyboardInterrupt:
        pass
    except Exception:
        pass
    finally:
        if screen_started:
            try:
                stdout.write(RESTORE_TERMINAL)
                stdout.flush()
            except Exception:
                pass


def play_rick(stdout: TextIO) -> None:
    """Stream the live animation until interrupted."""
    _play(stdout, None, stream_timeout=3, show_hint=True)
