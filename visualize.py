"""Binary byte-pair visualizer.

This module scans a binary file with a sliding two-byte window, interprets each
pair as coordinates on a 256x256 plane, and emits a grayscale PPM heatmap where
more frequent pairs appear brighter. Counts are stored in a dictionary that maps
the horizontal coordinate to a ``collections.Counter`` of vertical coordinates
to satisfy the requested data structure.
"""

from __future__ import annotations

import argparse
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import DefaultDict, Dict


GridCounts = DefaultDict[int, Counter]


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
        "--chunk-size",
        type=int,
        default=1 << 20,
        help="Number of bytes to read per chunk when streaming the file",
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
    parser.add_argument(
        "--gamma",
        type=float,
        default=0.4,
        help=(
            "Additional gamma correction applied after the tone-mapping curve. "
            "Values < 1 brighten rare pixels (default: 0.4); set to 1 to disable."
        ),
    )
    return parser.parse_args()


def scan_pairs(path: Path, chunk_size: int) -> GridCounts:
    """Return a dict-of-Counter grid with pair frequencies.

    The dictionary keys correspond to the X coordinate (first byte) and contain a
    Counter in which each key is the Y coordinate (second byte) of the pair.
    """

    counts: GridCounts = defaultdict(Counter)
    with path.open("rb") as handle:
        first_byte = handle.read(1)
        if not first_byte:
            return counts

        prev = first_byte[0]
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            for current in chunk:
                counts[prev][current] += 1
                prev = current

    return counts


def max_count(counts: GridCounts) -> int:
    """Return the maximum frequency present in the grid."""

    max_value = 0
    for column in counts.values():
        if column:
            column_max = column.most_common(1)[0][1]
            if column_max > max_value:
                max_value = column_max
    return max_value


def brightness(value: int, max_value: int, mode: str, gamma: float) -> int:
    """Convert a count to a grayscale value (0-255) using the requested curve."""

    if value == 0 or max_value == 0:
        return 0

    ratio = value / max_value
    if mode == "log":
        ratio = math.log1p(value) / math.log1p(max_value)
    elif mode == "sqrt":
        ratio = math.sqrt(ratio)

    ratio = max(0.0, min(1.0, ratio))
    if gamma > 0 and gamma != 1:
        ratio = ratio ** gamma

    scaled = ratio * 255
    # ``max`` ensures the faintest non-zero pair is not pure black.
    return min(255, max(1, int(round(scaled))))


def write_ppm(
    counts: GridCounts, peak: int, output: Path, scale: str, gamma: float
) -> None:
    """Write the grayscale visualization as an ASCII PPM file."""

    with output.open("w", encoding="ascii") as handle:
        handle.write("P3\n256 256\n255\n")
        for y in range(256):
            row_values = []
            for x in range(256):
                column = counts.get(x)
                count = column.get(y, 0) if column else 0
                value = brightness(count, peak, scale, gamma)
                row_values.append(f"{value} {value} {value}")
            handle.write(" ".join(row_values) + "\n")


def main() -> None:
    args = parse_args()
    counts = scan_pairs(args.input, args.chunk_size)
    peak = max_count(counts)
    write_ppm(counts, peak, args.output, args.scale, args.gamma)


if __name__ == "__main__":
    main()
