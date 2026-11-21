"""Inspect the active EasyEDA project/document on a pinned local Gateway window."""

import argparse
import http.client
import json


CONTEXT_QUERY = (
    "const p=await eda.dmt_Project.getCurrentProjectInfo();"
    "const d=await eda.dmt_SelectControl.getCurrentDocumentInfo();"
    "return {project:p?.uuid??null,document:d?.uuid??null,"
    "parent:d?.parentProjectUuid??null,type:d?.documentType??null,tab:d?.tabId??null};"
)


def request(port, path, window=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=6)
    try:
        if path == "/execute":
            payload = json.dumps({"windowId": window, "code": CONTEXT_QUERY})
            conn.request("POST", path, payload, {"Content-Type": "application/json"})
        else:
            conn.request("GET", path)
        response = conn.getresponse()
        if response.status != 200:
            raise ValueError(f"{path} HTTP {response.status}")
        data = response.read(65537)
        if len(data) > 65536:
            raise ValueError(f"{path} response too large")
        value = json.loads(data)
        if not isinstance(value, dict):
            raise ValueError(f"{path} expected JSON object")
        return value
    finally:
        conn.close()


def valid_id(value):
    return isinstance(value, str) and 0 < len(value.strip()) <= 256 and value == value.strip()


def inspect(port, window=None):
    health = request(port, "/health")
    if health.get("service") != "easyeda-bridge":
        raise ValueError("unexpected service identity")
    rows = request(port, "/eda-windows").get("windows")
    if not isinstance(rows, list) or not all(
            isinstance(row, dict) and type(row.get("connected")) is bool for row in rows):
        raise ValueError("invalid window inventory")
    ids = [row.get("windowId") for row in rows if row["connected"]]
    if not all(valid_id(i) for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("invalid or duplicate window ID")
    if health.get("edaConnected") is not bool(ids):
        raise ValueError("health/window inventory changed; retry")
    if not ids:
        return {"state": "no_window", "connected_windows": 0}
    if window is None and len(ids) > 1:
        return {"state": "choose_window", "windows": ids}
    selected = ids[0] if window is None else window
    if selected not in ids:
        raise ValueError("requested window is not connected")
    reply = request(port, "/execute", selected)
    if reply.get("success") is not True or reply.get("windowId") != selected:
        raise ValueError("execution failed or wrong reply window")
    ctx = reply.get("result")
    if not isinstance(ctx, dict):
        raise ValueError("missing context result")
    project, document = ctx.get("project"), ctx.get("document")
    if not project or not document:
        return {"state": "no_active_project_document", "window": selected}
    if not valid_id(project) or not valid_id(document) or type(ctx.get("type")) is not int:
        raise ValueError("invalid project/document identity or document type")
    if ctx.get("parent") is not None and ctx["parent"] != project:
        raise ValueError("document belongs to a different project")
    result = {"state": "context_read", "window": selected, "project_uuid": project,
              "document_uuid": document, "document_type": ctx["type"],
              "document_parent_confirmed": ctx.get("parent") == project}
    if valid_id(ctx.get("tab")):
        result["tab_id"] = ctx["tab"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, choices=range(49620, 49630), default=49620)
    parser.add_argument("--window", help="connected window ID (required when several are connected)")
    args = parser.parse_args()
    try:
        result = inspect(args.port, args.window)
    except (ValueError, OSError, http.client.HTTPException) as exc:
        print(json.dumps({"state": "read_failed", "detail": str(exc)}))
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result["state"] == "context_read" else 1


if __name__ == "__main__":
    raise SystemExit(main())
