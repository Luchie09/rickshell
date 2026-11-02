"""Tests for deadlock resource-state loading and safety checking."""

import os
import tempfile
import unittest

from sim.deadlock import ResourceState, safety_check
from sim.loader import LoaderError, load_resources


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOURCE_DIR = os.path.join(ROOT, "data", "resources")


class ResourceLoaderTests(unittest.TestCase):
    def test_sample_files(self) -> None:
        state = load_resources(os.path.join(RESOURCE_DIR, "safe.txt"))
        self.assertEqual(state.n, 5)
        self.assertEqual(state.m, 3)
        self.assertEqual(
            state.need(),
            [[7, 4, 3], [1, 2, 2], [6, 0, 0], [0, 1, 1], [4, 3, 1]],
        )
        self.assertEqual(
            safety_check(state),
            (True, ["P1", "P3", "P4", "P0", "P2"], []),
        )

        unsafe = load_resources(os.path.join(RESOURCE_DIR, "unsafe.txt"))
        self.assertEqual(unsafe.need(), [[0, 1], [1, 0]])
        self.assertEqual(safety_check(unsafe), (False, [], ["P0", "P1"]))

        single = load_resources(os.path.join(RESOURCE_DIR, "single.txt"))
        self.assertEqual(single.need(), [[2]])
        self.assertEqual(safety_check(single), (True, ["P0"], []))

        empty = load_resources(os.path.join(RESOURCE_DIR, "empty.txt"))
        self.assertEqual(empty.n, 0)
        self.assertEqual(safety_check(empty), (True, [], []))

        with self.assertRaisesRegex(LoaderError, "rows"):
            load_resources(os.path.join(RESOURCE_DIR, "bad_dims.txt"))

    def load_text(self, contents: str) -> ResourceState:
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "resources.txt")
            with open(path, "w", encoding="utf-8") as resource_file:
                resource_file.write(contents)
            return load_resources(path)

    def test_comments_and_blank_lines_are_skipped(self) -> None:
        state = self.load_text(
            "# dimensions\n\n1 1\n# allocation\n1\n\n# maximum\n2\n# available\n1\n"
        )
        self.assertEqual((state.n, state.m), (1, 1))
        self.assertEqual(state.allocation, [[1]])
        self.assertEqual(state.max_claim, [[2]])
        self.assertEqual(state.available, [1])

    def test_invalid_inputs(self) -> None:
        invalid_files = [
            ("1 1\n-1\n1\n1\n", "negative"),
            ("1 1\n2\n1\n0\n", "P0.*R0"),
            ("1 1\nx\n1\n1\n", "integers"),
            ("1 1 2\n1\n1\n1\n", "exactly"),
        ]
        for contents, expected in invalid_files:
            with self.subTest(contents=contents):
                with tempfile.TemporaryDirectory() as directory:
                    path = os.path.join(directory, "bad.txt")
                    with open(path, "w", encoding="utf-8") as resource_file:
                        resource_file.write(contents)
                    with self.assertRaisesRegex(LoaderError, expected):
                        load_resources(path)

        with tempfile.TemporaryDirectory() as directory:
            missing_path = os.path.join(directory, "missing.txt")
            with self.assertRaisesRegex(LoaderError, "No such file or directory"):
                load_resources(missing_path)

    def test_wrong_row_width_and_negative_dimensions(self) -> None:
        bad_width = "1 2\n1\n1 1\n0 0\n"
        with self.assertRaisesRegex(LoaderError, "expected 2 values"):
            self.load_text(bad_width)
        with self.assertRaisesRegex(LoaderError, "negative"):
            self.load_text("-1 2\n")


class ResourceStateTests(unittest.TestCase):
    def test_partial_deadlock_full_pass_order(self) -> None:
        state = ResourceState(
            3,
            1,
            [[1], [1], [0]],
            [[1], [3], [1]],
            [0],
        )
        # P0 needs 0, so it finishes first and releases one unit. P1 still
        # needs 2; continuing forward lets P2 need 1 and finish. P1 then
        # remains stuck because only one unit is available.
        self.assertEqual(
            safety_check(state),
            (False, ["P0", "P2"], ["P1"]),
        )

    def test_safety_check_does_not_modify_state(self) -> None:
        state = load_resources(os.path.join(RESOURCE_DIR, "safe.txt"))
        before = state.copy()
        safety_check(state)
        self.assertEqual(state, before)

    def test_copy_is_independent(self) -> None:
        state = load_resources(os.path.join(RESOURCE_DIR, "safe.txt"))
        duplicate = state.copy()
        duplicate.allocation[0][0] = 99
        duplicate.max_claim[0][0] = 100
        duplicate.available[0] = 88
        self.assertEqual(state.allocation[0][0], 0)
        self.assertEqual(state.max_claim[0][0], 7)
        self.assertEqual(state.available[0], 3)


if __name__ == "__main__":
    unittest.main()
