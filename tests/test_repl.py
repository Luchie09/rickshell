"""Tests for prompt construction."""

import os
import tempfile
import unittest

from shell.context import ShellContext
from shell.repl import build_prompt


class PromptTests(unittest.TestCase):
    def test_prompt_at_start_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = ShellContext()
            context.start_dir = directory
            context.cwd = directory
            folder = os.path.basename(directory)
            self.assertEqual(build_prompt(context), f"rickshell:{folder}> ")

    def test_prompt_one_level_inside_start_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = ShellContext()
            context.start_dir = directory
            context.cwd = os.path.join(directory, "scratch")
            folder = os.path.basename(directory)
            self.assertEqual(
                build_prompt(context),
                f"rickshell:{os.path.join(folder, 'scratch')}> ",
            )

    def test_prompt_nested_inside_start_directory(self) -> None:
        context = ShellContext()
        context.start_dir = os.path.abspath(os.path.join("start-folder"))
        context.cwd = os.path.join(context.start_dir, "scratch", "sub")
        folder = os.path.basename(context.start_dir)
        expected = os.path.join(folder, "scratch", "sub")
        self.assertEqual(build_prompt(context), f"rickshell:{expected}> ")

    def test_prompt_outside_start_directory_uses_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            context = ShellContext()
            context.start_dir = os.path.join(directory, "start")
            context.cwd = os.path.join(directory, "outside")
            expected = os.path.abspath(context.cwd)
            self.assertEqual(build_prompt(context), f"rickshell:{expected}> ")

    def test_prompt_at_drive_root_uses_full_path(self) -> None:
        if os.name != "nt":
            self.skipTest("Drive roots are only available on Windows")
        context = ShellContext()
        context.start_dir = "C:\\"
        context.cwd = "C:\\"
        self.assertEqual(build_prompt(context), "rickshell:C:\\> ")


if __name__ == "__main__":
    unittest.main()
