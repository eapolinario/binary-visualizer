"""Binary byte-pair visualizer.

This module scans a binary file with a sliding two-byte window, interprets each
pair as coordinates on a 256x256 plane, and emits a grayscale PPM heatmap where
more frequent pairs appear brighter. Counts are stored in a dictionary keyed by
``(x, y)`` pairs for direct lookups.
"""
# /// script
# dependencies = [
#   "plotly",
# ]
# ///

from __future__ import annotations

import argparse
import math
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Tuple

try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


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
            "256x256 PPM heatmap. '3d' scans byte triplets and outputs an "
            "interactive HTML file with a 3D Plotly visualization."
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


def write_plotly_3d(
    counts: Grid3DCounts, peak: int, output: Path, scale: str
) -> None:
    """Write an interactive 3D Plotly visualization as HTML.

    Creates a 3D scatter plot where each point represents a byte triplet.
    Point size and color represent frequency (applying the selected tone mapping).
    Only non-zero triplets are displayed to keep the visualization manageable.
    """

    if not PLOTLY_AVAILABLE:
        raise ImportError(
            "Plotly is required for 3D visualization. "
            "Run this script with 'uv run' to automatically install dependencies."
        )

    # Extract non-zero triplets
    x_coords = []
    y_coords = []
    z_coords = []
    values = []
    opacities = []
    hover_text = []

    for (x, y, z), count in counts.items():
        if count > 0:
            x_coords.append(x)
            y_coords.append(y)
            z_coords.append(z)
            # Apply tone mapping to the count
            mapped_value = brightness(count, peak, scale)
            values.append(mapped_value)
            # Calculate opacity based on frequency (0.2 to 1.0 range)
            # More common points are more opaque
            opacity = 0.2 + (mapped_value / 255) * 0.8
            opacities.append(opacity)
            hover_text.append(
                f"Triplet: [{x:02x}, {y:02x}, {z:02x}]<br>"
                f"Count: {count}<br>"
                f"Brightness: {mapped_value}/255<br>"
                f"Opacity: {opacity:.2f}"
            )

    # Create 3D scatter plot
    fig = go.Figure(data=[go.Scatter3d(
        x=x_coords,
        y=y_coords,
        z=z_coords,
        mode='markers',
        marker=dict(
            size=3,
            color=values,
            colorscale='Viridis',
            showscale=True,
            colorbar=dict(title="Frequency<br>(mapped)"),
            opacity=opacities
        ),
        text=hover_text,
        hoverinfo='text'
    )])

    fig.update_layout(
        title=f"3D Byte Triplet Visualization ({scale} scale)",
        scene=dict(
            xaxis_title="Byte 1 (0x00-0xFF)",
            yaxis_title="Byte 2 (0x00-0xFF)",
            zaxis_title="Byte 3 (0x00-0xFF)",
            xaxis=dict(range=[0, 255]),
            yaxis=dict(range=[0, 255]),
            zaxis=dict(range=[0, 255])
        ),
        width=1200,
        height=900
    )

    output_dir = output.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # Change extension to .html
    html_path = output.with_suffix('.html')
    fig.write_html(str(html_path))

    print(f"Wrote interactive 3D visualization to {html_path}")
    print(f"Total unique triplets: {len(x_coords):,}")


def main() -> None:
    args = parse_args()

    if args.mode == "2d":
        counts = scan_pairs(args.input)
        peak = max_count(counts)
        write_ppm(counts, peak, args.output, args.scale)
    else:  # 3d mode
        counts_3d = scan_triplets(args.input)
        peak = max_count_3d(counts_3d)
        write_plotly_3d(counts_3d, peak, args.output, args.scale)


if __name__ == "__main__":
    main()
