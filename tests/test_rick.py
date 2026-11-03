"""Tests for TTY-only live and saved Rick animations."""

import io
import os
import sys
import unittest
import urllib.request
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from shell.builtins.system import cmd_rick
from shell.context import ShellContext
from shell.easter import rick
from shell.repl import run


class TTYStringIO(io.StringIO):
    def isatty(self) -> bool:
        return True


class RecordingTTYStringIO(TTYStringIO):
    def __init__(self) -> None:
        super().__init__()
        self.write_calls: list[str] = []

    def write(self, text: str) -> int:
        self.write_calls.append(text)
        return super().write(text)


class RickTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = ShellContext()

    @staticmethod
    def response(chunks: list[bytes], status: int = 200) -> MagicMock:
        response = MagicMock()
        response.status = status
        response.read.side_effect = chunks
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        return response

    def test_frame_loading(self) -> None:
        frames = rick.load_frames()
        self.assertEqual(len(frames), 4)
        self.assertIn("o", frames[0])

    def test_live_rick_streams_to_tty_and_restores_screen(self) -> None:
        output = RecordingTTYStringIO()
        response = self.response(
            [
                b"\x1b[2J\x1b[H\x1b[31mlive ",
                b"frame\x1b[0m\x1b[Hsecond frame\x1b[H",
                b"",
            ]
        )
        with (
            patch("urllib.request.urlopen", return_value=response) as urlopen,
        ):
            result = cmd_rick([], io.StringIO(), output, io.StringIO(), self.context)

        self.assertEqual(result, 0)
        self.assertTrue(output.getvalue().startswith("Press Ctrl+C to stop\n"))
        self.assertIn(rick.ENTER_ANIMATION, output.getvalue())
        self.assertIn("live frame", output.getvalue())
        self.assertIn("second frame", output.getvalue())
        frame_writes = [
            call for call in output.write_calls if call.startswith("\x1b[H")
        ]
        self.assertEqual(frame_writes, ["\x1b[Hlive frame", "\x1b[Hsecond frame"])
        self.assertTrue(all("\x1b[2J" not in call for call in frame_writes))
        self.assertTrue(output.getvalue().endswith(rick.RESTORE_TERMINAL))
        urlopen.assert_called_once()
        request = urlopen.call_args.args[0]
        self.assertIsInstance(request, urllib.request.Request)
        self.assertEqual(request.get_header("User-agent"), "curl/8.0")
        self.assertEqual(request.get_header("Accept"), "*/*")
        self.assertEqual(urlopen.call_args.kwargs, {"timeout": 3})

    def test_live_flag_uses_the_same_stream(self) -> None:
        output = TTYStringIO()
        response = self.response([b"\x1b[Hlive\n\x1b[H", b""])
        with (
            patch("urllib.request.urlopen", return_value=response),
        ):
            result = cmd_rick(
                ["--live"],
                io.StringIO(),
                output,
                io.StringIO(),
                self.context,
            )
        self.assertEqual(result, 0)
        self.assertIn("\x1b[Hlive", output.getvalue())

    def test_screen_restored_when_stream_is_interrupted(self) -> None:
        output = TTYStringIO()
        response = self.response([])
        response.read.side_effect = KeyboardInterrupt()
        with patch("urllib.request.urlopen", return_value=response):
            result = cmd_rick([], io.StringIO(), output, io.StringIO(), self.context)
        self.assertEqual(result, 0)
        self.assertTrue(output.getvalue().startswith("Press Ctrl+C to stop\n"))
        self.assertIn(rick.ENTER_ANIMATION, output.getvalue())
        self.assertTrue(output.getvalue().endswith(rick.RESTORE_TERMINAL))

    def test_network_errors_and_empty_stream_fall_back_to_saved_dancer(self) -> None:
        for error in (URLError("offline"), TimeoutError("timed out")):
            with self.subTest(error=error):
                output = TTYStringIO()
                with (
                    patch("urllib.request.urlopen", side_effect=error),
                    patch("shell.easter.rick.time.monotonic", side_effect=[0, 3]),
                    patch(
                        "shell.easter.rick.time.sleep",
                        side_effect=[None, KeyboardInterrupt()],
                    ),
                ):
                    rick.play_rick(output)
                self.assertTrue(
                    output.getvalue().startswith("Press Ctrl+C to stop\n")
                )
                self.assertIn(rick.ENTER_ANIMATION, output.getvalue())
                self.assertIn("\x1b[H", output.getvalue())
                self.assertTrue(output.getvalue().endswith(rick.RESTORE_TERMINAL))

        output = TTYStringIO()
        response = self.response([b""])
        with (
            patch("urllib.request.urlopen", return_value=response),
            patch("shell.easter.rick.time.monotonic", side_effect=[0, 3]),
            patch(
                "shell.easter.rick.time.sleep",
                side_effect=[None, KeyboardInterrupt()],
            ),
        ):
            rick.play_rick(output)
        self.assertIn("\x1b[H", output.getvalue())

    def test_non_tty_does_not_write_or_open_network(self) -> None:
        output = io.StringIO()
        with patch("urllib.request.urlopen") as urlopen:
            rick.play_rick(output)
        self.assertEqual(output.getvalue(), "")
        urlopen.assert_not_called()

    def test_silent_fallback_runs_until_ctrl_c(self) -> None:
        output = TTYStringIO()
        frame_calls: list[int] = []
        original_print_frame = rick._print_frame

        def stop_after_few_frames(stream, frames, frame_number):
            frame_calls.append(frame_number)
            original_print_frame(stream, frames, frame_number)
            if len(frame_calls) == 3:
                raise KeyboardInterrupt

        with (
            patch("urllib.request.urlopen", side_effect=URLError("offline")),
            patch("shell.easter.rick._print_frame", side_effect=stop_after_few_frames),
            patch("shell.easter.rick.time.sleep"),
        ):
            result = cmd_rick([], io.StringIO(), output, io.StringIO(), self.context)

        self.assertEqual(result, 0)
        self.assertEqual(len(frame_calls), 3)
        self.assertTrue(output.getvalue().endswith(rick.RESTORE_TERMINAL))

    def test_unknown_command_trigger_streams_until_interrupted(self) -> None:
        unknown_stdout = TTYStringIO()
        response = self.response([b"\x1b[Hauto frame\x1b[H"])
        response.read.side_effect = [
            b"\x1b[Hauto frame\x1b[H",
            KeyboardInterrupt(),
        ]
        stderr = io.StringIO()
        with (
            patch.object(sys, "stdin", io.StringIO("unknown-command\n")),
            patch.object(sys, "stdout", unknown_stdout),
            patch.object(sys.stdout, "isatty", return_value=True),
            patch.object(sys, "stderr", stderr),
            patch("shell.repl.time.sleep"),
            patch("urllib.request.urlopen", return_value=response) as urlopen,
        ):
            run(self.context)
        self.assertTrue(unknown_stdout.getvalue().startswith("rickshell > "))
        self.assertIn("Press Ctrl+C to stop\n", unknown_stdout.getvalue())
        self.assertIn("\x1b[Hauto frame", unknown_stdout.getvalue())
        self.assertIn(rick.RESTORE_TERMINAL, unknown_stdout.getvalue())
        self.assertTrue(unknown_stdout.getvalue().endswith("rickshell > "))
        self.assertIn("unknown-command: command not found", stderr.getvalue())
        self.assertEqual(self.context.last_exit_code, 127)
        urlopen.assert_called_once_with(unittest.mock.ANY, timeout=3)

    def test_tenth_success_trigger_is_saved_and_bounded(self) -> None:
        self.context = ShellContext()
        success_stdout = TTYStringIO()
        dance = patch("shell.easter.rick._silent_timed_dance")
        with (
            patch.object(sys, "stdin", io.StringIO("true\n" * 10)),
            patch.object(sys, "stdout", success_stdout),
            patch.object(sys.stdout, "isatty", return_value=True),
            patch.object(sys, "stderr", io.StringIO()),
            patch("urllib.request.urlopen") as urlopen,
            dance as saved_dance,
        ):
            run(self.context)
        self.assertEqual(self.context.last_exit_code, 0)
        saved_dance.assert_called_once()
        self.assertEqual(saved_dance.call_args.args[2], 2.0)
        urlopen.assert_not_called()

    def test_timed_saved_dance_stops_at_two_seconds_without_network(self) -> None:
        output = TTYStringIO()
        with (
            patch(
                "shell.easter.rick.time.monotonic",
                side_effect=[0.0, 0.0, 2.0, 2.0],
            ),
            patch("shell.easter.rick.time.sleep"),
            patch("urllib.request.urlopen") as urlopen,
        ):
            rick.play_silent(output, duration=2.0)
        self.assertIn("\x1b[H", output.getvalue())
        self.assertTrue(output.getvalue().endswith(rick.RESTORE_TERMINAL))
        urlopen.assert_not_called()

    def test_automatic_trigger_skips_network_when_disabled_or_non_tty(self) -> None:
        self.context.easter_eggs = False
        disabled_stdout = TTYStringIO()
        with (
            patch.object(sys, "stdin", io.StringIO("unknown-command\n")),
            patch.object(sys, "stdout", disabled_stdout),
            patch.object(sys, "stderr", io.StringIO()),
            patch("shell.repl._rick.play_rick") as live_dance,
            patch("shell.repl._rick.play_silent") as silent_dance,
            patch("urllib.request.urlopen") as urlopen,
        ):
            run(self.context)
        live_dance.assert_not_called()
        silent_dance.assert_not_called()
        urlopen.assert_not_called()

        self.context = ShellContext()
        self.context.easter_eggs = False
        success_stdout = TTYStringIO()
        with (
            patch.object(sys, "stdin", io.StringIO("true\n" * 10)),
            patch.object(sys, "stdout", success_stdout),
            patch.object(sys.stdout, "isatty", return_value=True),
            patch.object(sys, "stderr", io.StringIO()),
            patch("shell.repl._rick.play_silent") as silent_dance,
            patch("urllib.request.urlopen") as urlopen,
        ):
            run(self.context)
        silent_dance.assert_not_called()
        urlopen.assert_not_called()

        non_tty_context = ShellContext()
        non_tty_stdout = io.StringIO()
        with (
            patch.object(sys, "stdin", io.StringIO("unknown-command\n")),
            patch.object(sys, "stdout", non_tty_stdout),
            patch.object(sys, "stderr", io.StringIO()),
            patch("urllib.request.urlopen") as urlopen,
        ):
            run(non_tty_context)
        urlopen.assert_not_called()

    def test_oversized_frame_is_downsampled_to_terminal(self) -> None:
        output = RecordingTTYStringIO()
        frame = "\n".join(
            [
                "ABCDEFGHIJ",
                "abcdefghij",
                "0123456789",
                "klmnopqrst",
            ]
        )
        with patch(
            "shell.easter.rick.shutil.get_terminal_size",
            return_value=os.terminal_size((4, 3)),
        ):
            rick._write_frame(output, frame)
        self.assertEqual(output.write_calls, ["\x1b[HADGJ\nknqt"])
        lines = output.getvalue().removeprefix("\x1b[H").splitlines()
        self.assertLessEqual(len(lines), 2)
        self.assertTrue(all(len(line) <= 4 for line in lines))

    def test_toggle_only_controls_automatic_setting(self) -> None:
        self.context.variables["KEEP"] = "value"
        self.context.last_exit_code = 19
        stdout = io.StringIO()
        stderr = io.StringIO()
        self.assertEqual(
            cmd_rick(["off"], io.StringIO(), stdout, stderr, self.context),
            0,
        )
        self.assertFalse(self.context.easter_eggs)
        self.assertEqual(self.context.variables, {"KEEP": "value"})
        self.assertEqual(self.context.last_exit_code, 19)
        self.assertEqual(
            cmd_rick(["on"], io.StringIO(), stdout, stderr, self.context),
            0,
        )
        self.assertTrue(self.context.easter_eggs)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def test_missing_local_frames_and_bad_response_do_not_raise(self) -> None:
        output = TTYStringIO()
        with patch("urllib.request.urlopen", side_effect=URLError("offline")):
            rick.play_rick(output, "missing-rick-frames.txt")
        self.assertTrue(output.getvalue().endswith(rick.RESTORE_TERMINAL))

        output = TTYStringIO()
        response = self.response([b"bad"])
        response.status = 500
        with (
            patch("urllib.request.urlopen", return_value=response),
            patch(
                "shell.easter.rick.time.sleep",
                side_effect=KeyboardInterrupt(),
            ),
        ):
            rick.play_rick(output)
        self.assertTrue(output.getvalue().endswith(rick.RESTORE_TERMINAL))


if __name__ == "__main__":
    unittest.main()
