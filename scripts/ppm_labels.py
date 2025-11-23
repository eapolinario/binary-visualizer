#!/usr/bin/env python3
"""Generate a Advanced Substation Alpha (.ssa) subtitle track for per-frame labels."""

from __future__ import annotations

import argparse
import textwrap
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write an SSA subtitle track that labels each frame with the source PPM filename."
    )
    parser.add_argument("--ppm-dir", required=True, type=Path, help="Directory containing PPM frames")
    parser.add_argument(
        "--framerate",
        required=True,
        type=float,
        help="Video framerate that determines frame durations",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Destination .ssa file path",
    )
    parser.add_argument(
        "--pad",
        type=int,
        default=60,
        help="Vertical padding added to the final video (default: 60)",
    )
    return parser.parse_args()


def ppm_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        magic = handle.readline().strip()
        if magic not in {b"P3", b"P6"}:
            raise SystemExit(f"Unsupported PPM magic {magic!r} in {path}")
        tokens: list[bytes] = []
        while len(tokens) < 3:
            chunk = handle.readline()
            if not chunk:
                break
            chunk = chunk.split(b"#", 1)[0]
            tokens.extend(part for part in chunk.split() if part)
        if len(tokens) < 3:
            raise SystemExit(f"Unable to determine dimensions for {path}")
    width, height, _ = map(int, tokens[:3])
    return width, height


def format_time(seconds: float) -> str:
    total = max(0.0, seconds)
    hours = int(total // 3600)
    total -= hours * 3600
    minutes = int(total // 60)
    total -= minutes * 60
    return f"{hours}:{minutes:02d}:{total:05.2f}"


def ssa_escape(text: str) -> str:
    return (
        text.replace("\\", r"\\")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace(",", r"\,")
        .replace("\n", r"\N")
    )


def main() -> None:
    args = parse_args()
    ppm_files = sorted(args.ppm_dir.glob("*.ppm"))
    if not ppm_files:
        raise SystemExit(f"No .ppm files found in {args.ppm_dir}")

    width, height = ppm_dimensions(ppm_files[0])
    play_res_y = height + args.pad

    header = textwrap.dedent(
        f"""\
        [Script Info]
        ScriptType: v4.00+
        PlayResX: {width}
        PlayResY: {play_res_y}
        ScaledBorderAndShadow: yes

        [V4+ Styles]
        Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
        Style: Label,DejaVu Sans,12,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,3,0,0,2,10,10,20,1

        [Events]
        Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
        """
    )

    frame_duration = 1.0 / args.framerate
    with args.output.open("w", encoding="utf-8") as handle:
        handle.write(header)
        for index, ppm_path in enumerate(ppm_files):
            start = format_time(index * frame_duration)
            end = format_time((index + 1) * frame_duration)
            label = ssa_escape(ppm_path.name)
            handle.write(f"Dialogue: 0,{start},{end},Label,,0,0,20,,{label}\n")


if __name__ == "__main__":
    main()
