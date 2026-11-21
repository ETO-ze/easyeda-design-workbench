"""Offline, standard-library regression tests for the check_pcb_pins.py CLI."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile


CHECKER = Path(__file__).resolve().parents[1] / "scripts" / "check_pcb_pins.py"


def record(kind, body, obj_id=None, ticket=1):
    head = {"type": kind, "ticket": ticket}
    if obj_id is not None:
        head["id"] = obj_id
    return json.dumps(head) + "||" + (json.dumps(body) if body is not None else "") + "|"


def pad(net, ticket=1, parent="component-1"):
    key = json.dumps(["PAD_NET", parent, "1", 0])
    return record("PAD_NET", {"padNet": net} if net is not None else None, key, ticket)


def board(uuid="pcb-a", title="Main", net="GND"):
    return [
        record("DOCHEAD", {"docType": "PCB", "uuid": uuid}),
        record("META", {"title": title}),
        record("COMPONENT", {}, "component-1"),
        record("ATTR", {"key": "Designator", "value": "J1", "parentId": "component-1"}, "ref-1"),
        pad(net),
    ]


class CheckPcbPinsTest(unittest.TestCase):
    def invoke(self, lines, *args, archive=False, contract='{"J1":{"1":"GND"}}'):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content = "\n".join(lines)
            if archive:
                source = root / "snapshot.zip"
                with ZipFile(source, "w") as bundle:
                    bundle.writestr("nested/pcb.epru", content)
            else:
                source = root / "snapshot.epru"
                source.write_text(content, encoding="utf-8")
            expected = root / "contract.json"
            expected.write_text(contract, encoding="utf-8")
            return subprocess.run(
                [sys.executable, "-I", str(CHECKER), str(source), str(expected), *args],
                cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=15, check=False,
            )

    def verdict(self, result, exit_code):
        self.assertEqual(result.returncode, exit_code, result.stderr or result.stdout)
        report = json.loads(result.stdout)
        self.assertIs(report["passed"], exit_code == 0)
        return report

    def assert_input_error(self, result):
        self.assertEqual(result.returncode, 2, result.stdout or result.stderr)
        self.assertTrue(result.stderr.strip(), "input errors must provide a diagnostic")
        self.assertFalse(result.stdout.strip(), "input errors must not publish a verdict")

    def test_zipped_export_selects_requested_uuid_and_returns_matching_pad(self):
        # Both boards use the same internal component ID, ref and pad.
        for selection in ("pcb-a", "Main"):
            with self.subTest(selection=selection):
                report = self.verdict(self.invoke(
                    board() + board("pcb-b", "Other", "VCC"), "--pcb", selection, archive=True,
                ), 0)
                self.assertEqual(report["pcb"], "pcb-a")
                self.assertEqual(report["pins"], [
                    {"ref": "J1", "pad": "1", "expected": "GND", "actual": ["GND"], "result": "match"},
                ])

    def test_wrong_net_reports_observed_assignment_and_exit_one(self):
        report = self.verdict(self.invoke(board(net="VCC")), 1)
        self.assertEqual(report["pins"], [
            {"ref": "J1", "pad": "1", "expected": "GND", "actual": ["VCC"], "result": "wrong-net"},
        ])

    def test_wrong_missing_or_ambiguous_board_selection_is_an_input_error(self):
        lines = board() + board("pcb-b", "Main", "VCC")
        for args in [(), ("--pcb", "Main"), ("--pcb", "unknown-uuid")]:
            with self.subTest(args=args):
                self.assert_input_error(self.invoke(lines, *args))

    def test_duplicate_designator_cannot_pass_even_if_one_matches(self):
        extra = [
            record("COMPONENT", {}, "component-2"),
            record("ATTR", {"key": "Designator", "value": "J1", "parentId": "component-2"}, "ref-2"),
            pad("VCC", parent="component-2"),
        ]
        report = self.verdict(self.invoke(board() + extra), 1)
        self.assertEqual(report["pins"][0]["result"], "ambiguous-designator")

    def test_highest_pad_revision_wins_over_later_lower_ticket(self):
        report = self.verdict(self.invoke(board(net="VCC") + [pad("GND", 3), pad("VCC", 2)]), 0)
        self.assertEqual(report["pins"][0]["actual"], ["GND"])

    def test_tombstone_does_not_resurrect_a_stale_pad(self):
        report = self.verdict(self.invoke(board() + [pad(None, 3), pad("GND", 2)]), 1)
        self.assertEqual(report["pins"][0]["result"], "missing-pad-assignment")
        self.assertEqual(report["pins"][0]["actual"], [])

    def test_deleted_board_does_not_participate_in_selection(self):
        lines = board() + board("pcb-b", "Main", "VCC") + [record("DELETE_DOC", {"isDelete": True})]
        self.assertEqual(self.verdict(self.invoke(lines), 0)["pcb"], "pcb-a")
        self.assert_input_error(self.invoke(lines, "--pcb", "pcb-b"))

    def test_contradictory_same_ticket_is_an_input_error(self):
        self.assert_input_error(self.invoke(board() + [pad("VCC", 1)]))

    def test_invalid_record_and_duplicate_contract_pin_are_input_errors(self):
        self.assert_input_error(self.invoke(["broken record"]))
        self.assert_input_error(self.invoke(board(), contract='{"J1":{"1":"VCC","1":"GND"}}'))


if __name__ == "__main__":
    unittest.main()
