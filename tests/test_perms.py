"""Tests for simulated file permissions."""

import io
import os
import tempfile
import unittest

from shell.builtins.perms import format_long, get_mode
from shell.context import ShellContext
from shell.builtins import REGISTRY


class PermissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.context = ShellContext()
        self.context.cwd = self.temporary_directory.name
        self.file_path = os.path.join(self.context.cwd, "item.txt")
        with open(self.file_path, "w") as file:
            file.write("data")

    def run_chmod(self, *args: str):
        output = io.StringIO()
        error = io.StringIO()
        result = REGISTRY["chmod"](
            list(args),
            io.StringIO(),
            output,
            error,
            self.context,
        )
        return result, output.getvalue(), error.getvalue()

    def test_default_and_recorded_modes(self) -> None:
        self.assertEqual(get_mode(self.context, self.file_path), 0o644)
        self.assertEqual(get_mode(self.context, self.context.cwd), 0o755)
        self.assertEqual(format_long(self.context, self.file_path)[:10], "-rw-r--r--")

    def test_chmod_755_and_ls_long_display(self) -> None:
        result, _, error = self.run_chmod("755", "item.txt")
        self.assertEqual((result, error), (0, ""))
        self.assertEqual(self.context.permissions[self.file_path], 0o755)

        output = io.StringIO()
        result = REGISTRY["ls"](
            ["-l"],
            io.StringIO(),
            output,
            io.StringIO(),
            self.context,
        )
        self.assertEqual(result, 0)
        self.assertRegex(
            output.getvalue(),
            r"^total 4\n-rwxr-xr-x +1 \S+ +\S+ +4 .* item\.txt\n$",
        )

    def test_chmod_644_and_four_digit_mode(self) -> None:
        result, _, error = self.run_chmod("644", "item.txt")
        self.assertEqual((result, error), (0, ""))
        self.assertTrue(format_long(self.context, self.file_path).startswith("-rw-r--r--"))

        result, _, error = self.run_chmod("0755", "item.txt")
        self.assertEqual((result, error), (0, ""))
        self.assertEqual(get_mode(self.context, self.file_path), 0o755)

    def test_invalid_mode_and_missing_file(self) -> None:
        for mode in ("999", "abc"):
            with self.subTest(mode=mode):
                result, _, error = self.run_chmod(mode, "item.txt")
                self.assertEqual(result, 2)
                self.assertIn(
                    f"chmod: invalid mode '{mode}' (use 3 or 4 octal digits)",
                    error,
                )

        result, _, error = self.run_chmod("755", "missing.txt")
        self.assertEqual(result, 1)
        self.assertIn("chmod: missing.txt: No such file or directory", error)

    def test_missing_operand(self) -> None:
        result, _, error = self.run_chmod()
        self.assertEqual(result, 2)
        self.assertIn("chmod: missing operand", error)
        result, _, error = self.run_chmod("755")
        self.assertEqual(result, 2)
        self.assertIn("chmod: missing operand", error)


if __name__ == "__main__":
    unittest.main()
