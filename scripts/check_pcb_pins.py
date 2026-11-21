"""Compare a pin contract with pad-net assignments in an EasyEDA Pro EPRU snapshot."""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from zipfile import BadZipFile, ZipFile


MAX_SOURCE = 128 * 1024 * 1024
TYPES = {"META", "DELETE_DOC", "COMPONENT", "ATTR", "PAD_NET"}


def read_source(path):
    if path.suffix.lower() == ".zip":
        with ZipFile(path) as archive:
            entries = [i for i in archive.infolist() if not i.is_dir() and i.filename.lower().endswith(".epru")]
            if len(entries) != 1:
                raise ValueError("ZIP must contain exactly one .epru member")
            if entries[0].file_size > MAX_SOURCE:
                raise ValueError("EPRU exceeds the 128 MiB input limit")
            return archive.read(entries[0]).decode("utf-8-sig")
    if path.suffix.lower() != ".epru":
        raise ValueError("expected an .epru file or a ZIP containing one")
    if path.stat().st_size > MAX_SOURCE:
        raise ValueError("EPRU exceeds the 128 MiB input limit")
    return path.read_text(encoding="utf-8-sig")


def select_board(text, selector):
    boards = {}
    current = None
    decoder = json.JSONDecoder()
    for index, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        head, end = decoder.raw_decode(line)
        tail = line[end:].lstrip()
        if not isinstance(head, dict) or not tail.startswith("||"):
            raise ValueError(f"invalid EPRU record at line {index}")
        kind = head.get("type")
        if kind != "DOCHEAD" and (current is None or kind not in TYPES):
            continue
        raw_body = tail[2:].removesuffix("|").strip()
        body = json.loads(raw_body) if raw_body else None
        if body == "":
            body = None
        if body is not None and not isinstance(body, dict):
            raise ValueError(f"unexpected record body at line {index}")
        if kind == "DOCHEAD":
            if not body or not body.get("docType"):
                raise ValueError(f"incomplete document header at line {index}")
            current = None
            if body["docType"] == "PCB":
                uuid = body.get("uuid")
                if not isinstance(uuid, str) or not uuid:
                    raise ValueError("PCB header is missing its UUID")
                current = boards.setdefault(uuid, {})
            continue
        obj_id = head.get("id", kind)
        if not isinstance(obj_id, str) or (obj_id == kind and kind not in {"META", "DELETE_DOC"}):
            raise ValueError(f"invalid object ID at line {index}")
        key = kind, obj_id
        ticket = head.get("ticket")
        if type(ticket) is not int:
            raise ValueError(f"invalid revision ticket at line {index}")
        old = current.get(key)
        if old is not None and old[0] == ticket and old[1] != body:
            raise ValueError("ambiguous same-ticket PCB revisions; export a single-client snapshot")
        if old is None or ticket > old[0]:
            current[key] = ticket, body
    matches = []
    for uuid, revisions in boards.items():
        live = {k: body for k, (_, body) in revisions.items() if body is not None}
        if any(k == "DELETE_DOC" and b.get("isDelete") for (k, _), b in live.items()):
            continue
        titles = {b.get("title") for (k, _), b in live.items() if k == "META"}
        if selector is None or selector == uuid or selector in titles:
            matches.append((uuid, live))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one matching PCB; found {len(matches)} (select by UUID with --pcb)")
    return matches[0]


def unique_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate key in pin contract")
        obj[key] = value
    return obj


def compare(live, expected):
    if not isinstance(expected, dict) or not expected:
        raise ValueError("expected non-empty {designator: {pad: net}} JSON")
    components = {cid for kind, cid in live if kind == "COMPONENT"}
    names = defaultdict(set)
    refs = defaultdict(set)
    pads = defaultdict(set)
    for (kind, obj_id), body in live.items():
        if kind == "ATTR" and body.get("key") == "Designator":
            cid, ref = body.get("parentId"), body.get("value")
            if cid in components and isinstance(ref, str):
                names[cid].add(ref)
                refs[ref].add(cid)
        if kind == "PAD_NET":
            fields = json.loads(obj_id)
            if not isinstance(fields, list) or len(fields) != 4 or fields[0] != "PAD_NET":
                raise ValueError("unsupported PCB pad-net ID")
            _, cid, pad, _ = fields
            net = body.get("padNet")
            if not isinstance(cid, str) or type(pad) not in (str, int) or net is not None and not isinstance(net, str):
                raise ValueError("unsupported PCB pad-net assignment")
            pads[cid, str(pad)].add(net or "")
    results = []
    for ref, wanted in expected.items():
        if not ref.strip() or not isinstance(wanted, dict) or not wanted:
            raise ValueError("each designator must have a non-empty pad contract")
        ids = refs[ref]
        for pin, net in wanted.items():
            if not pin.strip() or not isinstance(net, str) or not net.strip():
                raise ValueError("each expected pin and net must be a non-empty string")
            actual = set()
            if len(ids) == 1:
                cid = next(iter(ids))
                actual = pads[cid, pin]
                if len(names[cid]) != 1:
                    verdict = "ambiguous-designator"
                elif not actual:
                    verdict = "missing-pad-assignment"
                elif len(actual) > 1:
                    verdict = "conflicting-pad-assignments"
                else:
                    verdict = "match" if actual == {net} else "wrong-net"
            else:
                verdict = "ambiguous-designator" if ids else "missing-designator"
            results.append(dict(ref=ref, pad=pin, expected=net, actual=sorted(actual), result=verdict))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("contract", type=Path, help="UTF-8 JSON mapping designator to {pad: net}")
    parser.add_argument("--pcb", help="exact PCB UUID or unique title")
    args = parser.parse_args()
    try:
        expected = json.loads(args.contract.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_keys)
        uuid, live = select_board(read_source(args.source), args.pcb)
        results = compare(live, expected)
    except (OSError, ValueError, BadZipFile, RuntimeError, RecursionError) as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2
    passed = all(row["result"] == "match" for row in results)
    print(json.dumps(dict(pcb=uuid, scope="requested PCB pad-net assignments", passed=passed, pins=results),
                     ensure_ascii=True, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
