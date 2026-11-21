"""Black-box mechanical contract tests using only synthetic JSON and the stdlib."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_mechanics.py"
FRAME = {"origin": "DATUM-A", "view": "top", "x_positive": "right", "y_positive": "up"}
EXPECTED = {
    "unit": "mm", "frame": FRAME, "tolerance": {"center": 0.05, "drill": 0.0254},
    "holes": {"MH1": {"center": [2.54, 5.08], "drill": 3.175}},
    "interfaces": {"J1": {"side": "top", "insertion": "+x"}},
}
MEASURED = {
    "unit": "mil", "frame": FRAME,
    "holes": {"MH1": {"center": [100, 200], "drill": 125}},
    "interfaces": {"J1": {"side": "top", "insertion": "+x"}},
}


class MechanicalCheck(unittest.TestCase):
    def run_cli(self, intent, measurement, expected_exit):
        with tempfile.TemporaryDirectory() as tmp:
            files = []
            for idx, data in enumerate((intent, measurement)):
                p = Path(tmp) / f"{idx}.json"
                p.write_text(json.dumps(data), encoding="utf-8")
                files.append(str(p))
            result = subprocess.run([sys.executable, "-I", str(SCRIPT), *files],
                                    capture_output=True, text=True, timeout=10, check=False)
        self.assertEqual(result.returncode, expected_exit, result.stdout + result.stderr)
        if expected_exit == 2:
            self.assertIn("Input error:", result.stderr)
            return
        report = json.loads(result.stdout)
        self.assertIs(report["passed"], expected_exit == 0)
        return report

    def test_exact_mm_mil_equivalence(self):
        intent = copy.deepcopy(EXPECTED)
        intent["tolerance"] = {"center": 0, "drill": 0}
        report = self.run_cli(intent, MEASURED, 0)
        self.assertEqual(report["holes"]["MH1"]["center_error_mm"], 0)
        self.assertEqual(report["holes"]["MH1"]["drill_error_mm"], 0)
        self.assertTrue(report["interfaces"]["J1"]["passed"])

    def test_mm_numbers_accidentally_declared_as_mil_are_not_equal(self):
        got = copy.deepcopy(MEASURED)
        got["holes"] = copy.deepcopy(EXPECTED["holes"])
        report = self.run_cli(EXPECTED, got, 1)
        self.assertGreater(report["holes"]["MH1"]["center_error_mm"], 1)
        self.assertGreater(report["holes"]["MH1"]["drill_error_mm"], 1)

    def test_same_frame_required_even_when_numbers_match(self):
        for field, changed in [("view", "bottom"), ("x_positive", "left"),
                               ("y_positive", "down"), ("origin", "DATUM-B")]:
            with self.subTest(field=field):
                got = copy.deepcopy(MEASURED)
                got["frame"][field] = changed
                self.run_cli(EXPECTED, got, 2)

    def test_missing_or_extra_hole_is_a_reported_mismatch(self):
        for ref in ("MH1", "MH2"):
            with self.subTest(ref=ref):
                got = copy.deepcopy(MEASURED)
                if ref == "MH1":
                    del got["holes"][ref]
                else:
                    got["holes"][ref] = {"center": [300, 200], "drill": 125}
                report = self.run_cli(EXPECTED, got, 1)
                self.assertFalse(report["holes"][ref]["passed"])

    def test_different_interface_side_direction_or_missing_interface_do_not_pass(self):
        for value in ({"side": "bottom", "insertion": "+x"},
                      {"side": "top", "insertion": "-x"}, None):
            with self.subTest(value=value):
                got = copy.deepcopy(MEASURED)
                got["interfaces"] = {} if value is None else {"J1": value}
                self.assertFalse(self.run_cli(EXPECTED, got, 1)["interfaces"]["J1"]["passed"])

    def test_center_error_uses_radius_and_includes_tolerance_boundary(self):
        got = copy.deepcopy(EXPECTED)
        del got["tolerance"]
        got["holes"]["MH1"] = {"center": [2.57, 5.12], "drill": 3.2004}
        self.run_cli(EXPECTED, got, 0)  # 0.03/0.04 -> 0.05 radial; 0.0254 drill.
        got["holes"]["MH1"]["center"] = [2.58, 5.12]
        self.run_cli(EXPECTED, got, 1)
        got["holes"]["MH1"] = {"center": [2.54, 5.08], "drill": 3.2005}
        self.run_cli(EXPECTED, got, 1)

    def test_incomplete_or_invalid_input_cannot_pass(self):
        for field, value in [("unit", None), ("unit", "inch"), ("frame", {"view": "top"}),
                             ("holes", {"MH1": {"center": [0, 0], "drill": True}}),
                             ("holes", {"MH1": {"center": [0, float("nan")], "drill": 1}}),
                             ("interfaces", {"J1": {"side": "top"}})]:
            with self.subTest(field=field, value=value):
                got = copy.deepcopy(MEASURED)
                if value is None:
                    del got[field]
                else:
                    got[field] = value
                self.run_cli(EXPECTED, got, 2)
        for field, value in [("holes", {}), ("interfaces", {}), ("tolerance", {"center": -1, "drill": 0})]:
            with self.subTest(field=field, value=value):
                intent = copy.deepcopy(EXPECTED)
                intent[field] = value
                self.run_cli(intent, MEASURED, 2)

    def test_published_synthetic_examples_work(self):
        def load(name):
            return json.loads((ROOT / "assets" / name).read_text(encoding="utf-8"))
        self.run_cli(load("mechanics-intent.json"), load("mechanics-measured.json"), 0)


if __name__ == "__main__":
    unittest.main()
