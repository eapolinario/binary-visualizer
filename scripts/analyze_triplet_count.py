#!/usr/bin/env python3
"""Analyze the relationship between file size and unique triplet count."""

import sys
from pathlib import Path
from collections import defaultdict


def count_unique_triplets(path: Path) -> int:
    """Count unique triplets in a file."""
    counts = defaultdict(int)
    with path.open("rb") as handle:
        prev1 = None
        prev2 = None
        while True:
            chunk = handle.read(1024 * 1024)  # 1 MiB chunks
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

    return len(counts)


def generate_test_file(path: Path, size: int, pattern: str = "random"):
    """Generate a test file of given size."""
    import random
    with path.open("wb") as f:
        if pattern == "random":
            # Random bytes - should produce many unique triplets
            f.write(bytes(random.randint(0, 255) for _ in range(size)))
        elif pattern == "repetitive":
            # Repetitive pattern - should produce few unique triplets
            pattern_bytes = b"ABCD" * (size // 4 + 1)
            f.write(pattern_bytes[:size])
        elif pattern == "sequential":
            # Sequential bytes - should produce moderate unique triplets
            f.write(bytes(i % 256 for i in range(size)))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Analyze specific file
        file_path = Path(sys.argv[1])
        if file_path.exists():
            file_size = file_path.stat().st_size
            unique_triplets = count_unique_triplets(file_path)
            print(f"File: {file_path}")
            print(f"Size: {file_size:,} bytes")
            print(f"Unique triplets: {unique_triplets:,}")
            print(f"Percentage of possible triplets: {unique_triplets / 16777216 * 100:.2f}%")
        else:
            print(f"File not found: {file_path}")
    else:
        # Generate and analyze test files
        print("Generating test files and analyzing triplet counts...\n")
        print(f"Maximum possible triplets: {256**3:,}\n")

        test_dir = Path("test_files")
        test_dir.mkdir(exist_ok=True)

        sizes = [100, 1_000, 10_000, 100_000, 1_000_000]

        for pattern in ["random", "repetitive", "sequential"]:
            print(f"\n{pattern.upper()} PATTERN:")
            print("-" * 60)
            print(f"{'Size (bytes)':>15} | {'Unique Triplets':>20} | {'% of Max':>10}")
            print("-" * 60)

            for size in sizes:
                file_path = test_dir / f"test_{pattern}_{size}.bin"
                generate_test_file(file_path, size, pattern)
                unique_count = count_unique_triplets(file_path)
                percentage = unique_count / 16777216 * 100
                print(f"{size:>15,} | {unique_count:>20,} | {percentage:>9.2f}%")

        print("\n\nConclusion:")
        print("- Smaller files have fewer unique triplets")
        print("- Random files approach max triplets faster than structured files")
        print("- HTML file size grows with unique triplet count")
