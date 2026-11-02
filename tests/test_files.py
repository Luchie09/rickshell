"""Tests for file and directory built-ins."""

import io
import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

from shell.builtins import REGISTRY
from shell.builtins.perms import format_long
from shell.context import ShellContext
from shell.executor import execute
from shell.parser import parse
from shell.tokenizer import tokenize


class FileCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.context = ShellContext()
        self.context.cwd = self.temporary_directory.name

    def run_command(self, name: str, *args: str, stdin=None):
        output = io.StringIO()
        error = io.StringIO()
        input_stream = stdin if stdin is not None else io.StringIO()
        result = REGISTRY[name](
            list(args),
            input_stream,
            output,
            error,
            self.context,
        )
        return result, output.getvalue(), error.getvalue()

    def test_pwd_cd_and_return_to_original_directory(self) -> None:
        original = self.context.cwd
        os.mkdir(os.path.join(original, "sub"))

        result, output, _ = self.run_command("pwd")
        self.assertEqual((result, output), (0, original + "\n"))

        result, _, _ = self.run_command("cd", "sub")
        self.assertEqual(result, 0)
        self.assertEqual(self.context.cwd, os.path.join(original, "sub"))
        result, _, _ = self.run_command("cd", "..")
        self.assertEqual(result, 0)
        self.assertEqual(self.context.cwd, original)

    def test_cd_missing_path(self) -> None:
        result, _, error = self.run_command("cd", "missing")
        self.assertEqual(result, 1)
        self.assertIn("cd: missing: No such file or directory", error)

    def test_ls_empty_and_populated_directory_uses_plain_string_sort(self) -> None:
        result, output, _ = self.run_command("ls")
        self.assertEqual((result, output), (0, ""))

        for name in ("directory1", "Projects", ".hidden", "alpha"):
            with open(os.path.join(self.context.cwd, name), "w"):
                pass
        result, output, _ = self.run_command("ls")
        self.assertEqual(
            (result, output),
            (0, "Projects\nalpha\ndirectory1\n"),
        )

    def test_ls_hidden_entries_and_dot_entries(self) -> None:
        for name in (".hidden", "visible"):
            with open(os.path.join(self.context.cwd, name), "w"):
                pass

        self.assertEqual(self.run_command("ls")[1], "visible\n")
        self.assertEqual(
            self.run_command("ls", "-a")[1],
            ".\n..\n.hidden\nvisible\n",
        )
        long_output = self.run_command("ls", "-la")[1]
        self.assertRegex(long_output, r"(?m)^d.{9} .* \.$")
        self.assertRegex(long_output, r"(?m)^d.{9} .* \.\.$")

    def test_ls_stringio_is_one_name_per_line(self) -> None:
        for name in ("b", "a", "c"):
            with open(os.path.join(self.context.cwd, name), "w"):
                pass
        result, output, error = self.run_command("ls")
        self.assertEqual((result, output, error), (0, "a\nb\nc\n", ""))

    def test_ls_terminal_columns_are_column_major(self) -> None:
        for name in (f"{index:02}aaa" for index in range(1, 9)):
            with open(os.path.join(self.context.cwd, name), "w"):
                pass

        class TerminalOutput(io.StringIO):
            def isatty(self) -> bool:
                return True

        output = TerminalOutput()
        with patch(
            "shell.builtins.files.shutil.get_terminal_size",
            return_value=os.terminal_size((40, 24)),
        ):
            result = REGISTRY["ls"](
                [],
                io.StringIO(),
                output,
                io.StringIO(),
                self.context,
            )

        self.assertEqual(result, 0)
        self.assertEqual(
            output.getvalue(),
            "01aaa  03aaa  05aaa  06aaa  07aaa  08aaa\n"
            "02aaa  04aaa\n",
        )

    def test_ls_terminal_colors_directories(self) -> None:
        os.mkdir(os.path.join(self.context.cwd, "folder"))

        class TerminalOutput(io.StringIO):
            def isatty(self) -> bool:
                return True

        output = TerminalOutput()
        result = REGISTRY["ls"](
            [],
            io.StringIO(),
            output,
            io.StringIO(),
            self.context,
        )
        self.assertEqual(result, 0)
        self.assertEqual(output.getvalue(), "\x1b[1;34mfolder\x1b[0m\n")

        output = TerminalOutput()
        result = REGISTRY["ls"](
            ["-l"],
            io.StringIO(),
            output,
            io.StringIO(),
            self.context,
        )
        self.assertEqual(result, 0)
        self.assertIn("\x1b[1;34mfolder\x1b[0m\n", output.getvalue())

    def test_ls_multiple_directories_have_headers(self) -> None:
        for folder, filename in (("one", "a"), ("two", "b")):
            directory = os.path.join(self.context.cwd, folder)
            os.mkdir(directory)
            with open(os.path.join(directory, filename), "w"):
                pass
        result, output, error = self.run_command("ls", "one", "two")
        self.assertEqual(
            (result, output, error),
            (0, "one:\na\n\ntwo:\nb\n", ""),
        )

    def test_ls_invalid_option_returns_two(self) -> None:
        result, _, error = self.run_command("ls", "-z")
        self.assertEqual(result, 2)
        self.assertEqual(error, "ls: invalid option -- 'z'\n")

    def test_ls_missing_path_continues_with_other_paths(self) -> None:
        os.mkdir(os.path.join(self.context.cwd, "valid"))
        with open(os.path.join(self.context.cwd, "valid", "item"), "w"):
            pass
        result, output, error = self.run_command("ls", "missing", "valid")
        self.assertEqual(result, 1)
        self.assertIn("ls: missing: No such file or directory\n", error)
        self.assertIn("valid:\nitem\n", output)

    def test_ls_recursive_headers_depth_first_sorted_and_hidden_policy(self) -> None:
        os.mkdir(os.path.join(self.context.cwd, "a"))
        os.mkdir(os.path.join(self.context.cwd, "a", "child"))
        os.mkdir(os.path.join(self.context.cwd, "b"))
        os.mkdir(os.path.join(self.context.cwd, ".hidden"))

        result, output, error = self.run_command("ls", "-R")
        self.assertEqual((result, error), (0, ""))
        self.assertEqual(
            output,
            ".:\na\nb\n\n./a:\nchild\n\n./a/child:\n\n./b:\n",
        )
        self.assertNotIn(".hidden:", output)

        result, output, error = self.run_command("ls", "-aR")
        self.assertEqual((result, error), (0, ""))
        self.assertIn("./.hidden:\n", output)
        self.assertIn(".:\n.\n..\n.hidden\na\nb\n", output)

    def test_ls_recursive_combined_flags_are_equivalent(self) -> None:
        os.mkdir(os.path.join(self.context.cwd, "sub"))
        with open(os.path.join(self.context.cwd, "sub", "item"), "w"):
            pass
        with patch("shell.builtins.perms._link_count", return_value=2):
            self.assertEqual(
                self.run_command("ls", "-Rla"),
                self.run_command("ls", "-laR"),
            )

    def test_ls_recursive_permission_error_does_not_stop_later_entries(self) -> None:
        for folder in ("blocked", "visible"):
            os.mkdir(os.path.join(self.context.cwd, folder))
        original_listdir = os.listdir
        blocked_path = os.path.join(self.context.cwd, "blocked")

        def listdir_with_denied_path(path: str) -> list[str]:
            if os.path.abspath(path) == blocked_path:
                raise PermissionError("access denied")
            return original_listdir(path)

        with patch(
            "shell.builtins.files.os.listdir",
            side_effect=listdir_with_denied_path,
        ):
            result, output, error = self.run_command("ls", "-R")

        self.assertEqual(result, 1)
        self.assertIn("ls: ./blocked: Permission denied\n", error)
        self.assertIn("./visible:\n", output)

    def test_ls_long_rows_date_columns_and_totals(self) -> None:
        with open(os.path.join(self.context.cwd, "empty"), "w"):
            pass
        with open(os.path.join(self.context.cwd, "hundred"), "wb") as file:
            file.write(b"x" * 100)
        with open(os.path.join(self.context.cwd, "large"), "wb") as file:
            file.write(b"x" * 5000)
        os.mkdir(os.path.join(self.context.cwd, "subdir"))

        result, output, _ = self.run_command("ls", "-l")
        self.assertEqual(result, 0)
        self.assertTrue(output.startswith("total 16\n"))
        self.assertRegex(
            output,
            r"(?m)^-rw-r--r-- +1 \S+ +\S+ +0 [A-Z][a-z]{2} [ 0-3]\d (?:\d{2}:\d{2}| \d{4}) empty$",
            msg=output,
        )

        result, output, _ = self.run_command("ls", "-la")
        self.assertEqual(result, 0)
        self.assertTrue(output.startswith("total 24\n"))
        self.assertEqual(len(output.splitlines()), 7)

    def test_ls_long_recent_and_old_dates(self) -> None:
        recent_path = os.path.join(self.context.cwd, "recent")
        old_path = os.path.join(self.context.cwd, "old")
        for path in (recent_path, old_path):
            with open(path, "w"):
                pass
        now = datetime.now().timestamp()
        os.utime(recent_path, (now, now))
        old_time = datetime(2024, 4, 22, 12, 0).timestamp()
        os.utime(old_path, (old_time, old_time))

        result, output, _ = self.run_command("ls", "-l")
        self.assertEqual(result, 0)
        self.assertRegex(output, r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec")
        self.assertIn("Apr 22  2024 old", output)
        self.assertRegex(output, r"[A-Z][a-z]{2} [ 0-3]\d \d{2}:\d{2} recent")

    def test_ls_long_directory_link_count_includes_subdirectories(self) -> None:
        directory = os.path.join(self.context.cwd, "parent")
        os.mkdir(directory)
        os.mkdir(os.path.join(directory, "one"))
        os.mkdir(os.path.join(directory, "two"))
        row = format_long(self.context, directory, "parent")
        self.assertRegex(row, r"^drwxr-xr-x 4 ")

    def test_dir_alias_matches_ls_and_is_listed_by_help(self) -> None:
        with open(os.path.join(self.context.cwd, "item.txt"), "w"):
            pass

        self.assertEqual(
            self.run_command("dir"),
            self.run_command("ls"),
        )
        self.assertEqual(
            self.run_command("dir", "-l"),
            self.run_command("ls", "-l"),
        )

        output = io.StringIO()
        REGISTRY["help"]([], io.StringIO(), output, io.StringIO(), self.context)
        self.assertIn("dir\n", output.getvalue())

    def test_ls_long_format(self) -> None:
        with open(os.path.join(self.context.cwd, "item.txt"), "w") as file:
            file.write("data")
        result, output, _ = self.run_command("ls", "-l")
        self.assertEqual(result, 0)
        self.assertRegex(
            output,
            r"^total 4\n-rw-r--r-- +1 \S+ +\S+ +4 [A-Z][a-z]{2} [ 0-3]\d (?:\d{2}:\d{2}| \d{4}) item\.txt\n$",
        )

    def test_mkdir_rmdir_and_existing_name(self) -> None:
        result, _, error = self.run_command("mkdir", "new")
        self.assertEqual((result, error), (0, ""))
        result, _, error = self.run_command("mkdir", "new")
        self.assertEqual(result, 1)
        self.assertIn("mkdir: new: File exists", error)

        result, _, error = self.run_command("rmdir", "new")
        self.assertEqual((result, error), (0, ""))
        self.assertFalse(os.path.exists(os.path.join(self.context.cwd, "new")))

    def test_rmdir_nonempty_directory(self) -> None:
        os.mkdir(os.path.join(self.context.cwd, "d"))
        with open(os.path.join(self.context.cwd, "d", "file"), "w"):
            pass
        result, _, error = self.run_command("rmdir", "d")
        self.assertEqual(result, 1)
        self.assertIn("rmdir: d: Directory not empty", error)

    def test_touch_creates_and_updates_file(self) -> None:
        result, _, error = self.run_command("touch", "new.txt")
        path = os.path.join(self.context.cwd, "new.txt")
        self.assertEqual((result, error), (0, ""))
        self.assertTrue(os.path.isfile(path))

        old_time = os.path.getmtime(path)
        os.utime(path, (old_time - 60, old_time - 60))
        result, _, error = self.run_command("touch", "new.txt")
        self.assertEqual((result, error), (0, ""))
        self.assertGreater(os.path.getmtime(path), old_time - 60)

    def test_cp_file_into_file_and_directory(self) -> None:
        with open(os.path.join(self.context.cwd, "source.txt"), "w") as file:
            file.write("source")
        result, _, error = self.run_command("cp", "source.txt", "copy.txt")
        self.assertEqual((result, error), (0, ""))
        with open(os.path.join(self.context.cwd, "copy.txt")) as file:
            self.assertEqual(file.read(), "source")

        os.mkdir(os.path.join(self.context.cwd, "target"))
        result, _, error = self.run_command("cp", "source.txt", "target")
        self.assertEqual((result, error), (0, ""))
        with open(os.path.join(self.context.cwd, "target", "source.txt")) as file:
            self.assertEqual(file.read(), "source")

    def test_cp_recursive_and_directory_without_recursive_flag(self) -> None:
        os.mkdir(os.path.join(self.context.cwd, "source"))
        with open(os.path.join(self.context.cwd, "source", "child.txt"), "w") as file:
            file.write("child")

        result, _, error = self.run_command("cp", "source", "copy")
        self.assertEqual(result, 1)
        self.assertIn("cp: source: omitting directory", error)

        result, _, error = self.run_command("cp", "-r", "source", "copy")
        self.assertEqual((result, error), (0, ""))
        with open(os.path.join(self.context.cwd, "copy", "child.txt")) as file:
            self.assertEqual(file.read(), "child")

    def test_mv_rename_and_into_directory_moves_simulated_mode(self) -> None:
        source = os.path.join(self.context.cwd, "source.txt")
        with open(source, "w"):
            pass
        self.context.permissions[source] = 0o600

        result, _, error = self.run_command("mv", "source.txt", "renamed.txt")
        destination = os.path.join(self.context.cwd, "renamed.txt")
        self.assertEqual((result, error), (0, ""))
        self.assertFalse(os.path.exists(source))
        self.assertEqual(self.context.permissions[destination], 0o600)
        self.assertNotIn(source, self.context.permissions)

        os.mkdir(os.path.join(self.context.cwd, "target"))
        result, _, error = self.run_command("mv", "renamed.txt", "target")
        target = os.path.join(self.context.cwd, "target", "renamed.txt")
        self.assertEqual((result, error), (0, ""))
        self.assertTrue(os.path.isfile(target))
        self.assertEqual(self.context.permissions[target], 0o600)

    def test_rm_file_and_recursive_directory(self) -> None:
        file_path = os.path.join(self.context.cwd, "file.txt")
        with open(file_path, "w"):
            pass
        self.context.permissions[file_path] = 0o600
        result, _, error = self.run_command("rm", "file.txt")
        self.assertEqual((result, error), (0, ""))
        self.assertFalse(os.path.exists(file_path))
        self.assertNotIn(file_path, self.context.permissions)

        os.mkdir(os.path.join(self.context.cwd, "d"))
        with open(os.path.join(self.context.cwd, "d", "child"), "w"):
            pass
        result, _, error = self.run_command("rm", "d")
        self.assertEqual(result, 1)
        self.assertIn("rm: d: Is a directory", error)
        result, _, error = self.run_command("rm", "-r", "d")
        self.assertEqual((result, error), (0, ""))
        self.assertFalse(os.path.exists(os.path.join(self.context.cwd, "d")))

    def test_cat_file_missing_and_stdin(self) -> None:
        with open(os.path.join(self.context.cwd, "first.txt"), "w") as file:
            file.write("one\n")
        with open(os.path.join(self.context.cwd, "second.txt"), "w") as file:
            file.write("two\n")

        result, output, error = self.run_command("cat", "first.txt", "second.txt")
        self.assertEqual((result, output, error), (0, "one\ntwo\n", ""))
        result, _, error = self.run_command("cat", "missing.txt")
        self.assertEqual(result, 1)
        self.assertIn("cat: missing.txt: No such file or directory", error)
        result, output, error = self.run_command("cat", stdin=io.StringIO("from pipe\n"))
        self.assertEqual((result, output, error), (0, "from pipe\n", ""))

    def test_missing_operands(self) -> None:
        for name in ("mkdir", "rmdir", "touch", "cp", "mv", "rm"):
            with self.subTest(command=name):
                result, _, error = self.run_command(name)
                self.assertEqual(result, 2)
                self.assertIn(f"{name}: missing operand", error)

    def test_executor_runs_file_commands_and_redirects_output(self) -> None:
        output = io.StringIO()
        error = io.StringIO()
        result = execute(
            parse(tokenize("mkdir d ; touch d/a.txt ; ls d > out.txt")),
            self.context,
            io.StringIO(),
            output,
            error,
        )
        self.assertEqual((result, output.getvalue(), error.getvalue()), (0, "", ""))
        with open(os.path.join(self.context.cwd, "out.txt")) as file:
            self.assertEqual(file.read(), "a.txt\n")


if __name__ == "__main__":
    unittest.main()
