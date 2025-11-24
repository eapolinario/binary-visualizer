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

