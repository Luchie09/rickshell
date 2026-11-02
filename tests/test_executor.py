"""Tests for command execution and REPL integration."""

import io
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from shell.builtins import REGISTRY, register
from shell.context import ShellContext
from shell.executor import execute
from shell.parser import parse
from shell.repl import run
from shell.tokenizer import tokenize


@register("upper")
def upper(args, stdin, stdout, stderr, ctx):
    stdout.write(stdin.read().upper())
    return 0


@register("fail")
def fail(args, stdin, stdout, stderr, ctx):
    return 1


@register("streams")
def streams(args, stdin, stdout, stderr, ctx):
    stdout.write("out\n")
    stderr.write("err\n")
    return 0


@register("raises")
def raises(args, stdin, stdout, stderr, ctx):
    raise ValueError("test failure")


class ExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = ShellContext()

    def run_line(self, line: str, stdin=None, stdout=None, stderr=None) -> tuple[int, str, str]:
        stdin = stdin or io.StringIO()
        stdout = stdout or io.StringIO()
        stderr = stderr or io.StringIO()
        result = execute(parse(tokenize(line)), self.context, stdin, stdout, stderr)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_echo_and_variable_assignment_and_expansion(self) -> None:
        result, output, _ = self.run_line("echo hello world")
        self.assertEqual((result, output), (0, "hello world\n"))

        result, output, _ = self.run_line("X=5 ; echo $X")
        self.assertEqual((result, output), (0, "5\n"))

    def test_env_prints_variables_in_name_order(self) -> None:
        self.context.variables.update({"ZED": "last", "ALPHA": "first"})
        result, output, _ = self.run_line("env")
        self.assertEqual((result, output), (0, "ALPHA=first\nZED=last\n"))

    def test_quote_expansion_behavior(self) -> None:
        self.context.variables["X"] = "value"
        result, output, _ = self.run_line("echo '$X' \"$X\"")
        self.assertEqual(result, 0)
        self.assertEqual(output, "$X value\n")

    def test_last_exit_code_and_connectors(self) -> None:
        self.context.last_exit_code = 0
        result, output, _ = self.run_line("false ; echo $?")
        self.assertEqual((result, output), (0, "1\n"))

        result, output, _ = self.run_line("true && echo yes")
        self.assertEqual((result, output), (0, "yes\n"))
        result, output, _ = self.run_line("false && echo no")
        self.assertEqual((result, output), (1, ""))
        result, output, _ = self.run_line("false || echo yes")
        self.assertEqual((result, output), (0, "yes\n"))
        result, output, _ = self.run_line("true || echo no")
        self.assertEqual((result, output), (0, ""))
        result, output, _ = self.run_line("fail ; echo after")
        self.assertEqual((result, output), (0, "after\n"))

    def test_two_and_three_stage_pipelines(self) -> None:
        result, output, _ = self.run_line("echo hello | upper")
        self.assertEqual((result, output), (0, "HELLO\n"))

        result, output, _ = self.run_line("echo hello | upper | upper")
        self.assertEqual((result, output), (0, "HELLO\n"))

    def test_output_append_and_input_redirection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.context.cwd = directory
            target = os.path.join(directory, "data.txt")
            result, _, _ = self.run_line("echo first > data.txt")
            self.assertEqual(result, 0)
            result, _, _ = self.run_line("echo second >> data.txt")
            self.assertEqual(result, 0)
            with open(target) as file:
                self.assertEqual(file.read(), "first\nsecond\n")

            result, output, _ = self.run_line("upper < data.txt")
            self.assertEqual((result, output), (0, "FIRST\nSECOND\n"))

    def test_unknown_command_error_can_be_redirected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.context.cwd = directory
            result, _, error = self.run_line("missing-command 2> err.txt")
            self.assertEqual(result, 127)
            self.assertEqual(error, "")
            with open(os.path.join(directory, "err.txt")) as file:
                self.assertEqual(
                    file.read(),
                    "rickshell: missing-command: command not found\n",
                )

    def test_redirection_order_controls_stderr_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.context.cwd = directory
            result, stdout, stderr = self.run_line("streams > both.txt 2>&1")
            self.assertEqual((result, stdout, stderr), (0, "", ""))
            with open(os.path.join(directory, "both.txt")) as file:
                self.assertEqual(file.read(), "out\nerr\n")

            result, stdout, stderr = self.run_line("streams 2>&1 > stdout.txt")
            self.assertEqual((result, stdout, stderr), (0, "err\n", ""))
            with open(os.path.join(directory, "stdout.txt")) as file:
                self.assertEqual(file.read(), "out\n")

    def test_redirect_open_failure_and_exception(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.context.cwd = directory
            result, _, error = self.run_line("echo no > missing\\child.txt")
            self.assertEqual(result, 1)
            self.assertIn("rickshell: missing\\child.txt:", error)

        result, output, error = self.run_line("raises")
        self.assertEqual((result, output), (1, ""))
        self.assertIn("rickshell: raises: internal error: test failure", error)

    def test_unset_variable_expands_to_empty(self) -> None:
        result, output, _ = self.run_line("echo before${UNSET}after")
        self.assertEqual((result, output), (0, "beforeafter\n"))

    def test_repl_reports_syntax_errors_and_uses_executor(self) -> None:
        context = ShellContext()
        stdin = io.StringIO("echo hello\n&& bad\n")
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout), patch.object(
            sys, "stderr", stderr
        ):
            run(context)

        self.assertEqual(context.last_exit_code, 2)
        self.assertIn("hello\n", stdout.getvalue())
        self.assertIn("rickshell: syntax error:", stderr.getvalue())

    def test_registry_contains_requested_builtins(self) -> None:
        self.assertIn("echo", REGISTRY)
        self.assertIn("env", REGISTRY)
        self.assertIn("true", REGISTRY)
        self.assertIn("false", REGISTRY)


if __name__ == "__main__":
    unittest.main()
