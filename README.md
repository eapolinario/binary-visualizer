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
# or directly:
uv run visualize.py --scale log -o output.ppm /path/to/binary
```

Tone-mapping options:

- `log` (default): boosts rare pairs.
- `sqrt`: softer contrast.
- `linear`: raw counts.

## 3D Visualization

Generate a 3D volume by scanning byte **triplets** instead of pairs:

```bash
make run INPUT=/path/to/binary OUTPUT=output_3d.ppm SCALE=log MODE=3d
# or directly:
uv run visualize.py --mode 3d --scale log -o output_3d.ppm /path/to/binary
```

This creates a 256×256×256 volume where each voxel `(x, y, z)` represents how often the 3-byte sequence `[x, y, z]` appears. The output is 256 PPM slice images (`output_3d_slice_000.ppm` through `output_3d_slice_255.ppm`), where each slice fixes the first byte and shows a 2D heatmap of the following two bytes.

**Example:**
```bash
# Visualize /bin/ls in 3D
mkdir -p examples/3d_slices
uv run visualize.py --mode 3d --scale log -o examples/3d_slices/ls.ppm /bin/ls
# This creates examples/3d_slices/ls_slice_000.ppm through ls_slice_255.ppm
```

**Viewing the slices:**
- **Individual slices**: Open PPM files with any image viewer (ImageMagick, GIMP, etc.)
- **As video**: Animate through slices using ffmpeg:
  ```bash
  ffmpeg -framerate 10 -pattern_type glob -i 'examples/3d_slices/ls_slice_*.ppm' \
         -c:v libx264 -pix_fmt yuv420p examples/ls_3d.mp4
  ```
- **Convert to PNG**: Use ImageMagick for smaller files:
  ```bash
  mogrify -format png examples/3d_slices/*.ppm
  ```

**Interpreting the output:**
- **Slice 0x00**: All triplets starting with byte `0x00`
- **Slice 0x7F**: All triplets starting with byte `0x7F` (often ASCII text)
- **Bright regions**: Frequently occurring 3-byte sequences (e.g., common instructions, file headers)
- **Sparse slices**: Rare first bytes in the file

**Use cases:**
- Detect longer instruction sequences in executables (x86 opcodes are often 2-3 bytes)
- Visualize file format structures across 3-byte patterns
- Analyze compression or encryption artifacts over triplets
- Compare code patterns between different binaries

## Batch processing and videos

You can turn a directory of binaries into a video of PPM frames, each frame labeled with the source filename:

```bash
make bin-video BIN_DIR=/path/to/bin_dir PPM_DIR=/tmp/ppm_frames PPM_VIDEO_OUTPUT=/tmp/output.mp4 SCALE=log BIN_JOBS=4
```

`BIN_JOBS` controls parallelism when generating frames. The video uses `PPM_FRAMERATE` (default 4 fps) and adds a subtitle track to show the filename for each frame.

## Examples

### x86_64 ELF binaries

https://github.com/user-attachments/assets/d9f3bcf7-4a61-4b2e-9d95-f34b4c4f4bb9

### A few LLM models in the gguf format

https://github.com/user-attachments/assets/2eb7c8d5-8d54-427a-ac48-979f8ae46f1d

### Images in different formats

TODO

### Audio in different formats

TODO

