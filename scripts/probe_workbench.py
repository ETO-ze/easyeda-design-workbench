"""Print a read-only inventory of a local EasyEDA workbench (Python 3.9+)."""

import argparse
import http.client
import json
import os
import shutil
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


SKILLS = (
    "easyeda-api", "easyeda-project-guardian", "easyeda-schematic-audit",
    "easyeda-cardwallet-placement", "easyeda-pcb-routing", "easyeda-design-workbench",
)


def read_endpoint(port, path):
    # Direct loopback; do not use environment proxies or follow redirects.
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
    try:
        conn.request("GET", path, headers={"Accept": "application/json"})
        response = conn.getresponse()
        if response.status != 200:
            raise ValueError(f"{path} HTTP {response.status}")
        raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError(f"{path} response too large")
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise ValueError(f"{path} invalid JSON") from exc
        if not isinstance(data, dict):
            raise ValueError(f"{path} expected an object")
        return data
    finally:
        conn.close()


def gateway(port):
    result = {"port": port, "connected_windows": None,
              "can_probe_document": False, "document_verified": False}
    try:
        health = read_endpoint(port, "/health")
        if health.get("service") != "easyeda-bridge":
            return dict(result, state="different_service")
        windows = read_endpoint(port, "/eda-windows").get("windows")
        if not isinstance(windows, list) or any(
                not isinstance(w, dict) or type(w.get("connected")) is not bool or
                (w["connected"] and not isinstance(w.get("windowId"), str)) or
                (w["connected"] and not w["windowId"].strip()) for w in windows):
            raise ValueError("/eda-windows invalid window list")
        ids = [w["windowId"] for w in windows if w["connected"]]
        if len(set(ids)) != len(ids):
            raise ValueError("/eda-windows duplicate connected window")
        if health.get("edaConnected") is not bool(ids):
            raise ValueError("health/window observations disagree; retry")
        state = ("no_window" if not ids else "choose_window" if len(ids) > 1
                 else "ready_for_context_probe")
        result.update(state=state, connected_windows=len(ids),
                      can_probe_document=len(ids) == 1)
    except (TimeoutError, OSError, http.client.HTTPException) as exc:
        result.update(state="unreachable", detail=type(exc).__name__)
    except ValueError as exc:
        result.update(state="invalid_response", detail=str(exc))
    return result


def inspect_install(tools_dir, skills_dir):
    engine = tools_dir / "eprj3-v1.36.1"
    checker = tools_dir / "easyeda-pcb-design-bc3c736" / "scripts"
    package = {}
    manifest_issue = None
    try:
        package = json.loads((engine / "package.json").read_text(encoding="utf-8"))
        if not isinstance(package, dict) or package.get("name") != "easyeda-eprj3-skill":
            raise ValueError("unexpected package")
    except (OSError, ValueError) as exc:
        package = {}
        manifest_issue = type(exc).__name__
    try:
        shapely = version("shapely")
    except PackageNotFoundError:
        shapely = None
    return {
        "offline_engine": {"entry_present": (engine / "scripts/make-board.js").is_file(),
                           "version_from_manifest": package.get("version"),
                           "manifest_issue": manifest_issue, "node_on_path": bool(shutil.which("node"))},
        "copper_checker": {"entry_present": (checker / "check_copper_connectivity.py").is_file(),
                           "parser_present": (checker / "check_manufacturing.py").is_file(),
                           "shapely_in_this_python": shapely, "requires_shapely": ">=2,<3"},
        "skill_files_present": {name: (skills_dir / name / "SKILL.md").is_file() for name in SKILLS},
    }


def main():
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools-dir", type=Path, default=home / "easyeda-tools")
    parser.add_argument("--skills-dir", type=Path, default=home / "skills")
    parser.add_argument("--port", type=int, choices=range(49620, 49630), default=49620)
    args = parser.parse_args()
    snapshot = inspect_install(args.tools_dir, args.skills_dir)
    snapshot["gateway"] = gateway(args.port)
    print(json.dumps(snapshot, indent=2))


if __name__ == "__main__":
    main()
