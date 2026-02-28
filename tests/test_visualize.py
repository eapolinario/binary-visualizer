# /// script
# dependencies = [
#   "plotly",
#   "pytest",
#   "tqdm",
# ]
# ///

from pathlib import Path

import visualize


def test_counts_expected_pairs(tmp_path: Path) -> None:
    data = bytes([0, 1, 2, 3, 2])
    target = tmp_path / "sample.bin"
    target.write_bytes(data)

    counts = visualize.scan_pairs(target)
    expected = {
        (0, 1): 1,
        (1, 2): 1,
        (2, 3): 1,
        (3, 2): 1,
    }

    assert dict(counts) == expected
    assert visualize.max_count(counts) == 1


def test_counts_expected_triplets(tmp_path: Path) -> None:
    data = bytes([0, 1, 2, 3, 2, 1])
    target = tmp_path / "sample.bin"
    target.write_bytes(data)

    counts = visualize.scan_triplets(target)
    expected = {
        (0, 1, 2): 1,
        (1, 2, 3): 1,
        (2, 3, 2): 1,
        (3, 2, 1): 1,
    }

    assert dict(counts) == expected
    assert visualize.max_count_3d(counts) == 1


def test_triplets_chunk_boundary(tmp_path: Path) -> None:
    # Test that triplets are correctly tracked across chunk boundaries
    # We can't easily test 1GB chunks, but the logic should handle small boundaries
    data = bytes([5, 6, 7, 8])
    target = tmp_path / "sample.bin"
    target.write_bytes(data)

    counts = visualize.scan_triplets(target)
    expected = {
        (5, 6, 7): 1,
        (6, 7, 8): 1,
    }

    assert dict(counts) == expected


def test_write_plotly_3d(tmp_path: Path) -> None:
    # Create a simple 3D volume with a few triplets
    data = bytes([10, 20, 30, 10, 20, 30, 15, 25, 35])
    input_file = tmp_path / "test.bin"
    input_file.write_bytes(data)

    counts = visualize.scan_triplets(input_file)
    peak = visualize.max_count_3d(counts)

    output_path = tmp_path / "output_3d.html"

    # Plotly is now a required dependency, so this should not raise ImportError
    visualize.write_plotly_3d(counts, peak, output_path, "linear")

    # Check that HTML file was created
    assert output_path.exists()

    # Verify it's a valid HTML file with Plotly content
    content = output_path.read_text()
    assert "<html>" in content.lower()
    assert "plotly" in content.lower()
    assert "3D Byte Triplet Visualization" in content


def test_counts_expected_pairs_db(tmp_path: Path) -> None:
    data = bytes([0, 1, 2, 3, 2])
    target = tmp_path / "sample.bin"
    target.write_bytes(data)

    counts = visualize.scan_pairs_db(target)
    expected = {
        (0, 1): 1,
        (1, 2): 1,
        (2, 3): 1,
        (3, 2): 1,
    }

    assert dict(counts) == expected
    assert visualize.max_count(counts) == 1


def test_counts_expected_triplets_db(tmp_path: Path) -> None:
    data = bytes([0, 1, 2, 3, 2, 1])
    target = tmp_path / "sample.bin"
    target.write_bytes(data)

    counts = visualize.scan_triplets_db(target)
    expected = {
        (0, 1, 2): 1,
        (1, 2, 3): 1,
        (2, 3, 2): 1,
        (3, 2, 1): 1,
    }

    assert dict(counts) == expected
    assert visualize.max_count_3d(counts) == 1


def test_triplets_chunk_boundary_db(tmp_path: Path) -> None:
    data = bytes([5, 6, 7, 8])
    target = tmp_path / "sample.bin"
    target.write_bytes(data)

    counts = visualize.scan_triplets_db(target)
    expected = {
        (5, 6, 7): 1,
        (6, 7, 8): 1,
    }

    assert dict(counts) == expected


def test_db_matches_mmap_pairs(tmp_path: Path) -> None:
    """The db engine should produce identical results to the mmap engine."""
    data = bytes(range(256)) + bytes([0, 0, 0, 1, 1, 2])
    target = tmp_path / "sample.bin"
    target.write_bytes(data)

    mmap_counts = dict(visualize.scan_pairs(target))
    db_counts = dict(visualize.scan_pairs_db(target))

    assert mmap_counts == db_counts


def test_db_matches_mmap_triplets(tmp_path: Path) -> None:
    """The db engine should produce identical results to the mmap engine."""
    data = bytes(range(256)) + bytes([0, 0, 0, 1, 1, 2])
    target = tmp_path / "sample.bin"
    target.write_bytes(data)

    mmap_counts = dict(visualize.scan_triplets(target))
    db_counts = dict(visualize.scan_triplets_db(target))

    assert mmap_counts == db_counts


def test_db_empty_file(tmp_path: Path) -> None:
    target = tmp_path / "empty.bin"
    target.write_bytes(b"")

    assert dict(visualize.scan_pairs_db(target)) == {}
    assert dict(visualize.scan_triplets_db(target)) == {}


def test_db_single_byte(tmp_path: Path) -> None:
    target = tmp_path / "one.bin"
    target.write_bytes(b"\x42")

    assert dict(visualize.scan_pairs_db(target)) == {}
    assert dict(visualize.scan_triplets_db(target)) == {}


def test_db_two_bytes(tmp_path: Path) -> None:
    target = tmp_path / "two.bin"
    target.write_bytes(bytes([10, 20]))

    pairs = dict(visualize.scan_pairs_db(target))
    assert pairs == {(10, 20): 1}
    assert dict(visualize.scan_triplets_db(target)) == {}


def test_counts_expected_pairs_duckdb(tmp_path: Path) -> None:
    data = bytes([0, 1, 2, 3, 2])
    target = tmp_path / "sample.bin"
    target.write_bytes(data)

    counts = visualize.scan_pairs_duckdb(target)
    expected = {
        (0, 1): 1,
        (1, 2): 1,
        (2, 3): 1,
        (3, 2): 1,
    }

    assert dict(counts) == expected
    assert visualize.max_count(counts) == 1


def test_counts_expected_triplets_duckdb(tmp_path: Path) -> None:
    data = bytes([0, 1, 2, 3, 2, 1])
    target = tmp_path / "sample.bin"
    target.write_bytes(data)

    counts = visualize.scan_triplets_duckdb(target)
    expected = {
        (0, 1, 2): 1,
        (1, 2, 3): 1,
        (2, 3, 2): 1,
        (3, 2, 1): 1,
    }

    assert dict(counts) == expected
    assert visualize.max_count_3d(counts) == 1


def test_duckdb_matches_mmap_pairs(tmp_path: Path) -> None:
    """The duckdb engine should produce identical results to the mmap engine."""
    data = bytes(range(256)) + bytes([0, 0, 0, 1, 1, 2])
    target = tmp_path / "sample.bin"
    target.write_bytes(data)

    mmap_counts = dict(visualize.scan_pairs(target))
    duckdb_counts = dict(visualize.scan_pairs_duckdb(target))

    assert mmap_counts == duckdb_counts


def test_duckdb_matches_mmap_triplets(tmp_path: Path) -> None:
    """The duckdb engine should produce identical results to the mmap engine."""
    data = bytes(range(256)) + bytes([0, 0, 0, 1, 1, 2])
    target = tmp_path / "sample.bin"
    target.write_bytes(data)

    mmap_counts = dict(visualize.scan_triplets(target))
    duckdb_counts = dict(visualize.scan_triplets_duckdb(target))

    assert mmap_counts == duckdb_counts


def test_duckdb_empty_file(tmp_path: Path) -> None:
    target = tmp_path / "empty.bin"
    target.write_bytes(b"")

    assert dict(visualize.scan_pairs_duckdb(target)) == {}
    assert dict(visualize.scan_triplets_duckdb(target)) == {}


def test_sqlite_persistent_reuse(tmp_path: Path) -> None:
    """Second call with the same db_path should reuse cached data."""
    data = bytes([0, 1, 2, 3])
    target = tmp_path / "sample.bin"
    target.write_bytes(data)
    db = tmp_path / "cache.sqlite"

    first = dict(visualize.scan_pairs_db(target, db_path=db))
    assert db.exists()
    second = dict(visualize.scan_pairs_db(target, db_path=db))
    assert first == second


def test_sqlite_persistent_stale(tmp_path: Path) -> None:
    """Changing the source file should trigger a reload."""
    target = tmp_path / "sample.bin"
    target.write_bytes(bytes([0, 1, 2, 3]))
    db = tmp_path / "cache.sqlite"

    first = dict(visualize.scan_pairs_db(target, db_path=db))

    # Overwrite with different content
    target.write_bytes(bytes([10, 20, 30, 40, 50]))
    second = dict(visualize.scan_pairs_db(target, db_path=db))
    assert first != second
    assert second == {(10, 20): 1, (20, 30): 1, (30, 40): 1, (40, 50): 1}


def test_duckdb_persistent_reuse(tmp_path: Path) -> None:
    """Second call with the same db_path should reuse cached data."""
    data = bytes([0, 1, 2, 3])
    target = tmp_path / "sample.bin"
    target.write_bytes(data)
    db = tmp_path / "cache.duckdb"

    first = dict(visualize.scan_pairs_duckdb(target, db_path=db))
    assert db.exists()
    second = dict(visualize.scan_pairs_duckdb(target, db_path=db))
    assert first == second


def test_duckdb_persistent_stale(tmp_path: Path) -> None:
    """Changing the source file should trigger a reload."""
    target = tmp_path / "sample.bin"
    target.write_bytes(bytes([0, 1, 2, 3]))
    db = tmp_path / "cache.duckdb"

    first = dict(visualize.scan_pairs_duckdb(target, db_path=db))

    # Overwrite with different content
    target.write_bytes(bytes([10, 20, 30, 40, 50]))
    second = dict(visualize.scan_pairs_duckdb(target, db_path=db))
    assert first != second
    assert second == {(10, 20): 1, (20, 30): 1, (30, 40): 1, (40, 50): 1}


def test_3d_mode_integration(tmp_path: Path) -> None:
    """Integration test for full 3D mode execution via main()."""
    import sys
    from unittest.mock import patch

    # Create test binary data
    data = bytes([5, 10, 15, 20, 25, 30, 35, 40])
    input_file = tmp_path / "test_binary.bin"
    input_file.write_bytes(data)

    output_file = tmp_path / "test_3d_output.ppm"

    # Mock sys.argv to simulate command line arguments
    test_args = [
        "visualize.py",
        str(input_file),
        "--mode", "3d",
        "--scale", "linear",
        "-o", str(output_file),
    ]

    with patch.object(sys, "argv", test_args):
        visualize.main()

    # The output should be an HTML file (extension changes from .ppm to .html)
    html_output = output_file.with_suffix(".html")
    assert html_output.exists()

    # Verify the HTML content
    content = html_output.read_text()
    assert "<html>" in content.lower()
    assert "plotly" in content.lower()
    assert "3D Byte Triplet Visualization" in content
    assert "linear scale" in content.lower()
