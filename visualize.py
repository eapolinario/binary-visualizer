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
Grid3DCounts = DefaultDict[Tuple[int, int, int], int]


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
    parser.add_argument(
        "--mode",
        choices=("2d", "3d"),
        default="2d",
        help=(
            "Visualization mode. '2d' (default) scans byte pairs for a single "
            "256x256 heatmap. '3d' scans byte triplets and outputs 256 slice "
            "images representing a 256x256x256 volume."
        ),
    )
    return parser.parse_args()


def scan_pairs(path: Path) -> GridCounts:
    """Return a grid of pair frequencies keyed by ``(x, y)`` tuples."""

    counts: GridCounts = defaultdict(int)
    with path.open("rb") as handle:
        prev = None
        while True:
            chunk = handle.read(1024 * 1024 * 1024)  # 1 GiB chunks
            if not chunk:
                break

            if prev is not None:
                counts[(prev, chunk[0])] += 1

            for i in range(len(chunk) - 1):
                counts[(chunk[i], chunk[i + 1])] += 1

            prev = chunk[-1]
    return counts


def scan_triplets(path: Path) -> Grid3DCounts:
    """Return a 3D grid of triplet frequencies keyed by ``(x, y, z)`` tuples."""

    counts: Grid3DCounts = defaultdict(int)
    with path.open("rb") as handle:
        prev1 = None
        prev2 = None
        while True:
            chunk = handle.read(1024 * 1024 * 1024)  # 1 GiB chunks
            if not chunk:
                break

            # Handle boundary between chunks
            if prev1 is not None and prev2 is not None and len(chunk) >= 1:
                counts[(prev1, prev2, chunk[0])] += 1
            if prev2 is not None and len(chunk) >= 2:
                counts[(prev2, chunk[0], chunk[1])] += 1

            # Scan triplets within the chunk
            for i in range(len(chunk) - 2):
                counts[(chunk[i], chunk[i + 1], chunk[i + 2])] += 1

            # Keep last two bytes for next chunk
            if len(chunk) >= 2:
                prev1 = chunk[-2]
                prev2 = chunk[-1]
            elif len(chunk) == 1:
                prev1 = prev2
                prev2 = chunk[0]

    return counts


def max_count(counts: GridCounts) -> int:
    """Return the maximum frequency present in the grid."""

    return max(counts.values(), default=0)


def max_count_3d(counts: Grid3DCounts) -> int:
    """Return the maximum frequency present in the 3D grid."""

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


def write_ppm_slices(
    counts: Grid3DCounts, peak: int, output: Path, scale: str
) -> None:
    """Write 256 PPM slices representing the 3D volume.

    Each slice fixes the first byte (z-axis) and shows a 256x256 heatmap of
    the second and third bytes. Output files are named <output>_slice_000.ppm
    through <output>_slice_255.ppm.
    """

    output_dir = output.parent
    output_stem = output.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    for z in range(256):
        slice_path = output_dir / f"{output_stem}_slice_{z:03d}.ppm"
        with slice_path.open("w", encoding="ascii") as handle:
            handle.write("P3\n256 256\n255\n")
            for y in range(256):
                row_values = []
                for x in range(256):
                    count = counts.get((z, x, y), 0)
                    value = brightness(count, peak, scale)
                    row_values.append(f"{value} {value} {value}")
                handle.write(" ".join(row_values) + "\n")

    print(f"Wrote 256 slices to {output_dir}/{output_stem}_slice_*.ppm")


def main() -> None:
    args = parse_args()

    if args.mode == "2d":
        counts = scan_pairs(args.input)
        peak = max_count(counts)
        write_ppm(counts, peak, args.output, args.scale)
    else:  # 3d mode
        counts_3d = scan_triplets(args.input)
        peak = max_count_3d(counts_3d)
        write_ppm_slices(counts_3d, peak, args.output, args.scale)


if __name__ == "__main__":
    main()
