from __future__ import annotations

import argparse
import html
import json
import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT_DIR / "data" / "little_library_atlas.db"
DEFAULT_OUTPUT_PATH = ROOT_DIR / "assets" / "library-map.svg"
DEFAULT_BOX_TYPE = "library"
BOX_TYPE_LABELS = {
    "library": "Little Library",
    "art_gallery": "Little Art Gallery",
}
BOX_TYPE_COLORS = {
    "art_gallery": "#5f57c8",
}


def ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


@dataclass(frozen=True)
class LibraryPoint:
    id: int
    name: str
    box_type: str
    description: str
    latitude: float
    longitude: float
    book_count: int
    official_address: str

    @property
    def csn(self) -> str:
        return f"CSN-{self.id}"

    @property
    def location_label(self) -> str:
        return self.official_address or f"{self.latitude:.4f}, {self.longitude:.4f}"

    @property
    def type_label(self) -> str:
        return BOX_TYPE_LABELS.get(self.box_type, BOX_TYPE_LABELS[DEFAULT_BOX_TYPE])

    @property
    def inventory_label(self) -> str:
        if self.box_type == "art_gallery":
            return "art exchange"
        return f"{self.book_count} book{'s' if self.book_count != 1 else ''}"


def escape(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def parse_json_object(raw_value: str | None) -> dict[str, Any]:
    if not raw_value:
        return {}
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def format_official_address(raw_value: str | None) -> str:
    record = parse_json_object(raw_value)
    if record.get("status") != "matched":
        return ""

    street = str(record.get("street") or "").strip()
    city = str(record.get("city") or "").strip()
    state = str(record.get("state") or "").strip()
    postal_code = str(record.get("postal_code") or "").strip()
    country = str(record.get("country") or "").strip()

    city_line = ", ".join(part for part in [city, state] if part)
    if postal_code:
        city_line = f"{city_line} {postal_code}".strip()

    parts = [part for part in [street, city_line] if part]
    if country and country.upper() not in {"US", "USA", "UNITED STATES"}:
        parts.append(country)
    return ", ".join(parts)


def normalize_box_type(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in BOX_TYPE_LABELS else DEFAULT_BOX_TYPE


def load_library_points(db_path: Path) -> list[LibraryPoint]:
    if not db_path.exists():
        return []

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        ensure_column(connection, "books", "status", "TEXT NOT NULL DEFAULT 'active'")
        ensure_column(connection, "libraries", "box_type", "TEXT NOT NULL DEFAULT 'library'")
        ensure_column(connection, "libraries", "charter_record_json", "TEXT")
        rows = connection.execute(
            """
            SELECT
                l.id,
                l.name,
                COALESCE(l.box_type, 'library') AS box_type,
                l.description,
                l.latitude,
                l.longitude,
                l.charter_record_json,
                COUNT(b.id) AS book_count
            FROM libraries l
            LEFT JOIN books b
                ON b.library_id = l.id
               AND COALESCE(b.status, 'active') = 'active'
            WHERE l.latitude IS NOT NULL
              AND l.longitude IS NOT NULL
            GROUP BY l.id
            ORDER BY l.id ASC
            """
        ).fetchall()

    return [
        LibraryPoint(
            id=int(row["id"]),
            name=str(row["name"] or f"Library {row['id']}"),
            box_type=normalize_box_type(row["box_type"]),
            description=str(row["description"] or ""),
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            book_count=int(row["book_count"] or 0),
            official_address=format_official_address(row["charter_record_json"]),
        )
        for row in rows
    ]


def mercator(latitude: float, longitude: float) -> tuple[float, float]:
    clamped_latitude = max(min(latitude, 85.05112878), -85.05112878)
    sin_lat = math.sin(math.radians(clamped_latitude))
    x = (longitude + 180.0) / 360.0
    y = 0.5 - math.log((1.0 + sin_lat) / (1.0 - sin_lat)) / (4.0 * math.pi)
    return x, y


def interpolate(start: float, end: float, count: int) -> list[float]:
    if count <= 1:
        return [(start + end) / 2.0]
    return [start + ((end - start) * index / (count - 1)) for index in range(count)]


def point_label(index: int) -> str:
    return str(index + 1)


def render_empty_map(updated_at: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675" role="img" aria-labelledby="title desc">
  <title id="title">Civitas Library map</title>
  <desc id="desc">No geolocated community boxes have been added yet.</desc>
  <rect width="1200" height="675" rx="32" fill="#f7f0df"/>
  <rect x="48" y="48" width="1104" height="579" rx="28" fill="#fffaf0" stroke="#2f3a2f" stroke-width="3"/>
  <text x="86" y="122" fill="#1f2d24" font-family="Georgia, serif" font-size="48" font-weight="700">Civitas Library</text>
  <text x="86" y="176" fill="#526057" font-family="Arial, sans-serif" font-size="22">Map snapshot generated from the local SQLite database</text>
  <circle cx="600" cy="344" r="78" fill="#d8ead7" stroke="#5c7b5f" stroke-width="5"/>
  <path d="M600 287c-27 0-49 22-49 49 0 39 49 89 49 89s49-50 49-89c0-27-22-49-49-49z" fill="#c9523d"/>
  <circle cx="600" cy="336" r="18" fill="#fffaf0"/>
  <text x="600" y="514" text-anchor="middle" fill="#1f2d24" font-family="Arial, sans-serif" font-size="28" font-weight="700">No geolocated community boxes yet</text>
  <text x="600" y="552" text-anchor="middle" fill="#526057" font-family="Arial, sans-serif" font-size="18">Add a photo with GPS coordinates, then rerun scripts/render_library_map.py.</text>
  <text x="86" y="606" fill="#6e756f" font-family="Arial, sans-serif" font-size="15">Updated {escape(updated_at)}</text>
</svg>
"""


def render_library_map(db_path: Path = DEFAULT_DB_PATH, output_path: Path = DEFAULT_OUTPUT_PATH) -> dict[str, Any]:
    points = load_library_points(Path(db_path))
    updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not points:
        output_path.write_text(render_empty_map(updated_at), encoding="utf-8")
        return {"libraries": 0, "output": str(output_path)}

    projected = [mercator(point.latitude, point.longitude) for point in points]
    min_x = min(x for x, _ in projected)
    max_x = max(x for x, _ in projected)
    min_y = min(y for _, y in projected)
    max_y = max(y for _, y in projected)

    if math.isclose(min_x, max_x):
        min_x -= 0.00005
        max_x += 0.00005
    if math.isclose(min_y, max_y):
        min_y -= 0.00005
        max_y += 0.00005

    pad_x = (max_x - min_x) * 0.18
    pad_y = (max_y - min_y) * 0.18
    min_x -= pad_x
    max_x += pad_x
    min_y -= pad_y
    max_y += pad_y

    width = 1200
    height = 675
    map_x = 48
    map_y = 126
    map_w = 752
    map_h = 484
    side_x = 832
    side_y = 126

    def to_screen(projected_x: float, projected_y: float) -> tuple[float, float]:
        x = map_x + ((projected_x - min_x) / (max_x - min_x)) * map_w
        y = map_y + ((projected_y - min_y) / (max_y - min_y)) * map_h
        return x, y

    marker_rows = []
    sidebar_rows = []
    palette = ["#c94f3d", "#e2a236", "#477c66", "#416c9f", "#8c5b92", "#7a633c", "#d66a72", "#2f757f"]

    for index, (point, (projected_x, projected_y)) in enumerate(zip(points, projected)):
        screen_x, screen_y = to_screen(projected_x, projected_y)
        color = BOX_TYPE_COLORS.get(point.box_type, palette[index % len(palette)])
        label = point_label(index)
        csn = escape(point.csn)
        title = escape(point.name)
        location_label = escape(point.location_label)
        description = escape(point.description[:94] + ("..." if len(point.description) > 94 else ""))
        described_as_raw = point.description
        described_as = escape(described_as_raw[:106] + ("..." if len(described_as_raw) > 106 else ""))
        type_label = escape(point.type_label)
        inventory_label = escape(point.inventory_label)

        marker_rows.append(
            f"""    <g class="marker" transform="translate({screen_x:.2f} {screen_y:.2f})">
      <title>{csn} - {title}: {type_label}, {inventory_label}. {description}</title>
      <path d="M0 -29c-18 0-32 14-32 32 0 25 32 58 32 58S32 28 32 3C32 -15 18 -29 0 -29z" fill="{color}" stroke="#213226" stroke-width="4"/>
      <circle cx="0" cy="2" r="18" fill="#fffaf0"/>
      <text x="0" y="9" text-anchor="middle" font-family="Arial, sans-serif" font-size="20" font-weight="800" fill="#213226">{label}</text>
    </g>"""
        )

        y = side_y + 40 + index * 68
        sidebar_rows.append(
            f"""    <g transform="translate({side_x} {y})">
      <circle cx="0" cy="-8" r="18" fill="{color}" stroke="#213226" stroke-width="3"/>
      <text x="0" y="-1" text-anchor="middle" font-family="Arial, sans-serif" font-size="17" font-weight="800" fill="#fffaf0">{label}</text>
      <text x="32" y="-16" font-family="Arial, sans-serif" font-size="19" font-weight="800" fill="#1f2d24">{csn} - {title}</text>
      <text x="32" y="8" font-family="Arial, sans-serif" font-size="15" fill="#536158">{type_label} · {inventory_label} at {location_label}</text>
      <text x="32" y="30" font-family="Arial, sans-serif" font-size="13" fill="#7a8079">{described_as}</text>
    </g>"""
        )

    longitude_values = interpolate(
        min(point.longitude for point in points),
        max(point.longitude for point in points),
        5,
    )
    latitude_values = interpolate(
        min(point.latitude for point in points),
        max(point.latitude for point in points),
        5,
    )

    grid_rows = []
    for longitude in longitude_values:
        projected_x, _ = mercator(sum(point.latitude for point in points) / len(points), longitude)
        x, _ = to_screen(projected_x, min_y)
        grid_rows.append(
            f"""    <line x1="{x:.2f}" y1="{map_y}" x2="{x:.2f}" y2="{map_y + map_h}" class="grid"/>
    <text x="{x + 6:.2f}" y="{map_y + map_h - 10}" class="grid-label">{longitude:.3f}</text>"""
        )
    for latitude in latitude_values:
        _, projected_y = mercator(latitude, sum(point.longitude for point in points) / len(points))
        _, y = to_screen(min_x, projected_y)
        grid_rows.append(
            f"""    <line x1="{map_x}" y1="{y:.2f}" x2="{map_x + map_w}" y2="{y:.2f}" class="grid"/>
    <text x="{map_x + 10}" y="{y - 8:.2f}" class="grid-label">{latitude:.3f}</text>"""
        )

    center_lat = sum(point.latitude for point in points) / len(points)
    center_lon = sum(point.longitude for point in points) / len(points)
    total_books = sum(point.book_count for point in points)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">Civitas Library map</title>
  <desc id="desc">Map of {len(points)} geolocated community boxes with numbered markers, Civitas Library Serial Numbers, descriptions, and content summaries.</desc>
  <defs>
    <linearGradient id="paper" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0" stop-color="#fff7e8"/>
      <stop offset="1" stop-color="#e8f0dc"/>
    </linearGradient>
    <radialGradient id="park" cx="38%" cy="34%" r="75%">
      <stop offset="0" stop-color="#edf8dc"/>
      <stop offset="1" stop-color="#d1e5be"/>
    </radialGradient>
    <style>
      .small {{ font-family: Arial, sans-serif; fill: #536158; }}
      .grid {{ stroke: rgba(41, 65, 47, 0.22); stroke-width: 1.2; stroke-dasharray: 7 8; }}
      .grid-label {{ font-family: Arial, sans-serif; font-size: 12px; fill: rgba(46, 65, 53, 0.65); }}
      .road {{ fill: none; stroke: rgba(255, 250, 240, 0.86); stroke-width: 18; stroke-linecap: round; }}
      .road-line {{ fill: none; stroke: rgba(89, 102, 78, 0.35); stroke-width: 2; stroke-linecap: round; stroke-dasharray: 10 12; }}
    </style>
  </defs>
  <rect width="{width}" height="{height}" rx="34" fill="#263529"/>
  <rect x="18" y="18" width="{width - 36}" height="{height - 36}" rx="30" fill="url(#paper)"/>
  <text x="48" y="68" fill="#1f2d24" font-family="Georgia, serif" font-size="39" font-weight="700">Civitas Library</text>
  <text x="50" y="99" class="small" font-size="18">Generated map snapshot: {len(points)} community boxes, {total_books} books, CSN = database serial ID, centered near {center_lat:.4f}, {center_lon:.4f}</text>

  <g>
    <rect x="{map_x}" y="{map_y}" width="{map_w}" height="{map_h}" rx="28" fill="url(#park)" stroke="#253529" stroke-width="4"/>
    <path class="road" d="M76 523 C222 454, 308 447, 398 376 S623 236, 784 204"/>
    <path class="road-line" d="M76 523 C222 454, 308 447, 398 376 S623 236, 784 204"/>
    <path class="road" d="M105 216 C240 260, 342 260, 468 215 S665 155, 789 182"/>
    <path class="road-line" d="M105 216 C240 260, 342 260, 468 215 S665 155, 789 182"/>
    <circle cx="210" cy="318" r="92" fill="rgba(92, 123, 95, 0.18)"/>
    <circle cx="620" cy="402" r="112" fill="rgba(92, 123, 95, 0.15)"/>
{chr(10).join(grid_rows)}
{chr(10).join(marker_rows)}
    <text x="{map_x + 24}" y="{map_y + 36}" font-family="Arial, sans-serif" font-size="17" font-weight="800" fill="#263529">Geolocated community-box markers</text>
    <text x="{map_x + 24}" y="{map_y + map_h - 22}" class="small" font-size="14">SVG uses Web Mercator projection and local database coordinates.</text>
  </g>

  <g>
    <rect x="{side_x - 32}" y="{side_y}" width="336" height="{map_h}" rx="28" fill="#fffaf0" stroke="#253529" stroke-width="3"/>
    <text x="{side_x - 2}" y="{side_y + 27}" font-family="Arial, sans-serif" font-size="20" font-weight="900" fill="#1f2d24">Community boxes</text>
{chr(10).join(sidebar_rows)}
  </g>

  <text x="48" y="644" class="small" font-size="14">Updated {escape(updated_at)} by scripts/render_library_map.py. Photo uploads and SQLite data stay out of Git.</text>
</svg>
"""

    output_path.write_text(svg, encoding="utf-8")
    return {"libraries": len(points), "books": total_books, "output": str(output_path)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a README SVG map from the Civitas Library SQLite database.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Path to the SQLite database.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH, help="Destination SVG path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = render_library_map(args.db, args.output)
    print(f"Rendered {result.get('libraries', 0)} libraries to {result['output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
