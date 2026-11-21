import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/workbench.py"
spec = importlib.util.spec_from_file_location("workbench_cli", SCRIPT)
wb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wb)


class WorkbenchTests(unittest.TestCase):
    def test_draft_refuses_existing_dest_without_invoking_builder(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            script = base / wb.ENGINE / "scripts/make-board.js"
            script.parent.mkdir(parents=True)
            script.touch()
            design = base / "design.json"
            design.touch()
            with patch.object(wb.shutil, "which", return_value="node"), patch.object(wb.subprocess, "run") as child:
                with self.assertRaises(SystemExit) as raised:
                    wb.run(["--tools-dir", tmp, "draft", tmp, "--design", str(design)])
                self.assertEqual(2, raised.exception.code)
                child.assert_not_called()

    def test_pins_forwards_nonzero_result_and_board_selector(self):
        with patch.object(wb.subprocess, "run", return_value=subprocess.CompletedProcess([], 1)) as child:
            self.assertEqual(1, wb.run(["pins", "export.zip", "expected.json", "--pcb", "abcd"]))
            argv = child.call_args.args[0]
            self.assertEqual([sys.executable, "-B"], argv[:2])
            self.assertEqual(["export.zip", "expected.json", "--pcb", "abcd"], argv[-4:])

    def test_copper_never_overwrites_existing_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            script = base / wb.COPPER / "scripts/check_copper_connectivity.py"
            script.parent.mkdir(parents=True)
            script.touch()
            f = base / "sentinel"
            f.write_text("keep", encoding="utf-8")
            with patch.object(wb.subprocess, "run") as child, self.assertRaises(SystemExit):
                wb.run(["--tools-dir", tmp, "copper", str(f), str(f), "--out", str(f)])
            child.assert_not_called()
            self.assertEqual("keep", f.read_text(encoding="utf-8"))
