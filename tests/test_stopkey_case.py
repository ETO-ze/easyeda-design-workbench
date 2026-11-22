import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
STEMS = ("3DShell_StopKeyFinal_T.stl", "3DShell_StopKeyFinal_B.stl")


class StopKeyCaseTests(unittest.TestCase):
    def test_published_mesh_matches_assembly_envelope_not_sum_of_lid_heights(self):
        archive = ROOT / "assets/stopkey-r1-native-shell.zip"
        self.assertTrue(archive.is_file(), "the public example must be runnable without the editor")
        with tempfile.TemporaryDirectory() as dest, ZipFile(archive) as z:
            self.assertCountEqual(z.namelist(), STEMS)
            parts = [z.extract(name, dest) for name in STEMS]
            cmd = [sys.executable, "-B", str(ROOT / "scripts/workbench.py"), "shell-size", *parts,
                   "--unit", "mm", "--expected-mm", "160", "92", "33.2", "--tolerance-mm", "0.01"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(0, result.returncode, result.stderr or result.stdout)
            size = json.loads(result.stdout)["union"]["size_mm"]
            for measured, expected in zip(size, [160.0003, 92.0002, 33.2001], strict=True):
                self.assertAlmostEqual(measured, expected, delta=0.001)
