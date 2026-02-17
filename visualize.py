"""Binary byte-pair visualizer.

This module scans a binary file with a sliding two-byte window, interprets each
pair as coordinates on a 256x256 plane, and emits a grayscale PPM heatmap where
more frequent pairs appear brighter. Counts are stored in a dictionary keyed by
``(x, y)`` pairs for direct lookups.
"""
# /// script
# dependencies = [
#   "plotly",
#   "tqdm",
# ]
# ///

from __future__ import annotations

import argparse
import math
import mmap
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Tuple

from tqdm import tqdm

try:
    import plotly.graph_objects as go
    import plotly.colors
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False


GridCounts = DefaultDict[Tuple[int, int], int]
Grid3DCounts = DefaultDict[Tuple[int, int, int], int]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Scan a binary file with a sliding byte window and render a 256x256 "
            "PPM heatmap where brighter pixels represent more frequent pairs."
        )
    )
    parser.add_argument("input", type=Path, help="Path to the input binary file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("output.ppm"),
        help="Destination path for the generated PPM image (default: output.ppm)",
    )
    parser.add_argument(
        "--scale",
        choices=("linear", "sqrt", "log"),
        default="log",
        help=(
            "Tone-mapping curve for brightness. 'log' (default) highlights rare "
            "pairs, 'sqrt' is softer, and 'linear' matches the raw counts."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=("2d", "3d"),
        default="2d",
        help=(
            "Visualization mode. '2d' (default) scans byte pairs for a single "
            "256x256 PPM heatmap. '3d' scans byte triplets and outputs an "
            "interactive HTML file with a 3D Plotly visualization."
        ),
    )
    parser.add_argument(
        "--engine",
        choices=("mmap", "sqlite", "duckdb"),
        default="mmap",
        help=(
            "Computation engine. 'mmap' (default) scans the file directly "
            "with memory mapping. 'sqlite' loads the file into an in-memory "
            "SQLite database and computes frequencies with SQL window "
            "functions. 'duckdb' does the same with DuckDB's columnar "
            "engine for faster analytical queries."
        ),
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help=(
            "Path to an on-disk database file for the sqlite/duckdb engines. "
            "When set, the byte data is persisted between runs and reloaded "
            "only when the source file changes (checked via size and mtime). "
            "Ignored when --engine is mmap."
        ),
    )
    return parser.parse_args()


def _db_is_fresh(conn: object, path: Path) -> tuple[bool, int]:
    """Check whether the ``_meta`` table records the current state of *path*.

    Returns ``(True, file_size)`` when the cached byte data is still valid,
    or ``(False, 0)`` when a reload is needed.  Works with both SQLite and
    DuckDB connections (duck-typed via ``.execute`` / ``.fetchone``).
    """

    try:
        row = conn.execute(  # type: ignore[union-attr]
            "SELECT source_path, source_size, source_mtime_ns FROM _meta"
        ).fetchone()
    except Exception:
        return False, 0
    if row is None:
        return False, 0
    stat = path.stat()
    if (
        row[0] == str(path.resolve())
        and row[1] == stat.st_size
        and row[2] == int(stat.st_mtime_ns)
    ):
        return True, row[1]
    return False, 0


def scan_pairs(path: Path) -> GridCounts:
    """Return a grid of pair frequencies keyed by ``(x, y)`` tuples.

    Uses memory mapping for efficient sequential access without loading the
    entire file into memory at once.
    """

    counts: GridCounts = defaultdict(int)

    # Get file size using stat
    file_size = path.stat().st_size
    if file_size == 0:
        return counts

    with path.open("rb") as handle:
        # Memory map the file
        with mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            # Scan all consecutive byte pairs
            for i in tqdm(range(len(mm) - 1), desc="Scanning byte pairs", unit="pairs"):
                counts[(mm[i], mm[i + 1])] += 1

    return counts


def scan_triplets(path: Path) -> Grid3DCounts:
    """Return a 3D grid of triplet frequencies keyed by ``(x, y, z)`` tuples.

    Uses memory mapping for efficient sequential access without loading the
    entire file into memory at once.
    """

    counts: Grid3DCounts = defaultdict(int)

    # Get file size using stat
    file_size = path.stat().st_size
    if file_size < 3:
        return counts

    with path.open("rb") as handle:
        # Memory map the file
        with mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            # Scan all consecutive byte triplets
            for i in tqdm(range(len(mm) - 2), desc="Scanning byte triplets", unit="triplets"):
                counts[(mm[i], mm[i + 1], mm[i + 2])] += 1

    return counts


def _load_bytes_to_db(path: Path, conn: sqlite3.Connection) -> int:
    """Load every byte of *path* into a ``bytes`` table and return the row count.

    The table has two columns: ``offset`` (the byte position) and ``value``
    (the unsigned byte value 0-255).  Rows are inserted in batches for
    efficiency and the table is indexed on ``offset`` to accelerate the
    window-function queries that follow.

    A ``_meta`` table is written alongside ``bytes`` so that subsequent runs
    against the same on-disk database can skip the load when the source file
    has not changed.
    """

    conn.execute("DROP TABLE IF EXISTS bytes")
    conn.execute("DROP TABLE IF EXISTS _meta")
    conn.execute("CREATE TABLE bytes (offset INTEGER PRIMARY KEY, value INTEGER NOT NULL)")
    conn.execute(
        "CREATE TABLE _meta (source_path TEXT, source_size INTEGER, source_mtime_ns INTEGER)"
    )

    stat = path.stat()
    file_size = stat.st_size

    if file_size > 0:
        BATCH = 65_536
        with path.open("rb") as fh:
            with mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                batch = []
                for i in tqdm(range(len(mm)), desc="Loading bytes into DB", unit="bytes"):
                    batch.append((i, mm[i]))
                    if len(batch) >= BATCH:
                        conn.executemany("INSERT INTO bytes VALUES (?, ?)", batch)
                        batch.clear()
                if batch:
                    conn.executemany("INSERT INTO bytes VALUES (?, ?)", batch)

    conn.execute(
        "INSERT INTO _meta VALUES (?, ?, ?)",
        (str(path.resolve()), file_size, int(stat.st_mtime_ns)),
    )
    conn.commit()
    return file_size


def scan_pairs_db(path: Path, db_path: Path | None = None) -> GridCounts:
    """Compute byte-pair frequencies using SQL window functions.

    Loads the file into an in-memory SQLite database (or the on-disk file
    given by *db_path*), uses ``LEAD()`` to form consecutive pairs, and
    aggregates with ``GROUP BY`` to produce the same ``GridCounts``
    dictionary as :func:`scan_pairs`.
    """

    counts: GridCounts = defaultdict(int)
    conn = sqlite3.connect(str(db_path) if db_path else ":memory:")
    try:
        fresh, n = _db_is_fresh(conn, path)
        if fresh:
            print(f"Reusing cached data from {db_path}")
        else:
            n = _load_bytes_to_db(path, conn)
        if n < 2:
            return counts

        rows = conn.execute(
            """
            SELECT b1, b2, COUNT(*) AS freq
            FROM (
                SELECT value AS b1,
                       LEAD(value) OVER (ORDER BY offset) AS b2
                FROM bytes
            )
            WHERE b2 IS NOT NULL
            GROUP BY b1, b2
            """
        )
        for b1, b2, freq in tqdm(rows, desc="Reading pair counts from DB"):
            counts[(b1, b2)] = freq
    finally:
        conn.close()
    return counts


def scan_triplets_db(path: Path, db_path: Path | None = None) -> Grid3DCounts:
    """Compute byte-triplet frequencies using SQL window functions.

    Loads the file into an in-memory SQLite database (or the on-disk file
    given by *db_path*), uses ``LEAD()`` to form consecutive triplets, and
    aggregates with ``GROUP BY`` to produce the same ``Grid3DCounts``
    dictionary as :func:`scan_triplets`.
    """

    counts: Grid3DCounts = defaultdict(int)
    conn = sqlite3.connect(str(db_path) if db_path else ":memory:")
    try:
        fresh, n = _db_is_fresh(conn, path)
        if fresh:
            print(f"Reusing cached data from {db_path}")
        else:
            n = _load_bytes_to_db(path, conn)
        if n < 3:
            return counts

        rows = conn.execute(
            """
            SELECT b1, b2, b3, COUNT(*) AS freq
            FROM (
                SELECT value AS b1,
                       LEAD(value, 1) OVER (ORDER BY offset) AS b2,
                       LEAD(value, 2) OVER (ORDER BY offset) AS b3
                FROM bytes
            )
            WHERE b2 IS NOT NULL AND b3 IS NOT NULL
            GROUP BY b1, b2, b3
            """
        )
        for b1, b2, b3, freq in tqdm(rows, desc="Reading triplet counts from DB"):
            counts[(b1, b2, b3)] = freq
    finally:
        conn.close()
    return counts


def _load_bytes_to_duckdb(path: Path, conn: duckdb.DuckDBPyConnection) -> int:
    """Load every byte of *path* into a ``bytes`` table and return the row count.

    Uses the same schema as :func:`_load_bytes_to_db` but targets a DuckDB
    connection.  DuckDB's vectorised execution makes the subsequent
    window-function queries significantly faster than SQLite for large files.

    A ``_meta`` table is written alongside ``bytes`` so that subsequent runs
    against the same on-disk database can skip the load when the source file
    has not changed.
    """

    conn.execute("DROP TABLE IF EXISTS bytes")
    conn.execute("DROP TABLE IF EXISTS _meta")
    conn.execute("CREATE TABLE bytes (pos INTEGER, value INTEGER)")
    conn.execute(
        "CREATE TABLE _meta (source_path TEXT, source_size BIGINT, source_mtime_ns BIGINT)"
    )

    stat = path.stat()
    file_size = stat.st_size

    if file_size > 0:
        BATCH = 65_536
        with path.open("rb") as fh:
            with mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                batch = []
                for i in tqdm(range(len(mm)), desc="Loading bytes into DuckDB", unit="bytes"):
                    batch.append((i, mm[i]))
                    if len(batch) >= BATCH:
                        conn.executemany("INSERT INTO bytes VALUES (?, ?)", batch)
                        batch.clear()
                if batch:
                    conn.executemany("INSERT INTO bytes VALUES (?, ?)", batch)

    conn.execute(
        "INSERT INTO _meta VALUES (?, ?, ?)",
        (str(path.resolve()), file_size, int(stat.st_mtime_ns)),
    )
    return file_size


def scan_pairs_duckdb(path: Path, db_path: Path | None = None) -> GridCounts:
    """Compute byte-pair frequencies using DuckDB window functions.

    Same approach as :func:`scan_pairs_db` but uses DuckDB's columnar,
    vectorised engine which is significantly faster for analytical queries.
    """

    if not DUCKDB_AVAILABLE:
        raise ImportError(
            "DuckDB is required for --engine duckdb. "
            "Install it with: pip install duckdb"
        )

    counts: GridCounts = defaultdict(int)
    conn = duckdb.connect(str(db_path) if db_path else ":memory:")
    try:
        fresh, n = _db_is_fresh(conn, path)
        if fresh:
            print(f"Reusing cached data from {db_path}")
        else:
            n = _load_bytes_to_duckdb(path, conn)
        if n < 2:
            return counts

        rows = conn.execute(
            """
            SELECT b1, b2, COUNT(*) AS freq
            FROM (
                SELECT value AS b1,
                       LEAD(value) OVER (ORDER BY pos) AS b2
                FROM bytes
            )
            WHERE b2 IS NOT NULL
            GROUP BY b1, b2
            """
        ).fetchall()
        for b1, b2, freq in tqdm(rows, desc="Reading pair counts from DuckDB"):
            counts[(b1, b2)] = freq
    finally:
        conn.close()
    return counts


def scan_triplets_duckdb(path: Path, db_path: Path | None = None) -> Grid3DCounts:
    """Compute byte-triplet frequencies using DuckDB window functions.

    Same approach as :func:`scan_triplets_db` but uses DuckDB's columnar,
    vectorised engine which is significantly faster for analytical queries.
    """

    if not DUCKDB_AVAILABLE:
        raise ImportError(
            "DuckDB is required for --engine duckdb. "
            "Install it with: pip install duckdb"
        )

    counts: Grid3DCounts = defaultdict(int)
    conn = duckdb.connect(str(db_path) if db_path else ":memory:")
    try:
        fresh, n = _db_is_fresh(conn, path)
        if fresh:
            print(f"Reusing cached data from {db_path}")
        else:
            n = _load_bytes_to_duckdb(path, conn)
        if n < 3:
            return counts

        rows = conn.execute(
            """
            SELECT b1, b2, b3, COUNT(*) AS freq
            FROM (
                SELECT value AS b1,
                       LEAD(value, 1) OVER (ORDER BY pos) AS b2,
                       LEAD(value, 2) OVER (ORDER BY pos) AS b3
                FROM bytes
            )
            WHERE b2 IS NOT NULL AND b3 IS NOT NULL
            GROUP BY b1, b2, b3
            """
        ).fetchall()
        for b1, b2, b3, freq in tqdm(rows, desc="Reading triplet counts from DuckDB"):
            counts[(b1, b2, b3)] = freq
    finally:
        conn.close()
    return counts


def max_count(counts: GridCounts) -> int:
    """Return the maximum frequency present in the grid."""

    return max(counts.values(), default=0)


def max_count_3d(counts: Grid3DCounts) -> int:
    """Return the maximum frequency present in the 3D grid."""

    return max(counts.values(), default=0)


def brightness(value: int, max_value: int, mode: str) -> int:
    """Convert a count to a grayscale value (0-255) using the requested curve."""

    if value == 0 or max_value == 0:
        return 0

    ratio = value / max_value
    if mode == "log":
        ratio = math.log1p(value) / math.log1p(max_value)
    elif mode == "sqrt":
        ratio = math.sqrt(ratio)

    ratio = max(0.0, min(1.0, ratio))
    scaled = ratio * 255
    # ``max`` ensures the faintest non-zero pair is not pure black.
    return min(255, max(1, int(round(scaled))))


def write_ppm(counts: GridCounts, peak: int, output: Path, scale: str) -> None:
    """Write the grayscale visualization as an ASCII PPM file."""

    with output.open("w", encoding="ascii") as handle:
        handle.write("P3\n256 256\n255\n")
        for y in tqdm(range(256), desc="Writing PPM", unit="rows"):
            row_values = []
            for x in range(256):
                count = counts.get((x, y), 0)
                value = brightness(count, peak, scale)
                row_values.append(f"{value} {value} {value}")
            handle.write(" ".join(row_values) + "\n")


def write_plotly_3d(
    counts: Grid3DCounts, peak: int, output: Path, scale: str, max_points: int = 100000
) -> None:
    """Write an interactive 3D Plotly visualization as HTML.

    Creates a 3D scatter plot where each point represents a byte triplet.
    Point size and color represent frequency (applying the selected tone mapping).
    Only non-zero triplets are displayed to keep the visualization manageable.

    If there are more than max_points triplets, intelligently sample them,
    prioritizing high-frequency triplets for better performance and visual quality.
    """

    if not PLOTLY_AVAILABLE:
        raise ImportError(
            "Plotly is required for 3D visualization. "
            "Run this script with 'uv run' to automatically install dependencies."
        )

    # Extract non-zero triplets
    triplets = [(coords, count) for coords, count in counts.items() if count > 0]
    total_triplets = len(triplets)

    # Sample if needed to keep browser performance reasonable
    if total_triplets > max_points:
        print(f"Sampling {max_points:,} of {total_triplets:,} triplets for performance")
        # Sort by frequency (descending) to keep most significant patterns
        print("Sorting triplets by frequency...")
        triplets.sort(key=lambda item: item[1], reverse=True)
        triplets = triplets[:max_points]

    x_coords = []
    y_coords = []
    z_coords = []
    rgba_colors = []
    values = []  # Keep values for colorbar reference
    hover_text = []

    # Get the viridis colorscale
    viridis = plotly.colors.sequential.Viridis

    for (x, y, z), count in tqdm(triplets, desc="Processing triplets", unit="triplets"):
        x_coords.append(x)
        y_coords.append(y)
        z_coords.append(z)
        # Apply tone mapping to the count
        mapped_value = brightness(count, peak, scale)
        values.append(mapped_value)
        # Calculate opacity based on frequency (0.2 to 1.0 range)
        # More common points are more opaque
        opacity = 0.2 + (mapped_value / 255) * 0.8

        # Map the value to a viridis color and add alpha channel
        # Normalize mapped_value to 0-1 range for colorscale lookup
        norm_value = mapped_value / 255
        # Get color from viridis scale
        color_idx = int(norm_value * (len(viridis) - 1))
        rgb_str = viridis[color_idx]
        # Convert hex to RGB
        rgb = plotly.colors.hex_to_rgb(rgb_str)
        # Create RGBA string with variable alpha
        rgba = f'rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {opacity})'
        rgba_colors.append(rgba)

        hover_text.append(
            f"Triplet: [{x:02x}, {y:02x}, {z:02x}]<br>"
            f"Count: {count}<br>"
            f"Brightness: {mapped_value}/255<br>"
            f"Opacity: {opacity:.2f}"
        )

    # Create 3D scatter plot with RGBA colors for variable transparency
    main_trace = go.Scatter3d(
        x=x_coords,
        y=y_coords,
        z=z_coords,
        mode='markers',
        marker=dict(
            size=3,
            color=rgba_colors
        ),
        text=hover_text,
        hoverinfo='text',
        name='Triplets'
    )

    # Add invisible trace for colorbar legend
    # This shows the frequency scale without the transparency
    colorbar_trace = go.Scatter3d(
        x=[None],  # No actual points
        y=[None],
        z=[None],
        mode='markers',
        marker=dict(
            size=3,
            color=[0, 255],  # Min and max values
            colorscale='Viridis',
            showscale=True,
            colorbar=dict(
                title="Frequency<br>(mapped)",
                tickvals=[0, 64, 128, 192, 255],
                ticktext=['Low', '', 'Medium', '', 'High']
            ),
            cmin=0,
            cmax=255
        ),
        showlegend=False,
        hoverinfo='skip'
    )

    fig = go.Figure(data=[main_trace, colorbar_trace])

    fig.update_layout(
        title=f"3D Byte Triplet Visualization ({scale} scale)",
        scene=dict(
            xaxis_title="Byte 1 (0x00-0xFF)",
            yaxis_title="Byte 2 (0x00-0xFF)",
            zaxis_title="Byte 3 (0x00-0xFF)",
            xaxis=dict(range=[0, 255]),
            yaxis=dict(range=[0, 255]),
            zaxis=dict(range=[0, 255])
        ),
        width=1200,
        height=900
    )

    output_dir = output.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # Change extension to .html
    html_path = output.with_suffix('.html')
    fig.write_html(str(html_path))

    print(f"Wrote interactive 3D visualization to {html_path}")
    print(f"Total unique triplets: {len(x_coords):,}")


def main() -> None:
    args = parse_args()
    engine = args.engine
    db_path = args.db_path

    if args.mode == "2d":
        if engine == "sqlite":
            counts = scan_pairs_db(args.input, db_path=db_path)
        elif engine == "duckdb":
            counts = scan_pairs_duckdb(args.input, db_path=db_path)
        else:
            counts = scan_pairs(args.input)
        peak = max_count(counts)
        write_ppm(counts, peak, args.output, args.scale)
    else:  # 3d mode
        if engine == "sqlite":
            counts_3d = scan_triplets_db(args.input, db_path=db_path)
        elif engine == "duckdb":
            counts_3d = scan_triplets_duckdb(args.input, db_path=db_path)
        else:
            counts_3d = scan_triplets(args.input)
        peak = max_count_3d(counts_3d)
        write_plotly_3d(counts_3d, peak, args.output, args.scale)


if __name__ == "__main__":
    main()
