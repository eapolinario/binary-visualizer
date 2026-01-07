#!/usr/bin/env python3
"""Benchmark different approaches to reading triplets from binary files."""

import mmap
import time
from collections import defaultdict
from pathlib import Path
import tempfile


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


def scan_triplets_mmap_chunked(path: Path, chunk_size: int = 1024 * 1024) -> dict:
    """Hybrid: memory-mapped but read into bytes chunks."""
    counts = defaultdict(int)
    file_size = path.stat().st_size
    if file_size < 3:
        return counts

    with path.open("rb") as handle:
        with mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            mm_len = len(mm)
            offset = 0
            prev1 = None
            prev2 = None

            while offset < mm_len:
                # Read a chunk from mmap into bytes
                end = min(offset + chunk_size, mm_len)
                chunk = mm[offset:end]

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

                offset = end
    return counts


def generate_test_file(size: int) -> Path:
    """Generate a test file with random-ish data."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.bin')
    path = Path(tmp.name)

    # Generate semi-random but reproducible data
    with path.open("wb") as f:
        # Use a simple pattern that creates variety
        data = bytes((i * 137 + i // 256) % 256 for i in range(size))
        f.write(data)

    return path


def benchmark(func, path: Path, name: str, runs: int = 3):
    """Benchmark a function multiple times and return average time."""
    times = []
    result = None
    for _ in range(runs):
        start = time.perf_counter()
        result = func(path)
        elapsed = time.perf_counter() - start
        times.append(elapsed)

    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)

    return avg_time, min_time, max_time, result


def main():
    # Test with different file sizes
    sizes = [
        (10_000, "10 KB"),
        (100_000, "100 KB"),
        (1_000_000, "1 MB"),
        (10_000_000, "10 MB"),
    ]

    print("=" * 80)
    print("TRIPLET READING PERFORMANCE BENCHMARK")
    print("=" * 80)
    print()

    for size, label in sizes:
        print(f"\nTest file size: {label} ({size:,} bytes)")
        print("-" * 80)

        # Generate test file
        test_file = generate_test_file(size)

        try:
            # Benchmark mmap indexed (current implementation)
            avg1, min1, max1, result1 = benchmark(
                scan_triplets_mmap_indexed, test_file, "mmap indexed"
            )

            # Benchmark chunked (proposed implementation)
            avg2, min2, max2, result2 = benchmark(
                scan_triplets_chunked, test_file, "chunked"
            )

            # Benchmark mmap chunked (hybrid)
            avg3, min3, max3, result3 = benchmark(
                scan_triplets_mmap_chunked, test_file, "mmap chunked"
            )

            # Verify all methods produce the same results
            assert len(result1) == len(result2) == len(result3), "Result mismatch!"
            assert result1 == result2 == result3, "Count mismatch!"

            print(f"{'Method':<20} {'Avg Time':>12} {'Min Time':>12} {'Max Time':>12} {'Speedup':>10}")
            print("-" * 80)
            print(f"{'mmap indexed':<20} {avg1:>10.4f}s {min1:>10.4f}s {max1:>10.4f}s {'1.00x':>10}")
            print(f"{'chunked':<20} {avg2:>10.4f}s {min2:>10.4f}s {max2:>10.4f}s {avg1/avg2:>10.2f}x")
            print(f"{'mmap chunked':<20} {avg3:>10.4f}s {min3:>10.4f}s {max3:>10.4f}s {avg1/avg3:>10.2f}x")
            print()
            print(f"Unique triplets found: {len(result1):,}")

        finally:
            # Clean up test file
            test_file.unlink()

    print()
    print("=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print("Speedup shows how many times faster each method is compared to mmap indexed.")
    print()


if __name__ == "__main__":
    main()
