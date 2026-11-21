import importlib.util
from pathlib import Path
import unittest
from unittest.mock import call, patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/read_context.py"
spec = importlib.util.spec_from_file_location("read_context", SCRIPT)
ctx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctx)


def replies(windows, **changes):
    reply = {"windowId": "w", "success": True, "result": {
        "project": "proj", "parent": "proj", "document": "pcb", "type": 3, "tab": "tab",
        "unexpected": "should be excluded"}}
    reply.update(changes)
    return [{"service": "easyeda-bridge", "edaConnected": bool(windows)},
            {"windows": [{"windowId": w, "connected": True} for w in windows]}, reply]


class ReadContextTests(unittest.TestCase):
    def test_explicit_window_pinned_in_multiclient_read(self):
        with patch.object(ctx, "request", side_effect=replies(["other", "w"])) as req:
            out = ctx.inspect(49620, "w")
        self.assertEqual("context_read", out["state"])
        self.assertEqual(("w", "pcb", "proj", 3), tuple(
            out[k] for k in ("window", "document_uuid", "project_uuid", "document_type")))
        self.assertNotIn("unexpected", out)
        self.assertEqual([call(49620, "/health"), call(49620, "/eda-windows"),
                          call(49620, "/execute", "w")], req.call_args_list)

    def test_no_editor_and_ambiguous_windows_require_no_execution(self):
        for ids, state in [([], "no_window"), (["a", "b"], "choose_window")]:
            with self.subTest(ids=ids), patch.object(ctx, "request", side_effect=replies(ids)) as req:
                out = ctx.inspect(49620)
                self.assertEqual(state, out["state"])
                if ids:
                    self.assertEqual(ids, out["windows"])
                self.assertEqual(2, req.call_count)

    def test_wrong_window_fails(self):
        with patch.object(ctx, "request", side_effect=replies(["w"], windowId="other")):
            with self.assertRaisesRegex(ValueError, "wrong reply window"):
                ctx.inspect(49620)

    def test_wrong_document_owner_fails(self):
        detail = {"project": "proj", "document": "doc", "type": 1, "parent": "other"}
        with patch.object(ctx, "request", side_effect=replies(["w"], result=detail)):
            with self.assertRaisesRegex(ValueError, "different project"):
                ctx.inspect(49620)

    def test_unopened_document(self):
        with patch.object(ctx, "request", side_effect=replies(["w"], result={"document": None})):
            self.assertEqual("no_active_project_document", ctx.inspect(49620)["state"])
