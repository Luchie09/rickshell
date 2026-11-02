"""Tests for prompt construction."""

import os
import tempfile
import unittest

from shell.context import ShellContext
from shell.repl import build_prompt


class PromptTests(unittest.TestCase):
    def make_context(self, root: str) -> ShellContext:
        start_dir = os.path.join(root, "rickshell")
        os.makedirs(start_dir)
        context = ShellContext()
        context.start_dir = start_dir
        context.cwd = start_dir
        return context

    def test_prompt_at_start_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = self.make_context(directory)
            self.assertEqual(build_prompt(context), "rickshell > ")

    def test_prompt_one_level_inside_start_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = self.make_context(directory)
            context.cwd = os.path.join(context.start_dir, "scratch")
            self.assertEqual(
                build_prompt(context),
                "rickshell" + os.sep + "scratch > ",
            )

    def test_prompt_nested_inside_start_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = self.make_context(directory)
            context.cwd = os.path.join(context.start_dir, "data", "resources")
            expected = os.path.join("rickshell", "data", "resources") + " > "
            self.assertEqual(build_prompt(context), expected)

    def test_prompt_outside_start_directory_uses_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = self.make_context(directory)
            context.cwd = os.path.join(directory, "outside")
            self.assertEqual(build_prompt(context), context.cwd + " > ")

    def test_prompt_updates_when_working_directory_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = self.make_context(directory)
            self.assertEqual(build_prompt(context), "rickshell > ")
            context.cwd = os.path.join(context.start_dir, "scratch")
            self.assertEqual(
                build_prompt(context),
                "rickshell" + os.sep + "scratch > ",
            )


if __name__ == "__main__":
    unittest.main()
