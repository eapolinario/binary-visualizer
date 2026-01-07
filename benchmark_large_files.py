#!/usr/bin/env python3
"""Benchmark with larger, more realistic files."""

import mmap
import time
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


def generate_random_file(size: int) -> Path:
    """Generate a file with truly random bytes."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.bin')
    path = Path(tmp.name)

    with path.open("wb") as f:
        # Generate in chunks to avoid memory issues
        chunk_size = 1024 * 1024
        remaining = size
        while remaining > 0:
            write_size = min(chunk_size, remaining)
            data = bytes(random.randint(0, 255) for _ in range(write_size))
            f.write(data)
            remaining -= write_size

    return path


def main():
    # Test with larger files
    sizes = [
        (50_000_000, "50 MB"),
        (100_000_000, "100 MB"),
    ]

    print("=" * 80)
    print("LARGE FILE TRIPLET READING BENCHMARK")
    print("=" * 80)
    print()

    for size, label in sizes:
        print(f"\nGenerating random test file: {label} ({size:,} bytes)...")
        test_file = generate_random_file(size)

        try:
            print("Running benchmarks (single run due to size)...")
            print("-" * 80)

            # Benchmark mmap indexed
            print("Testing mmap indexed...", flush=True)
            start = time.perf_counter()
            result1 = scan_triplets_mmap_indexed(test_file)
            time1 = time.perf_counter() - start

            # Benchmark chunked
            print("Testing chunked...", flush=True)
            start = time.perf_counter()
            result2 = scan_triplets_chunked(test_file)
            time2 = time.perf_counter() - start

            print()
            print(f"{'Method':<20} {'Time':>12} {'Speedup':>10}")
            print("-" * 80)
            print(f"{'mmap indexed':<20} {time1:>10.2f}s {'1.00x':>10}")
            print(f"{'chunked':<20} {time2:>10.2f}s {time1/time2:>10.2f}x")
            print()
            print(f"Unique triplets (mmap): {len(result1):,}")
            print(f"Unique triplets (chunked): {len(result2):,}")
            print(f"Time saved: {time1 - time2:.2f}s ({(time1-time2)/time1*100:.1f}%)")

        finally:
            # Clean up test file
            print(f"\nCleaning up {test_file}")
            test_file.unlink()

    print()


if __name__ == "__main__":
    main()
