# Civitas Library Public API

Civitas Library exposes a small, read-only HTTP API for community programmers who want to search the shared mini-library database from scripts, bots, local apps, classroom projects, or civic experiments.

Base URL for local development:

```text
http://127.0.0.1:8000
```

Production deployments should serve the same paths over HTTPS.

## Fair Use And Rate Limits

The public API is designed for neighbors and community tools, not bulk commercial scraping.

- Default limit: `60` requests per `60` seconds per client IP.
- Override for deployments: set `PUBLIC_API_RATE_LIMIT_REQUESTS` and `PUBLIC_API_RATE_LIMIT_WINDOW_SECONDS`.
- A limited request returns HTTP `429` with `Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` headers.
- Cache responses where practical, especially library lists and repeated common searches.

If you want to do a larger research export, contact `civitaslibrary@gmail.com` first so we can find a friendly path.

## Search Books

```http
GET /api/v1/search?q=gardening&zip=20877&radius_miles=25&limit=5
```

Query parameters:

- `q`: Title, author, topic, publisher, ISBN, or any visible book metadata.
- `category`: Optional broad category, such as `non-fiction`, `gardening`, `kids`, `history`, `travel`, `wellness`, or `media`.
- `zip`: Optional 5-digit ZIP code for distance ranking. The server includes a local centroid table for the current DC/Maryland/Virginia collection area.
- `lat` and `lon`: Optional coordinates for distance ranking. Use these instead of ZIP for locations outside the built-in table.
- `radius_miles`: Optional search radius. Defaults to `25`; capped at `250`.
- `limit`: Optional result limit. Defaults to `25`; capped at `100`.

Example with Python:

```python
import requests

response = requests.get(
    "http://127.0.0.1:8000/api/v1/search",
    params={"q": "Octavia Butler", "zip": "20877", "radius_miles": 25, "limit": 10},
    timeout=10,
)
response.raise_for_status()
for item in response.json()["results"]:
    print(item["title"], "at", item["library"]["csn"], item["library"]["name"])
```

Example with JavaScript:

```javascript
const params = new URLSearchParams({
  q: "gardening",
  zip: "20877",
  radius_miles: "25",
  limit: "10",
});

const response = await fetch(`/api/v1/search?${params}`);
if (!response.ok) throw new Error(`API error ${response.status}`);
const payload = await response.json();
console.log(payload.results);
```

## List Libraries

```http
GET /api/v1/libraries?zip=20877&limit=25&offset=0
```

This returns mini-library records with CSNs, descriptions, location labels, coordinates, charter metadata when known, derived 144x144 icon URLs, active book counts, and up to five sample book titles.

Map placement uses the photo GPS location, not the postal address. Use `marker_latitude` and `marker_longitude` for pins. `official_address` is display metadata only, because a large campus, park, apartment complex, or institution can have a mailing address far from the actual book box.

Parameters:

- `q`: Optional text filter over library name, description, charter number, and sample books.
- `zip`, `lat`, `lon`: Optional distance ranking.
- `limit`: Defaults to `25`; capped at `100`.
- `offset`: Defaults to `0`.

## Get One Library

```http
GET /api/v1/libraries/12
```

This returns one library plus its active books. Removed historical books are kept in the database but are intentionally excluded from the public active-search API.

## Machine-Readable Schema

```http
GET /api/v1/openapi.json
```

The OpenAPI document describes the public read endpoints and can be used by API clients, docs tools, or typed-client generators.

## Privacy Notes

Original phone photos are not exposed by this API. Public responses may include only derived shelf icons from `docs/library-icons`, library metadata, book metadata, and non-sensitive location labels. When an official Little Free Library registry match is available, the API returns the official address; otherwise it may return coordinates.
