"""One command for environment, draft creation, design intent, and copper checks."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ENGINE = "eprj3-v1.36.1"
COPPER = "easyeda-pcb-design-bc3c736"


def add_shell_size_options(parser):
    parser.add_argument("parts", type=Path, nargs="+", help="ASCII/binary shell STLs in the same assembled frame")
    parser.add_argument("--unit", choices=("mm",), required=True, help="declare STL coordinate units")
    parser.add_argument("--expected-mm", nargs=3, metavar=("X", "Y", "Z"), required=True,
                        help="positive target outer spans on the export axes")
    parser.add_argument("--tolerance-mm", required=True, help="absolute, inclusive per-axis tolerance")


def run(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
    parser.add_argument("--tools-dir", type=Path, default=root / "easyeda-tools")
    sub = parser.add_subparsers(dest="action", required=True)
    doctor = sub.add_parser("doctor", help="read-only environment snapshot; no project edits")
    doctor.add_argument("--port", type=int, default=49620, help="Gateway port 49620-49629")
    context = sub.add_parser("context", help="read current project and document IDs from a pinned Gateway window")
    context.add_argument("--port", type=int, default=49620)
    context.add_argument("--window", help="exact window ID; required to disambiguate multiple windows")
    demo = sub.add_parser("draft", help="build a new placed-only V4 project directory")
    demo.add_argument("dest", type=Path, help="fresh directory that does not already exist")
    demo.add_argument("--design", type=Path, help="design.json (default: official blink fixture)")
    pins = sub.add_parser("pins", help="compare expected electrical names on selected PCB pads")
    pins.add_argument("source", type=Path, help="EPRU or ZIP backup")
    pins.add_argument("contract", type=Path)
    pins.add_argument("--pcb", required=True, help="board UUID or unique board name")
    mech = sub.add_parser("mechanics", help="compare measured mechanical features against intent")
    mech.add_argument("intent", type=Path)
    mech.add_argument("measured", type=Path)
    shell = sub.add_parser("shell-size", help="check the assembled outer envelope of native shell STLs")
    add_shell_size_options(shell)
    cop = sub.add_parser("copper", help="test supported two-layer Gerber copper with independent expected pads")
    cop.add_argument("fab", type=Path)
    cop.add_argument("expected", type=Path)
    cop.add_argument("--out", type=Path, required=True, help="new report path")
    args = parser.parse_args(argv)
    tools = args.tools_dir.resolve()
    py = [sys.executable, "-B"]
    if args.action == "doctor":
        cmd = py + [HERE / "probe_workbench.py", "--tools-dir", tools, "--port", str(args.port)]
    elif args.action == "context":
        cmd = py + [HERE / "read_context.py", "--port", str(args.port)]
        if args.window is not None:
            cmd += ["--window", args.window]
    elif args.action == "pins":
        cmd = py + [HERE / "check_pcb_pins.py", args.source, args.contract, "--pcb", args.pcb]
    elif args.action == "mechanics":
        cmd = py + [HERE / "check_mechanics.py", args.intent, args.measured]
    elif args.action == "shell-size":
        cmd = py + [HERE / "check_shell_size.py", "--unit", args.unit, "--expected-mm", *args.expected_mm,
                    "--tolerance-mm", args.tolerance_mm, "--", *args.parts]
    elif args.action == "draft":
        engine = tools / ENGINE
        script = engine / "scripts/make-board.js"
        design = args.design or engine / "examples/designs/blink.json"
        node = shutil.which("node")
        if not node or not script.is_file() or not design.is_file():
            parser.error("draft requires Node, the pinned eprj3 engine, and a readable design input; run doctor")
        if args.dest.exists() or args.dest.is_symlink():
            parser.error("draft destination already exists; use a fresh directory")
        cmd = [node, script, "--design", design.resolve(), "--dir", args.dest.resolve()]
    else:
        script = tools / COPPER / "scripts/check_copper_connectivity.py"
        if not script.is_file():
            parser.error("copper engine missing; see scripts/install_tools.py")
        if not args.fab.is_file() or not args.expected.is_file():
            parser.error("expected an existing Gerber ZIP and independent pad map JSON")
        if args.out.exists() or args.out.is_symlink():
            parser.error("report path already exists; use a fresh report name")
        cmd = py + [script, args.fab, "--expected", args.expected, "--out", args.out]
    try:
        return subprocess.run([str(item) for item in cmd], check=False).returncode
    except OSError as exc:
        parser.exit(2, f"Cannot launch check: {exc}\n")


if __name__ == "__main__":
    sys.exit(run())
