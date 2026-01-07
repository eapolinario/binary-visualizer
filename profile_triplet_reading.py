#!/usr/bin/env python3
"""Profile triplet reading to find the actual bottleneck."""

import cProfile
import pstats
import io
import mmap
from collections import defaultdict
from pathlib import Path
import tempfile
import random


def scan_triplets_mmap_indexed(path: Path) -> dict:
    """Current implementation: memory-mapped with individual indexing."""
    counts = defaultdict(int)
    file_size = path.stat().st_size
    if file_size < 3:
        return counts

    with path.open("rb") as handle:
        with mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            for i in range(len(mm) - 2):
                counts[(mm[i], mm[i + 1], mm[i + 2])] += 1
    return counts


def scan_triplets_chunked(path: Path, chunk_size: int = 1024 * 1024) -> dict:
    """Proposed implementation: chunk-based reading."""
    counts = defaultdict(int)
    with path.open("rb") as handle:
        prev1 = None
        prev2 = None
        while True:
            chunk = handle.read(chunk_size)
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


def generate_test_file(size: int) -> Path:
    """Generate a test file with semi-random data."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.bin')
    path = Path(tmp.name)

    with path.open("wb") as f:
        chunk_size = 1024 * 1024
        remaining = size
        while remaining > 0:
            write_size = min(chunk_size, remaining)
            data = bytes(random.randint(0, 255) for _ in range(write_size))
            f.write(data)
            remaining -= write_size

    return path


def profile_function(func, *args):
    """Profile a function and return statistics."""
    pr = cProfile.Profile()
    pr.enable()
    result = func(*args)
    pr.disable()

    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s)
    ps.strip_dirs()
    ps.sort_stats('cumulative')
    ps.print_stats(20)  # Top 20 functions

    return result, s.getvalue()


def main():
    print("Generating 10 MB test file...")
    test_file = generate_test_file(10_000_000)

    try:
        print("\n" + "=" * 80)
        print("PROFILING: mmap indexed")
        print("=" * 80)
        result1, profile1 = profile_function(scan_triplets_mmap_indexed, test_file)
        print(profile1)

        print("\n" + "=" * 80)
        print("PROFILING: chunked")
        print("=" * 80)
        result2, profile2 = profile_function(scan_triplets_chunked, test_file)
        print(profile2)

        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Unique triplets (mmap): {len(result1):,}")
        print(f"Unique triplets (chunked): {len(result2):,}")

    finally:
        test_file.unlink()


if __name__ == "__main__":
    main()
