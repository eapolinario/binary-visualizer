# Binary Visualizer

Implementation of the byte-pair heatmap idea from [Binary Visualizer by binji](https://www.youtube.com/watch?v=4bM3Gut1hIk). 

Point it at a binary, it renders a 256x256 grayscale PPM where each pixel represents how often a byte is followed by another. 

- Input: any binary file.
- Output: ASCII PPM heatmap with optional tone mapping (`log`, `sqrt`, or `linear`).
- Extras: Make targets to batch process directories and stitch frames into labeled videos.

## Quickstart

Requirements: Python 3.11+, [uv](https://github.com/astral-sh/uv) for running scripts, and `ffmpeg` if you want to build videos.

Generate a single heatmap:

```bash
make run INPUT=/path/to/binary OUTPUT=output.ppm SCALE=log
```

Tone-mapping options:

- `log` (default): boosts rare pairs.
- `sqrt`: softer contrast.
- `linear`: raw counts.

## 3D Visualization

Generate an **interactive 3D visualization** by scanning byte **triplets** instead of pairs:

```bash
make run INPUT=/path/to/binary OUTPUT=output_3d.html SCALE=log MODE=3d
```

This creates an interactive HTML file with a 3D scatter plot where each point represents a byte triplet `[x, y, z]`. The visualization shows only triplets that actually occur in the file, making it easy to spot patterns.

**Example:**
```bash
# Visualize /bin/ls in 3D
make run INPUT=/bin/ls OUTPUT=ls_3d.html SCALE=log MODE=3d
# Open ls_3d.html in your browser
```

**Note:** 3D mode requires Plotly. Install with `uv pip install plotly` if needed.

**Features:**
- **Interactive rotation**: Click and drag to rotate the 3D space
- **Zoom**: Scroll to zoom in/out
- **Hover details**: Hover over points to see:
  - Exact byte triplet (in hex)
  - Occurrence count
  - Mapped brightness value
- **Color coding**: Viridis colorscale from dark (rare) to bright (frequent)
- **Sparse representation**: Only non-zero triplets are shown

**Interpreting the output:**
- **Clusters**: Dense regions indicate frequently co-occurring byte sequences
- **Color**: Brighter yellow/green = more frequent triplets
- **Distribution**: Spread shows variety of 3-byte patterns in the file
- **Axis positions**:
  - X-axis: First byte of triplet
  - Y-axis: Second byte
  - Z-axis: Third byte

**Use cases:**
- **Executable analysis**: Detect x86 instruction sequences (opcodes often 2-3 bytes)
- **Format fingerprinting**: Identify file format structures by triplet clusters
- **Compression detection**: Encrypted/compressed files show uniform distribution
- **Pattern comparison**: Overlay multiple files to compare code patterns
- **Malware analysis**: Identify unusual byte sequence patterns

## Batch processing and videos

Generate PPM frames for every file in a directory:

```bash
make bin-ppm BIN_DIR=/path/to/bin_dir PPM_DIR=/tmp/ppm_frames SCALE=log BIN_JOBS=4
```

