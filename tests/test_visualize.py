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


def test_scan_byte_positions(tmp_path: Path) -> None:
    data = bytes([0, 1, 2, 0, 1, 0])
    target = tmp_path / "sample.bin"
    target.write_bytes(data)

    positions, file_size = visualize.scan_byte_positions(target)

    assert file_size == 6
    assert sorted(positions[0]) == [0, 3, 5]
    assert sorted(positions[1]) == [1, 4]
    assert positions[2] == [2]
    # Byte value 3 never appears
    assert 3 not in positions


def test_scan_byte_positions_empty(tmp_path: Path) -> None:
    target = tmp_path / "empty.bin"
    target.write_bytes(b"")

    positions, file_size = visualize.scan_byte_positions(target)

    assert file_size == 0
    assert len(positions) == 0


def test_write_minimap_html(tmp_path: Path) -> None:
    data = bytes([10, 20, 30, 10, 20, 10])
    input_file = tmp_path / "test.bin"
    input_file.write_bytes(data)

    positions, file_size = visualize.scan_byte_positions(input_file)
    output_path = tmp_path / "minimap.html"

    visualize.write_minimap_html(positions, file_size, output_path, "log")

    assert output_path.exists()
    content = output_path.read_text()
    assert "Binary Minimap" in content
    assert "log" in content
    assert "minimap" in content.lower()


def test_minimap_mode_integration(tmp_path: Path) -> None:
    """Integration test for full minimap mode execution via main()."""
    import sys
    from unittest.mock import patch

    data = bytes([5, 10, 15, 20, 25, 30, 35, 40])
    input_file = tmp_path / "test_binary.bin"
    input_file.write_bytes(data)

    output_file = tmp_path / "test_minimap_output.ppm"

    test_args = [
        "visualize.py",
        str(input_file),
        "--mode", "minimap",
        "--scale", "sqrt",
        "-o", str(output_file),
    ]

    with patch.object(sys, "argv", test_args):
        visualize.main()

    html_output = output_file.with_suffix(".html")
    assert html_output.exists()

    content = html_output.read_text()
    assert "Binary Minimap" in content
    assert "sqrt" in content
