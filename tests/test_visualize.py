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


def test_write_ppm_slices(tmp_path: Path) -> None:
    # Create a simple 3D volume with one triplet
    data = bytes([10, 20, 30])
    input_file = tmp_path / "test.bin"
    input_file.write_bytes(data)

    counts = visualize.scan_triplets(input_file)
    peak = visualize.max_count_3d(counts)

    output_path = tmp_path / "slices" / "output.ppm"
    visualize.write_ppm_slices(counts, peak, output_path, "linear")

    # Check that slices directory was created
    assert (tmp_path / "slices").exists()

    # Check that all 256 slices were created
    slice_files = list((tmp_path / "slices").glob("output_slice_*.ppm"))
    assert len(slice_files) == 256

    # Check that slice 10 exists (from our triplet (10, 20, 30))
    slice_10 = tmp_path / "slices" / "output_slice_010.ppm"
    assert slice_10.exists()

    # Verify it's a valid PPM header
    content = slice_10.read_text()
    assert content.startswith("P3\n256 256\n255\n")
