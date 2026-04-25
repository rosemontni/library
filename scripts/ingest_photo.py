from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

import app  # noqa: E402


DEFAULT_METADATA_PATH = ROOT_DIR / "samples" / "blue_little_library_books.json"


def load_metadata(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        metadata = json.load(handle)

    if not isinstance(metadata.get("books"), list) or not metadata["books"]:
        raise ValueError(f"{path} must contain a non-empty books array")

    return metadata


def fingerprint_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:12]


def stored_photo_path(image_path: Path) -> Path:
    suffix = image_path.suffix.lower() or ".jpg"
    return app.UPLOADS_DIR / f"{image_path.stem}-{fingerprint_file(image_path)}{suffix}"


def relative_upload_path(path: Path) -> str:
    return path.relative_to(app.BASE_DIR).as_posix()


def existing_library_for_photo(photo_path: str) -> dict[str, Any] | None:
    with app.get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, name, latitude, longitude, photo_path
            FROM libraries
            WHERE photo_path = ?
            """,
            (photo_path,),
        ).fetchone()

    return dict(row) if row else None


def copy_photo(image_path: Path) -> str:
    app.ensure_directories()
    destination = stored_photo_path(image_path)
    if not destination.exists():
        shutil.copy2(image_path, destination)
    return relative_upload_path(destination)


def build_payload(image_path: Path, metadata: dict[str, Any], photo_path: str, allow_missing_location: bool) -> dict[str, Any]:
    image_bytes = image_path.read_bytes()
    location = app.extract_exif_gps(image_bytes)

    if location is None and not allow_missing_location:
        raise ValueError(
            "No valid EXIF GPS coordinates were found. Pass --allow-missing-location to ingest without coordinates."
        )

    geolocation = (
        location.to_dict()
        if location
        else {
            "latitude": None,
            "longitude": None,
            "source": "unavailable",
            "confidence": 0.0,
            "accuracy_meters": None,
        }
    )

    return {
        "library_name": metadata.get("library_name") or image_path.stem,
        "library_description": metadata.get("library_description") or "",
        "photo_path": photo_path,
        "place_clues": metadata.get("place_clues") or [],
        "geolocation": geolocation,
        "books": metadata["books"],
    }


def verify_search(query: str, latitude: float | None, longitude: float | None, radius_miles: float) -> dict[str, Any]:
    results = app.search_books(query, latitude, longitude, radius_miles)
    return {
        "query": query,
        "count": len(results),
        "top_result": results[0] if results else None,
    }


def ingest(args: argparse.Namespace) -> dict[str, Any]:
    image_path = args.image.resolve()
    metadata_path = args.metadata.resolve()

    if not image_path.exists():
        raise FileNotFoundError(image_path)
    if not metadata_path.exists():
        raise FileNotFoundError(metadata_path)

    app.initialize_database()
    metadata = load_metadata(metadata_path)
    photo_path = copy_photo(image_path)
    existing = existing_library_for_photo(photo_path)

    if existing:
        library_id = int(existing["id"])
        inserted = False
        latitude = existing["latitude"]
        longitude = existing["longitude"]
    else:
        payload = build_payload(image_path, metadata, photo_path, args.allow_missing_location)
        library_id = app.insert_library(payload)
        inserted = True
        latitude = payload["geolocation"]["latitude"]
        longitude = payload["geolocation"]["longitude"]

    query = args.verify_query or metadata.get("verify_query") or metadata["books"][0]["title"]
    verification = verify_search(query, latitude, longitude, args.radius_miles)

    return {
        "status": "inserted" if inserted else "already_exists",
        "library_id": library_id,
        "photo_path": photo_path,
        "metadata_path": str(metadata_path),
        "geolocation": {
            "latitude": latitude,
            "longitude": longitude,
            "source": "photo_exif" if latitude is not None and longitude is not None else "unavailable",
        },
        "verification": verification,
        "counts": app.get_counts(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest a local little-library photo into the SQLite atlas.")
    parser.add_argument("image", type=Path, help="Path to a local JPEG or image file.")
    parser.add_argument(
        "--metadata",
        type=Path,
        default=DEFAULT_METADATA_PATH,
        help="JSON metadata file with library fields and books.",
    )
    parser.add_argument(
        "--verify-query",
        default="",
        help="Optional title, author, or ISBN to search after ingesting.",
    )
    parser.add_argument(
        "--radius-miles",
        type=float,
        default=25.0,
        help="Search radius used for the verification query.",
    )
    parser.add_argument(
        "--allow-missing-location",
        action="store_true",
        help="Allow ingesting a photo that has no valid EXIF GPS.",
    )
    return parser.parse_args()


def main() -> int:
    try:
        result = ingest(parse_args())
    except (FileNotFoundError, ValueError, sqlite3.Error) as error:
        print(json.dumps({"status": "error", "error": str(error)}, indent=2))
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
