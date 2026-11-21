import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/probe_workbench.py"
spec = importlib.util.spec_from_file_location("probe_workbench", SCRIPT)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class ProbeTests(unittest.TestCase):
    def assert_inventory(self, windows, connected, state, count, can_probe):
        health = {"service": "easyeda-bridge", "edaConnected": connected}
        with patch.object(probe, "read_endpoint", side_effect=[health, {"windows": windows}]) as get:
            result = probe.gateway(49620)
        self.assertEqual([call(49620, "/health"), call(49620, "/eda-windows")], get.call_args_list)
        self.assertEqual(state, result["state"])
        self.assertEqual(count, result["connected_windows"])
        self.assertEqual(can_probe, result["can_probe_document"])
        self.assertFalse(result["document_verified"])

    def test_healthy_bridge_with_no_editor(self):
        self.assert_inventory([], False, "no_window", 0, False)

    def test_one_connected_window_allows_context_read(self):
        self.assert_inventory([{"connected": True, "windowId": "w1"}],
                              True, "ready_for_context_probe", 1, True)

    def test_multiple_windows_require_target(self):
        windows = [{"connected": True, "windowId": key} for key in ("w1", "w2")]
        self.assert_inventory(windows, True, "choose_window", 2, False)

    def test_connected_window_needs_usable_id(self):
        self.assert_inventory([{"connected": True}], True, "invalid_response", None, False)

    def test_fresh_machine_requires_no_installed_optional_tools(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(probe.shutil, "which", return_value=None), \
                patch.object(probe, "version", side_effect=probe.PackageNotFoundError):
            root = Path(tmp)
            inventory = probe.inspect_install(root / "missing-tools", root / "missing-skills")
            self.assertEqual([], list(root.iterdir()))
        self.assertFalse(inventory["offline_engine"]["entry_present"])
        self.assertIsNone(inventory["offline_engine"]["version_from_manifest"])
        self.assertFalse(inventory["offline_engine"]["node_on_path"])
        self.assertFalse(inventory["copper_checker"]["entry_present"])
        self.assertIsNone(inventory["copper_checker"]["shapely_in_this_python"])
        self.assertTrue(inventory["skill_files_present"])
        self.assertFalse(any(inventory["skill_files_present"].values()))
