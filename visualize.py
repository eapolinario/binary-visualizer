"""Binary byte-pair visualizer.

This module scans a binary file with a sliding two-byte window, interprets each
pair as coordinates on a 256x256 plane, and emits a grayscale PPM heatmap where
more frequent pairs appear brighter. Counts are stored in a dictionary keyed by
``(x, y)`` pairs for direct lookups.
"""

from __future__ import annotations

import argparse
import math
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Tuple


GridCounts = DefaultDict[Tuple[int, int], int]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Scan a binary file with a sliding byte window and render a 256x256 "
            "PPM heatmap where brighter pixels represent more frequent pairs."
        )
    )
    parser.add_argument("input", type=Path, help="Path to the input binary file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("output.ppm"),
        help="Destination path for the generated PPM image (default: output.ppm)",
    )
    parser.add_argument(
        "--scale",
        choices=("linear", "sqrt", "log"),
        default="log",
        help=(
            "Tone-mapping curve for brightness. 'log' (default) highlights rare "
            "pairs, 'sqrt' is softer, and 'linear' matches the raw counts."
        ),
    )
    return parser.parse_args()


def scan_pairs(path: Path) -> GridCounts:
    """Return a grid of pair frequencies keyed by ``(x, y)`` tuples."""

    counts: GridCounts = defaultdict(int)
    with path.open("rb") as handle:
        data = handle.read()
        if len(data) < 2:
            return counts

        for pair in zip(data, data[1:]):
            counts[pair] += 1

    return counts


def max_count(counts: GridCounts) -> int:
    """Return the maximum frequency present in the grid."""

    return max(counts.values(), default=0)


def brightness(value: int, max_value: int, mode: str) -> int:
    """Convert a count to a grayscale value (0-255) using the requested curve."""

    if value == 0 or max_value == 0:
        return 0

    ratio = value / max_value
    if mode == "log":
        ratio = math.log1p(value) / math.log1p(max_value)
    elif mode == "sqrt":
        ratio = math.sqrt(ratio)

    ratio = max(0.0, min(1.0, ratio))
    scaled = ratio * 255
    # ``max`` ensures the faintest non-zero pair is not pure black.
    return min(255, max(1, int(round(scaled))))


def write_ppm(counts: GridCounts, peak: int, output: Path, scale: str) -> None:
    """Write the grayscale visualization as an ASCII PPM file."""

    with output.open("w", encoding="ascii") as handle:
        handle.write("P3\n256 256\n255\n")
        for y in range(256):
            row_values = []
            for x in range(256):
                count = counts.get((x, y), 0)
                value = brightness(count, peak, scale)
                row_values.append(f"{value} {value} {value}")
            handle.write(" ".join(row_values) + "\n")


def main() -> None:
    args = parse_args()
    counts = scan_pairs(args.input)
    peak = max_count(counts)
    write_ppm(counts, peak, args.output, args.scale)


if __name__ == "__main__":
    main()
