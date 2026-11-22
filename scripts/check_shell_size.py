"""Check only the axis-aligned outer envelope of STL parts in their exported frame."""

import argparse
import json
import math
import re
import struct
import sys
from decimal import Decimal, InvalidOperation
from fractions import Fraction

from workbench import add_shell_size_options


FACET = struct.Struct("<12fH")
NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")


def number(text):
    if len(text) > 64 or not NUMBER.fullmatch(text):
        raise ValueError("expected a finite decimal number")
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("invalid decimal number") from exc
    if abs(value.as_tuple().exponent) > 80:
        raise ValueError("numeric exponent outside supported range")
    return value


def binary_triangles(stream, count):
    stream.seek(84)
    for _ in range(count):
        record = stream.read(FACET.size)
        if len(record) != FACET.size:
            raise ValueError("truncated binary facet")
        values = FACET.unpack(record)[:12]
        if not all(map(math.isfinite, values)):
            raise ValueError("non-finite binary STL normal or vertex")
        yield values[3:6], values[6:9], values[9:12]
    if stream.read(1):
        raise ValueError("unexpected bytes after binary facets")


def ascii_lines(stream):
    # Bound individual reads even when a damaged binary header starts with "solid".
    for line in iter(lambda: stream.readline(4097), b""):
        if len(line) > 4096:
            raise ValueError("ASCII STL line exceeds 4096 bytes")
        words = line.decode("ascii").split()
        if words:
            yield words


def ascii_triangles(stream):
    stream.seek(0)
    lines = ascii_lines(stream)

    def take(*prefix, vector=False):
        words = next(lines, [])
        if words[:len(prefix)] != list(prefix) or len(words) != len(prefix) + (3 if vector else 0):
            raise ValueError(f"expected ASCII STL {' '.join(prefix)}")
        if vector:
            return tuple(number(s) for s in words[len(prefix):])

    header = next(lines, [])
    while header:
        if header[0] != "solid":
            raise ValueError("expected ASCII STL solid header")
        words = next(lines, [])
        while words[:1] != ["endsolid"]:
            if words[:2] != ["facet", "normal"] or len(words) != 5:
                raise ValueError("expected ASCII STL facet normal or endsolid")
            for s in words[2:]:
                number(s)
            take("outer", "loop")
            points = [take("vertex", vector=True) for _ in range(3)]
            take("endloop")
            take("endfacet")
            yield points
            words = next(lines, [])
        if len(words) > 1 and words[1:] != header[1:]:
            raise ValueError("ASCII STL endsolid name differs from solid name")
        header = next(lines, [])


def read_part(path):
    try:
        with path.open("rb") as stream:
            size = stream.seek(0, 2)
            stream.seek(0)
            header = stream.read(84)
            # Length + count distinguish valid binary files, even with a "solid" header.
            if len(header) == 84 and size == 84 + int.from_bytes(header[80:], "little") * FACET.size:
                fmt = "binary"
                triangles = binary_triangles(stream, (size - 84) // FACET.size)
            else:
                fmt = "ascii"
                triangles = ascii_triangles(stream)
            lo, hi = [math.inf] * 3, [-math.inf] * 3
            count = 0
            for triangle in triangles:
                count += 1
                for point in triangle:
                    for i, v in enumerate(point):
                        if v < lo[i]:
                            lo[i] = v
                        if v > hi[i]:
                            hi[i] = v
            if not count:
                raise ValueError("STL has no triangles")
    except (OSError, ValueError) as exc:
        raise ValueError(f"{path}: {exc}") from exc
    return fmt, count, list(map(Fraction, lo)), list(map(Fraction, hi))


def box(lo, hi):
    return {"min_mm": list(map(float, lo)), "max_mm": list(map(float, hi)),
            "size_mm": [float(b - a) for a, b in zip(lo, hi)]}


def measure(args):
    expected = [Fraction(number(s)) for s in args.expected_mm]
    tolerance = Fraction(number(args.tolerance_mm))
    if min(expected) <= 0 or not 0 <= tolerance < min(expected):
        raise ValueError("targets must be positive and 0 <= tolerance < the smallest target")
    parts, lows, highs = [], [], []
    for path in args.parts:
        fmt, count, lo, hi = read_part(path)
        parts.append({"path": str(path), "format": fmt, "triangles": count, **box(lo, hi)})
        lows.append(lo)
        highs.append(hi)
    lo = list(map(min, zip(*lows)))
    hi = list(map(max, zip(*highs)))
    failed = [axis for axis, a, b, target in zip("XYZ", lo, hi, expected)
              if abs((b - a) - target) > tolerance]
    return {"passed": not failed, "failed_axes": failed,
            "scope": "Axis-aligned outer envelope only; assumes a common assembled frame. Not a fit or clearance test.",
            "parts": parts, "union": box(lo, hi), "expected_mm": list(map(float, expected)),
            "tolerance_mm": float(tolerance)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_shell_size_options(parser)
    args = parser.parse_args()
    try:
        result = measure(args)
    except ValueError as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
