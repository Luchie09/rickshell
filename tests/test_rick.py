"""Tests for TTY-only live Rick animation."""

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
        response = self.response([b"\x1b[Hframe\x1b[H"])
        response.read.side_effect = [
            b"\x1b[Hframe\x1b[H",
            KeyboardInterrupt(),
        ]
        with patch("urllib.request.urlopen", return_value=response):
            result = cmd_rick([], io.StringIO(), output, io.StringIO(), self.context)
        self.assertEqual(result, 0)
        self.assertTrue(output.getvalue().startswith("Press Ctrl+C to stop\n"))
        self.assertIn(rick.ENTER_ANIMATION, output.getvalue())
        self.assertTrue(output.getvalue().endswith(rick.RESTORE_TERMINAL))

    def test_stream_failures_leave_the_screen_untouched(self) -> None:
        for error in (URLError("offline"), TimeoutError("timed out")):
            with self.subTest(error=error):
                output = TTYStringIO()
                with patch("urllib.request.urlopen", side_effect=error):
                    result = cmd_rick(
                        [], io.StringIO(), output, io.StringIO(), self.context
                    )
                self.assertEqual(result, 0)
                self.assertEqual(output.getvalue(), "")

        for response in (self.response([b""]), self.response([b"bad stream"])):
            output = TTYStringIO()
            with patch("urllib.request.urlopen", return_value=response):
                result = cmd_rick(
                    [], io.StringIO(), output, io.StringIO(), self.context
                )
            self.assertEqual(result, 0)
            self.assertEqual(output.getvalue(), "")

        output = TTYStringIO()
        bad_response = self.response([b"\x1b[Hframe\x1b[H"], status=500)
        with patch("urllib.request.urlopen", return_value=bad_response):
            result = cmd_rick(
                [], io.StringIO(), output, io.StringIO(), self.context
            )
        self.assertEqual(result, 0)
        self.assertEqual(output.getvalue(), "")

    def test_non_tty_does_not_write_or_open_network(self) -> None:
        output = io.StringIO()
        with patch("urllib.request.urlopen") as urlopen:
            rick.play_rick(output)
        self.assertEqual(output.getvalue(), "")
        urlopen.assert_not_called()

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

    def test_unknown_command_trigger_does_nothing_when_offline(self) -> None:
        output = TTYStringIO()
        stderr = io.StringIO()
        with (
            patch.object(sys, "stdin", io.StringIO("unknown-command\n")),
            patch.object(sys, "stdout", output),
            patch.object(sys.stdout, "isatty", return_value=True),
            patch.object(sys, "stderr", stderr),
            patch("shell.repl.time.sleep"),
            patch("urllib.request.urlopen", side_effect=URLError("offline")),
        ):
            run(self.context)
        self.assertNotIn("\x1b[", output.getvalue())
        self.assertNotIn("Press Ctrl+C to stop", output.getvalue())
        self.assertIn("unknown-command: command not found", stderr.getvalue())
        self.assertEqual(self.context.last_exit_code, 127)

    def test_successful_commands_never_trigger_animation(self) -> None:
        # Only an unknown command plays Rick; ten successes in a row do not.
        self.context = ShellContext()
        success_stdout = TTYStringIO()
        with (
            patch.object(sys, "stdin", io.StringIO("true\n" * 10)),
            patch.object(sys, "stdout", success_stdout),
            patch.object(sys.stdout, "isatty", return_value=True),
            patch.object(sys, "stderr", io.StringIO()),
            patch("shell.repl._rick.play_rick") as live_dance,
            patch("urllib.request.urlopen") as urlopen,
        ):
            run(self.context)
        self.assertEqual(self.context.last_exit_code, 0)
        live_dance.assert_not_called()
        urlopen.assert_not_called()

    def test_automatic_trigger_skips_network_when_disabled_or_non_tty(self) -> None:
        self.context.easter_eggs = False
        disabled_stdout = TTYStringIO()
        with (
            patch.object(sys, "stdin", io.StringIO("unknown-command\n")),
            patch.object(sys, "stdout", disabled_stdout),
            patch.object(sys, "stderr", io.StringIO()),
            patch("shell.repl._rick.play_rick") as live_dance,
            patch("urllib.request.urlopen") as urlopen,
        ):
            run(self.context)
        live_dance.assert_not_called()
        urlopen.assert_not_called()

        self.context = ShellContext()
        self.context.easter_eggs = False
        success_stdout = TTYStringIO()
        with (
            patch.object(sys, "stdin", io.StringIO("true\n" * 10)),
            patch.object(sys, "stdout", success_stdout),
            patch.object(sys.stdout, "isatty", return_value=True),
            patch.object(sys, "stderr", io.StringIO()),
            patch("urllib.request.urlopen") as urlopen,
        ):
            run(self.context)
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

if __name__ == "__main__":
    unittest.main()
