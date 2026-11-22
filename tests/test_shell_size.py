import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CLI = Path(__file__).resolve().parents[1] / "scripts/workbench.py"
DEFAULT = ("--unit", "mm", "--expected-mm", "8", "5", "5", "--tolerance-mm", "0")
ASCII = b"""solid Designed by EasyEDA Pro
 facet normal 0.0e+00 0.0e+00 1.0e+00
   outer loop
     vertex 0 12 1
     vertex 2.0E+00 12 2
     vertex 0 14 3
   endloop
 endfacet
endsolid
"""


def stl(*triangles):
    # Binary STL allows a header beginning with "solid"; the records decide the format.
    return (b"solid fixture".ljust(80, b"\0") + struct.pack("<I", len(triangles))
            + b"".join(struct.pack("<12fH", 0, 0, 1, *vertices, 0) for vertices in triangles))


class ShellSizeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.lower = self.directory / "lower.stl"
        self.upper = self.directory / "upper.stl"
        self.lower.write_bytes(stl((-3, 10, -2, 5, 10, -2, -3, 15, 0)))
        self.upper.write_bytes(stl((0, 12, 1, 2, 12, 2, 0, 14, 2),
                                   (0, 12, 1, 0, 14, 2, 1, 13, 3)))

    def cli(self, paths, options=DEFAULT):
        return subprocess.run([sys.executable, "-B", str(CLI), "shell-size", *paths, *options],
                              capture_output=True, text=True)

    def test_common_frame_union_includes_all_triangles(self):
        proc = self.cli([self.lower, self.upper])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertTrue(result["passed"])
        self.assertIn("outer", result["scope"].lower())
        self.assertEqual(result["union"]["min_mm"], [-3, 10, -2])
        self.assertEqual(result["union"]["max_mm"], [5, 15, 3])
        self.assertEqual(result["union"]["size_mm"], [8, 5, 5])
        self.assertEqual([part["size_mm"] for part in result["parts"]], [[8, 5, 2], [2, 2, 2]])

    def test_one_axis_outside_tolerance_is_a_mismatch(self):
        proc = self.cli([self.lower])
        self.assertEqual(proc.returncode, 1, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertFalse(result["passed"])
        self.assertEqual(result["failed_axes"], ["Z"])

    def test_ascii_native_export_measures_in_same_frame_as_binary(self):
        self.upper.write_bytes(ASCII)
        proc = self.cli([self.lower, self.upper])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual([p["format"] for p in result["parts"]], ["binary", "ascii"])
        self.assertEqual(result["union"]["size_mm"], [8, 5, 5])

    def test_single_part_at_inclusive_tolerance(self):
        proc = self.cli([self.lower], ("--unit", "mm", "--expected-mm", "8.3", "5", "2",
                                       "--tolerance-mm", "0.3"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(json.loads(proc.stdout)["passed"])

    def test_invalid_stl_is_an_input_error_even_after_valid_part(self):
        binary = self.lower.read_bytes()
        for label, data in [
            ("empty ASCII", b"solid a\nendsolid a\n"),
            ("ASCII truncation", ASCII.removesuffix(b"endsolid\n")),
            ("ASCII missing vertex", ASCII.replace(b"     vertex 0 12 1\n", b"")),
            ("ASCII extra vertex", ASCII.replace(b"   endloop", b"     vertex 1 1 1\n   endloop")),
            ("ASCII facet structure", ASCII.replace(b"outer loop", b"malformed")),
            ("ASCII nonfinite", ASCII.replace(b"0 12 1", b"nan 12 1")),
            ("ASCII trailing junk", ASCII + b"vertex 1 2 3\n"),
            ("zero", stl()),
            ("truncated", binary[:-1]),
            ("trailing", binary + b"!"),
            ("vertex", stl((0, 1, 0, 1, float("nan"), 0, 1, 0, 1))),
            ("normal", binary[:84] + struct.pack("<f", float("inf")) + binary[88:]),
        ]:
            with self.subTest(label):
                self.upper.write_bytes(data)
                proc = self.cli([self.lower, self.upper])
                self.assertEqual(proc.returncode, 2, proc.stderr)
                self.assertIn(self.upper.name, proc.stderr)
                self.assertFalse(proc.stdout)

    def test_units_and_sensible_limits_are_required(self):
        for label, unit, x, tolerance in [
            ("undeclared unit", (), "8", "0"),
            ("wrong unit", ("--unit", "in"), "8", "0"),
            ("zero target", ("--unit", "mm"), "0", "0"),
            ("negative target", ("--unit", "mm"), "-8", "0"),
            ("infinite target", ("--unit", "mm"), "inf", "0"),
            ("negative tolerance", ("--unit", "mm"), "8", "-1"),
            ("nonfinite tolerance", ("--unit", "mm"), "8", "nan"),
            ("tolerance permits collapsed axis", ("--unit", "mm"), "8", "2"),
        ]:
            with self.subTest(label):
                proc = self.cli([self.lower], (*unit, "--expected-mm", x, "5", "2",
                                                "--tolerance-mm", tolerance))
                self.assertEqual(proc.returncode, 2, proc.stderr)
                self.assertNotIn("invalid choice: 'shell-size'", proc.stderr)
                self.assertFalse(proc.stdout)


if __name__ == "__main__":
    unittest.main()
