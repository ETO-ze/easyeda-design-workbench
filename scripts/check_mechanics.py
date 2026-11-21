"""Compare declared PCB mounting holes and connector orientations (not a fit test).

Distances and both tolerances use each file's explicit unit (mm or mil).
Center tolerance is a radius, drill tolerance is an absolute diameter error.
Frame axes are directions on the drawing as viewed from the declared side.
Insertion is plug motion toward its receptacle along a declared board axis:
+x/-x/+y/-y, or into-view/out-of-view perpendicular to the drawing.
The hole and interface lists are complete for the agreed inspection scope.
"""

import argparse
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from math import sqrt
from pathlib import Path


SCALE = {"mm": Fraction(1), "mil": Fraction(127, 5000)}
SIDES = ("top", "bottom")
INSERTIONS = ("+x", "-x", "+y", "-y", "into-view", "out-of-view")


def unique_dict(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_dict,
                      parse_float=Decimal, parse_int=Decimal, parse_constant=Decimal)


def obj(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label}: expected a JSON object")
    return value


def choice(value, options, label):
    if not isinstance(value, str) or value not in options:
        raise ValueError(f"{label}: expected one of {', '.join(options)}")
    return value


def distance(value, scale, label):
    # Bound numerical precision/exponents before conversion to exact fractions.
    if (not isinstance(value, Decimal) or not value.is_finite()
            or len(value.as_tuple().digits) > 40 or abs(value.as_tuple().exponent) > 80):
        raise ValueError(f"{label}: expected a finite JSON number of practical precision")
    return Fraction(value) * scale


def parse(data, intent):
    obj(data, "document")
    scale = SCALE[choice(data.get("unit"), SCALE, "unit")]
    f = obj(data.get("frame"), "frame")
    origin = f.get("origin")
    if not isinstance(origin, str) or not origin.strip():
        raise ValueError("frame.origin: specify the common physical datum")
    frame = {
        "origin": origin,
        "view": choice(f.get("view"), SIDES, "frame.view"),
        "x_positive": choice(f.get("x_positive"), ("right", "left"), "frame.x_positive"),
        "y_positive": choice(f.get("y_positive"), ("up", "down"), "frame.y_positive"),
    }
    if set(f) != set(frame):
        raise ValueError("frame: unrecognized coordinate declaration; no transforms are inferred")
    holes = {}
    for ref, hole in obj(data.get("holes"), "holes").items():
        if not re.fullmatch(r"MH[0-9]+", ref):
            raise ValueError(f"holes.{ref}: expected an MH designator such as MH1")
        point = obj(hole, ref).get("center")
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError(f"{ref}.center: expected [x,y]")
        xy = [distance(v, scale, f"{ref}.center") for v in point]
        drill = distance(hole.get("drill"), scale, f"{ref}.drill")
        if drill <= 0:
            raise ValueError(f"{ref}.drill: must be positive")
        holes[ref] = (*xy, drill)
    interfaces = {}
    for ref, port in obj(data.get("interfaces"), "interfaces").items():
        if not ref.strip() or ref != ref.strip() or ref in holes:
            raise ValueError(f"invalid interface designator {ref!r}")
        obj(port, ref)
        interfaces[ref] = {"side": choice(port.get("side"), SIDES, f"{ref}.side"),
                           "insertion": choice(port.get("insertion"), INSERTIONS, f"{ref}.insertion")}
    tol = None
    if intent:
        if not holes or not interfaces:
            raise ValueError("intent needs at least one mounting hole and one physical interface")
        t = obj(data.get("tolerance"), "tolerance")
        tol = tuple(distance(t.get(k), scale, f"tolerance.{k}") for k in ("center", "drill"))
        if min(tol) < 0:
            raise ValueError("tolerance: negative tolerances are not allowed")
    return frame, holes, interfaces, tol


def aligned(wanted, observed, delta):
    result = {}
    for ref in sorted(wanted.keys() | observed.keys()):
        if ref not in observed:
            result[ref] = {"passed": False, "result": "missing"}
        elif ref not in wanted:
            result[ref] = {"passed": False, "result": "unexpected"}
        else:
            result[ref] = delta(wanted[ref], observed[ref])
    return result


def compare(intent, measured):
    frame, holes, interfaces, (ctr_tol, drill_tol) = parse(intent, True)
    actual_frame, actual_holes, actual_interfaces, _ = parse(measured, False)
    if frame != actual_frame:
        diff = {k: (frame[k], actual_frame[k]) for k in frame if frame[k] != actual_frame[k]}
        raise ValueError(f"coordinate frames differ (expected, measured): {diff}; no automatic transform")

    def hole_delta(a, b):
        radius_squared = (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
        drill_error = abs(a[2] - b[2])
        return {"passed": radius_squared <= ctr_tol ** 2 and drill_error <= drill_tol,
                "expected_mm": list(map(float, a)), "observed_mm": list(map(float, b)),
                "center_error_mm": sqrt(radius_squared), "drill_error_mm": float(drill_error)}

    hd = aligned(holes, actual_holes, hole_delta)
    ports = aligned(interfaces, actual_interfaces,
                    lambda a, b: {"passed": a == b, "expected": a, "observed": b})
    return {"passed": all(v["passed"] for group in (hd, ports) for v in group.values()),
            "scope": "Declared mounting-hole centers/drills and interface orientations only; not physical fit.",
            "frame": frame, "tolerance_mm": {"center": float(ctr_tol), "drill": float(drill_tol)},
            "holes": hd, "interfaces": ports}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("expected", type=Path, help="mechanical intent JSON")
    parser.add_argument("measured", type=Path, help="independent measurement JSON")
    args = parser.parse_args()
    try:
        result = compare(read_json(args.expected), read_json(args.measured))
    except (OSError, ValueError, InvalidOperation, RecursionError) as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
