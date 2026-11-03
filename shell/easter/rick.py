"""Original ASCII dancer and the optional live Rick animation.

The local frame file stores four frames separated by a line containing `---`.
"""

import os
import re
import shutil
import time
import urllib.request
from typing import TextIO

LIVE_URL = "https://ascii.live/rick"
ENTER_ANIMATION = "\x1b[?1049h\x1b[2J\x1b[H\x1b[?25l"
RESTORE_TERMINAL = "\x1b[0m\x1b[?25h\x1b[?1049l"
_ANSI_ESCAPE = re.compile(
    r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\)|[@-_])"
)
_CURSOR_HOME = b"\x1b[H"
_CLEAR_SCREEN = b"\x1b[2J"


def _default_frames_path() -> str:
    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    return os.path.join(project_root, "data", "rick_frames.txt")


def load_frames(path: str | None = None) -> list[str]:
    """Load dance frames; missing or unreadable files produce no frames."""
    frames: list[str] = []
    current: list[str] = []
    try:
        with open(path or _default_frames_path(), "r", encoding="utf-8") as file:
            for line in file:
                line = line.rstrip("\r\n")
                if line == "---":
                    if current:
                        frames.append("\n".join(current))
                        current = []
                else:
                    current.append(line)
    except (OSError, UnicodeError):
        return []

    if current:
        frames.append("\n".join(current))
    return frames


def is_terminal(stream: TextIO) -> bool:
    """Return whether a stream is a terminal, treating missing checks as false."""
    try:
        return stream.isatty()
    except Exception:
        return False


def _print_frame(stdout: TextIO, frames: list[str], frame_number: int) -> None:
    """Draw one saved frame from the top-left of the animation screen."""
    _write_frame(stdout, frames[frame_number % len(frames)])


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


def _silent_timed_dance(
    stdout: TextIO,
    frames: list[str],
    duration: float | None,
) -> None:
    """Play saved frames at about ten frames per second."""
    deadline = None if duration is None else time.monotonic() + duration
    frame_number = 0
    while deadline is None or time.monotonic() < deadline:
        _print_frame(stdout, frames, frame_number)
        frame_number += 1
        if deadline is None:
            time.sleep(0.1)
        else:
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(0.1, remaining))


def _stream_live(
    stdout: TextIO,
    duration: float | None = None,
    timeout: float = 3,
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
                _write_frame(stdout, frame)
                del pending[:next_marker]

    if not received_data:
        raise OSError("empty stream")


def _play(
    stdout: TextIO,
    frames_path: str | None,
    duration: float | None,
    use_live_stream: bool,
    stream_timeout: float = 3,
) -> None:
    """Play on a TTY, restoring the prompt screen even when interrupted."""
    if not is_terminal(stdout):
        return

    try:
        stdout.write(ENTER_ANIMATION)
        stdout.flush()
        if use_live_stream:
            try:
                _stream_live(stdout, duration, stream_timeout)
                return
            except KeyboardInterrupt:
                return
            except Exception:
                pass

        frames = load_frames(frames_path)
        if frames:
            _silent_timed_dance(stdout, frames, duration)
    except KeyboardInterrupt:
        pass
    except Exception:
        pass
    finally:
        try:
            stdout.write(RESTORE_TERMINAL)
            stdout.flush()
        except Exception:
            pass


def play_rick(stdout: TextIO, frames_path: str | None = None) -> None:
    """Stream the live animation until interrupted, with a saved-frame fallback."""
    if not is_terminal(stdout):
        return
    try:
        stdout.write("Press Ctrl+C to stop\n")
        stdout.flush()
    except Exception:
        return
    _play(stdout, frames_path, None, use_live_stream=True)


def play_silent(
    stdout: TextIO,
    frames_path: str | None = None,
    duration: float = 2.0,
) -> None:
    """Play only the saved dancer for a bounded automatic trigger."""
    _play(
        stdout,
        frames_path,
        duration,
        use_live_stream=False,
    )
