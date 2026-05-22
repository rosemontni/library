from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

try:
    from scripts.validate_public_export import validate_public_export
except ModuleNotFoundError:
    from validate_public_export import validate_public_export


REQUIRED_ELEMENT_IDS = (
    "libraryCount",
    "bookCount",
    "generatedAt",
    "searchForm",
    "searchQuery",
    "zipCode",
    "radiusMiles",
    "useLocation",
    "locationStatus",
    "results",
    "map",
    "mapStatus",
    "fitMarkers",
    "databaseSummary",
    "contribute",
    "builderNotes",
)

REQUIRED_APP_SNIPPETS = (
    "lookupZipCode",
    "searchBooks",
    "renderMap",
    "popupHtml",
    "libraryLocationLabel",
    "LOCAL_ZIP_CENTROIDS",
)


def normalize(value: object) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s-]+", " ", str(value or "").lower())).strip()


def has_coordinates(library: dict) -> bool:
    try:
        latitude = float(library.get("latitude"))
        longitude = float(library.get("longitude"))
    except (TypeError, ValueError):
        return False
    return math.isfinite(latitude) and math.isfinite(longitude)


def book_search_blob(book: dict) -> str:
    return normalize(
        " ".join(
            str(book.get(key) or "")
            for key in ("title", "author", "isbn", "publisher", "published_year", "genre", "format", "notes")
        )
    )


def validate_pages_site(site_root: Path) -> list[str]:
    errors: list[str] = []
    site_root = Path(site_root)
    index_path = site_root / "index.html"
    app_path = site_root / "app.js"
    data_path = site_root / "atlas-data.json"

    for path in (index_path, app_path, data_path):
        if not path.exists():
            errors.append(f"Missing required Pages file: {path}")

    if errors:
        return errors

    index_html = index_path.read_text(encoding="utf-8")
    app_js = app_path.read_text(encoding="utf-8")

    errors.extend(validate_public_export(data_path, site_root))

    for element_id in REQUIRED_ELEMENT_IDS:
        if not re.search(rf"\bid=[\"']{re.escape(element_id)}[\"']", index_html):
            errors.append(f"Missing HTML element id required by app.js: {element_id}")

    if "leaflet.css" not in index_html or "leaflet.js" not in index_html:
        errors.append("Leaflet assets are not referenced by docs/index.html.")

    for snippet in REQUIRED_APP_SNIPPETS:
        if snippet not in app_js:
            errors.append(f"Missing expected Pages JavaScript function or constant: {snippet}")

    try:
        data = json.loads(data_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return errors + [f"Invalid Pages JSON: {exc}"]

    libraries = data.get("libraries")
    books = data.get("books")
    counts = data.get("counts")
    if not isinstance(libraries, list):
        errors.append("atlas-data.json must contain a libraries array.")
        libraries = []
    if not isinstance(books, list):
        errors.append("atlas-data.json must contain a books array.")
        books = []
    if not isinstance(counts, dict):
        errors.append("atlas-data.json must contain a counts object.")
        counts = {}

    if counts.get("libraries") != len(libraries):
        errors.append(f"Library count mismatch: counts.libraries={counts.get('libraries')} actual={len(libraries)}")
    if counts.get("books") != len(books):
        errors.append(f"Book count mismatch: counts.books={counts.get('books')} actual={len(books)}")

    library_ids = {library.get("id") for library in libraries}
    if libraries and not any(has_coordinates(library) for library in libraries):
        errors.append("At least one exported library should have usable coordinates for the map.")

    for index, library in enumerate(libraries, start=1):
        if not library.get("id"):
            errors.append(f"Library at position {index} is missing an id.")
        if not library.get("csn"):
            errors.append(f"Library {library.get('id') or index} is missing a CSN.")
        if not library.get("name"):
            errors.append(f"Library {library.get('id') or index} is missing a name.")
        icon_url = library.get("icon_url")
        if icon_url:
            icon_path = (site_root / str(icon_url).lstrip("./")).resolve()
            if not icon_path.exists():
                errors.append(f"Library {library.get('id')} references a missing icon: {icon_url}")
        description = normalize(library.get("description"))
        csn = normalize(library.get("csn"))
        if csn and description.startswith(csn):
            errors.append(f"Library {library.get('id')} repeats its CSN at the start of the description.")

    for index, book in enumerate(books, start=1):
        if not book.get("title"):
            errors.append(f"Book at position {index} is missing a title.")
        if book.get("library_id") not in library_ids:
            errors.append(f"Book {book.get('title') or index} points to an unknown library_id: {book.get('library_id')}")

    if books:
        sample_book = next((book for book in books if normalize(book.get("title"))), books[0])
        sample_terms = normalize(sample_book.get("title")).split()[:2]
        if sample_terms and not any(all(term in book_search_blob(book) for term in sample_terms) for book in books):
            errors.append("Static search smoke test could not find an exported sample book by title terms.")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the generated Civitas Library GitHub Pages site.")
    parser.add_argument("--site-root", type=Path, default=Path("docs"), help="Path to the generated static site root.")
    args = parser.parse_args()

    errors = validate_pages_site(args.site_root)
    if errors:
        print("GitHub Pages smoke test failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"GitHub Pages smoke test passed: {args.site_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
