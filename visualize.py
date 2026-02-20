"""Binary byte-pair visualizer.

This module scans a binary file with a sliding two-byte window, interprets each
pair as coordinates on a 256x256 plane, and emits a grayscale PPM heatmap where
more frequent pairs appear brighter. Counts are stored in a dictionary keyed by
``(x, y)`` pairs for direct lookups.
"""
# /// script
# dependencies = [
#   "plotly",
#   "tqdm",
# ]
# ///

from __future__ import annotations

import argparse
import math
import mmap
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Tuple

from tqdm import tqdm

try:
    import plotly.graph_objects as go
    import plotly.colors
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


GridCounts = DefaultDict[Tuple[int, int], int]
Grid3DCounts = DefaultDict[Tuple[int, int, int], int]
BytePositions = DefaultDict[int, list]


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
        choices=("2d", "3d", "minimap"),
        default="2d",
        help=(
            "Visualization mode. '2d' (default) scans byte pairs for a single "
            "256x256 PPM heatmap. '3d' scans byte triplets and outputs an "
            "interactive HTML file with a 3D Plotly visualization. 'minimap' "
            "shows byte value frequency as a 256-row strip; click a row to "
            "see where that byte value appears in the file."
        ),
    )
    return parser.parse_args()


def scan_pairs(path: Path) -> GridCounts:
    """Return a grid of pair frequencies keyed by ``(x, y)`` tuples.

    Uses memory mapping for efficient sequential access without loading the
    entire file into memory at once.
    """

    counts: GridCounts = defaultdict(int)

    # Get file size using stat
    file_size = path.stat().st_size
    if file_size == 0:
        return counts

    with path.open("rb") as handle:
        # Memory map the file
        with mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            # Scan all consecutive byte pairs
            for i in tqdm(range(len(mm) - 1), desc="Scanning byte pairs", unit="pairs"):
                counts[(mm[i], mm[i + 1])] += 1

    return counts


def scan_triplets(path: Path) -> Grid3DCounts:
    """Return a 3D grid of triplet frequencies keyed by ``(x, y, z)`` tuples.

    Uses memory mapping for efficient sequential access without loading the
    entire file into memory at once.
    """

    counts: Grid3DCounts = defaultdict(int)

    # Get file size using stat
    file_size = path.stat().st_size
    if file_size < 3:
        return counts

    with path.open("rb") as handle:
        # Memory map the file
        with mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            # Scan all consecutive byte triplets
            for i in tqdm(range(len(mm) - 2), desc="Scanning byte triplets", unit="triplets"):
                counts[(mm[i], mm[i + 1], mm[i + 2])] += 1

    return counts


def scan_byte_positions(path: Path) -> tuple[BytePositions, int]:
    """Return a mapping of byte value to file offsets, plus total file size.

    For each byte value (0-255), records every offset in the file where that
    value appears. Uses memory mapping for efficient sequential access.
    """

    positions: BytePositions = defaultdict(list)

    file_size = path.stat().st_size
    if file_size == 0:
        return positions, 0

    with path.open("rb") as handle:
        with mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            with memoryview(mm) as mv:
                for i, b in enumerate(tqdm(mv, desc="Scanning byte positions", unit="bytes")):
                    positions[b].append(i)

    return positions, file_size


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
        for y in tqdm(range(256), desc="Writing PPM", unit="rows"):
            row_values = []
            for x in range(256):
                count = counts.get((x, y), 0)
                value = brightness(count, peak, scale)
                row_values.append(f"{value} {value} {value}")
            handle.write(" ".join(row_values) + "\n")


def write_plotly_3d(
    counts: Grid3DCounts, peak: int, output: Path, scale: str, max_points: int = 100000
) -> None:
    """Write an interactive 3D Plotly visualization as HTML.

    Creates a 3D scatter plot where each point represents a byte triplet.
    Point size and color represent frequency (applying the selected tone mapping).
    Only non-zero triplets are displayed to keep the visualization manageable.

    If there are more than max_points triplets, intelligently sample them,
    prioritizing high-frequency triplets for better performance and visual quality.
    """

    if not PLOTLY_AVAILABLE:
        raise ImportError(
            "Plotly is required for 3D visualization. "
            "Run this script with 'uv run' to automatically install dependencies."
        )

    # Extract non-zero triplets
    triplets = [(coords, count) for coords, count in counts.items() if count > 0]
    total_triplets = len(triplets)

    # Sample if needed to keep browser performance reasonable
    if total_triplets > max_points:
        print(f"Sampling {max_points:,} of {total_triplets:,} triplets for performance")
        # Sort by frequency (descending) to keep most significant patterns
        print("Sorting triplets by frequency...")
        triplets.sort(key=lambda item: item[1], reverse=True)
        triplets = triplets[:max_points]

    x_coords = []
    y_coords = []
    z_coords = []
    rgba_colors = []
    values = []  # Keep values for colorbar reference
    hover_text = []

    # Get the viridis colorscale
    viridis = plotly.colors.sequential.Viridis

    for (x, y, z), count in tqdm(triplets, desc="Processing triplets", unit="triplets"):
        x_coords.append(x)
        y_coords.append(y)
        z_coords.append(z)
        # Apply tone mapping to the count
        mapped_value = brightness(count, peak, scale)
        values.append(mapped_value)
        # Calculate opacity based on frequency (0.2 to 1.0 range)
        # More common points are more opaque
        opacity = 0.2 + (mapped_value / 255) * 0.8

        # Map the value to a viridis color and add alpha channel
        # Normalize mapped_value to 0-1 range for colorscale lookup
        norm_value = mapped_value / 255
        # Get color from viridis scale
        color_idx = int(norm_value * (len(viridis) - 1))
        rgb_str = viridis[color_idx]
        # Convert hex to RGB
        rgb = plotly.colors.hex_to_rgb(rgb_str)
        # Create RGBA string with variable alpha
        rgba = f'rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {opacity})'
        rgba_colors.append(rgba)

        hover_text.append(
            f"Triplet: [{x:02x}, {y:02x}, {z:02x}]<br>"
            f"Count: {count}<br>"
            f"Brightness: {mapped_value}/255<br>"
            f"Opacity: {opacity:.2f}"
        )

    # Create 3D scatter plot with RGBA colors for variable transparency
    main_trace = go.Scatter3d(
        x=x_coords,
        y=y_coords,
        z=z_coords,
        mode='markers',
        marker=dict(
            size=3,
            color=rgba_colors
        ),
        text=hover_text,
        hoverinfo='text',
        name='Triplets'
    )

    # Add invisible trace for colorbar legend
    # This shows the frequency scale without the transparency
    colorbar_trace = go.Scatter3d(
        x=[None],  # No actual points
        y=[None],
        z=[None],
        mode='markers',
        marker=dict(
            size=3,
            color=[0, 255],  # Min and max values
            colorscale='Viridis',
            showscale=True,
            colorbar=dict(
                title="Frequency<br>(mapped)",
                tickvals=[0, 64, 128, 192, 255],
                ticktext=['Low', '', 'Medium', '', 'High']
            ),
            cmin=0,
            cmax=255
        ),
        showlegend=False,
        hoverinfo='skip'
    )

    fig = go.Figure(data=[main_trace, colorbar_trace])

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


def write_minimap_html(
    positions: BytePositions, file_size: int, output: Path, scale: str
) -> None:
    """Write an interactive byte-value minimap as a self-contained HTML file.

    The minimap is a 256-row strip where each row represents a byte value
    (0x00-0xFF). Row brightness reflects how frequently that byte appears.
    Clicking a row reveals a location bar showing where that byte value
    occurs throughout the file.
    """

    # Compute frequency for each byte value
    freq = [len(positions.get(b, [])) for b in range(256)]
    peak_freq = max(freq) if freq else 0

    # Bin positions into buckets for the location bar.  Using 1024 bins
    # keeps the display fast even for large files while still giving good
    # resolution.
    num_bins = 1024

    # Pre-compute binned data for every byte value so the JS side only
    # needs a compact lookup table.
    import json

    bin_data: dict[int, list[int]] = {}
    for byte_val in range(256):
        if not positions.get(byte_val):
            continue
        bins = [0] * num_bins
        for offset in positions[byte_val]:
            idx = offset * num_bins // file_size if file_size else 0
            idx = min(idx, num_bins - 1)
            bins[idx] += 1
        bin_data[byte_val] = bins

    # Brightness values for each byte (used by the minimap strip)
    bright = [brightness(f, peak_freq, scale) for f in freq]

    html_path = output.with_suffix(".html")
    html_path.parent.mkdir(parents=True, exist_ok=True)

    with html_path.open("w", encoding="utf-8") as f:
        f.write(f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Binary Minimap</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #1e1e1e; color: #ccc; font-family: monospace;
         display: flex; flex-direction: column; align-items: center;
         padding: 20px; }}
  h1 {{ margin-bottom: 8px; font-size: 18px; }}
  .subtitle {{ margin-bottom: 16px; font-size: 12px; color: #888; }}
  .container {{ display: flex; gap: 24px; align-items: flex-start; }}
  .minimap-wrap {{ display: flex; flex-direction: column; align-items: center; }}
  .minimap-label {{ font-size: 11px; color: #888; margin-bottom: 4px; }}
  canvas#minimap {{ cursor: pointer; border: 1px solid #444;
                    image-rendering: pixelated; }}
  .detail {{ width: 600px; }}
  .detail h2 {{ font-size: 14px; margin-bottom: 8px; }}
  .info {{ font-size: 12px; margin-bottom: 8px; color: #aaa; }}
  canvas#locbar {{ border: 1px solid #444; width: 100%; height: 48px; }}
  .legend {{ display: flex; justify-content: space-between; font-size: 10px;
             color: #666; margin-top: 2px; }}
  .hint {{ margin-top: 24px; font-size: 11px; color: #666; }}
</style>
</head>
<body>
<h1>Binary Minimap &mdash; {scale} scale</h1>
<p class="subtitle">File size: {file_size:,} bytes</p>
<div class="container">
  <div class="minimap-wrap">
    <span class="minimap-label">Byte value (0x00 &ndash; 0xFF)</span>
    <canvas id="minimap" width="48" height="256"></canvas>
  </div>
  <div class="detail">
    <h2 id="heading">Click a row in the minimap&hellip;</h2>
    <p class="info" id="info">&nbsp;</p>
    <canvas id="locbar" width="1024" height="48"></canvas>
    <div class="legend"><span>Offset 0</span><span>{file_size:,}</span></div>
  </div>
</div>
<p class="hint">Each minimap row = one byte value. Brightness = frequency ({scale}).
Click to see where that byte appears in the file.</p>
<script>
const freq = {json.dumps(freq)};
const bright = {json.dumps(bright)};
const binData = {json.dumps(bin_data)};
const numBins = {num_bins};
const fileSize = {file_size};

// --- Draw minimap strip ---
const mc = document.getElementById("minimap");
const mctx = mc.getContext("2d");
for (let b = 0; b < 256; b++) {{
  const v = bright[b];
  mctx.fillStyle = `rgb(${{v}},${{v}},${{v}})`;
  mctx.fillRect(0, b, 48, 1);
}}

// --- Location bar ---
const lc = document.getElementById("locbar");
const lctx = lc.getContext("2d");

function showByte(byteVal) {{
  document.getElementById("heading").textContent =
    "Byte 0x" + byteVal.toString(16).toUpperCase().padStart(2, "0") +
    " (" + byteVal + ")";
  document.getElementById("info").textContent =
    "Frequency: " + freq[byteVal].toLocaleString() + " occurrences";

  lctx.fillStyle = "#111";
  lctx.fillRect(0, 0, lc.width, lc.height);

  const bins = binData[byteVal.toString()];
  if (!bins) return;

  const maxBin = Math.max(...bins);
  if (maxBin === 0) return;

  for (let i = 0; i < numBins; i++) {{
    if (bins[i] === 0) continue;
    const ratio = bins[i] / maxBin;
    const h = Math.max(1, Math.round(ratio * lc.height));
    const g = Math.round(50 + ratio * 205);
    lctx.fillStyle = `rgb(0,${{g}},0)`;
    lctx.fillRect(i, lc.height - h, 1, h);
  }}
}}

mc.addEventListener("click", function(e) {{
  const rect = mc.getBoundingClientRect();
  const y = Math.floor((e.clientY - rect.top) / rect.height * 256);
  if (y >= 0 && y < 256) showByte(y);
}});
</script>
</body>
</html>
""")

    print(f"Wrote interactive minimap to {html_path}")


def main() -> None:
    args = parse_args()

    if args.mode == "2d":
        counts = scan_pairs(args.input)
        peak = max_count(counts)
        write_ppm(counts, peak, args.output, args.scale)
    elif args.mode == "3d":
        counts_3d = scan_triplets(args.input)
        peak = max_count_3d(counts_3d)
        write_plotly_3d(counts_3d, peak, args.output, args.scale)
    else:  # minimap mode
        positions, file_size = scan_byte_positions(args.input)
        write_minimap_html(positions, file_size, args.output, args.scale)


if __name__ == "__main__":
    main()
