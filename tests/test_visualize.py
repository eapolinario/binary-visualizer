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
