# Civitas Library Architecture Improvement Plan

Date: May 21, 2026

Status: Authorized for incremental implementation by the project owner. Use small, reversible, verified slices rather than a single schema rewrite.

## Implementation Progress

- Phase 1 CI gates are in progress: backend tests, JavaScript syntax checks, public export privacy validation, GitHub Pages smoke testing, Android lint, Android unit-test task, and Android debug build are wired into GitHub Actions.
- Public export privacy validation is implemented through `scripts/validate_public_export.py`.
- Generated GitHub Pages output is smoke-tested through `scripts/smoke_test_pages.py` for required DOM wiring, map/search functions, exported data shape, icon references, and popup-ready library metadata.
- Backend SQLite initialization now records an explicit `schema_migrations` version and refuses to open databases created by newer app versions.
- Backend SQLite now includes the first observation-layer scaffold: `ingestion_runs`, `photo_evidence`, `model_predictions`, and `review_decisions`.
- Accepted mobile uploads now create an ingestion run and link each accepted GPS-tagged upload to `photo_evidence` for provenance auditing while preserving existing public export behavior.
- GPS-less mobile uploads are now covered by endpoint-level regression tests that verify rejection, no database writes, and no orphaned uploaded originals.
- Android local storage now has a non-destructive migration scaffold and allows empty-shelf observations.
- Larger observation-centered schema changes remain pending and should be handled in a separate migration-focused slice.

## Committee

This plan synthesizes four independent architecture reviews:

- Computer science professor: data model, correctness, abstractions, and long-term maintainability.
- Senior software engineer: backend/frontend/Android boundaries, deployment, security, privacy, and operations.
- Applied researcher at DeepMind: ML-assisted ingestion, uncertainty, evaluation, data quality, and human review.
- Software testing engineer: regression strategy, CI, Android tests, frontend tests, migrations, and deployment verification.

## Executive Summary

Civitas Library is a strong prototype with a coherent mission: turn GPS-tagged photos of mini libraries into a searchable, map-based public catalog while keeping original photos private. The current architecture is effective for local development and early data collection: SQLite is the source of truth, Python handles intake and export, GitHub Pages hosts the public read-only site, and Android provides a mobile capture path.

The main architectural risk is that the system currently treats photo-derived outputs as final records too quickly. A better long-term architecture should treat each upload as an observation with provenance, uncertainty, review state, and evidence. From those observations, the system can derive the current public catalog, historical inventory, duplicate candidates, and quality dashboards.

The second major risk is concentration of responsibility. `app.py` currently handles schema setup, HTTP routing, upload parsing, EXIF extraction, model calls, duplicate matching, inventory reconciliation, file serving, and export triggers. That is acceptable for a prototype, but it will become difficult to reason about as contributions grow.

## Highest Priority Recommendations

### P0: Add an Observation Layer

Introduce first-class records for photo submissions and review decisions before writing final library/book state. The system should store:

- Ingestion run ID, timestamp, contributor/source, model version, prompt version, and processing status.
- Photo evidence records for each uploaded image, including EXIF GPS, accuracy if available, original filename hash, accepted/rejected status, and whether the photo shows contents or surroundings.
- Raw model predictions, including detected books, charter numbers, confidence, uncertainty notes, and image references.
- Human review decisions, including accepted fields, corrected fields, rejected predictions, and reviewer notes.

The public database should be derived from accepted observations rather than being the first place model output lands.

### P0: Define a Stable Domain Data Model

Separate these concepts:

- Physical library: the real-world shelf, with CSN, charter number, address/location evidence, icon, and status.
- Observation event: one visit or upload batch documenting the shelf at a moment in time.
- Photo evidence: one accepted GPS-tagged image, classified as contents, surroundings, or both.
- Book edition: bibliographic metadata such as title, author, ISBN, publisher, publication year, and genre.
- Book observation: evidence that a book appeared in a specific library observation.
- Current inventory: a derived view from the latest accepted observation, not the canonical history.

This model will support empty shelves, removed books, duplicate-resolution workflows, and future quality analysis.

### P0: Protect Public Write Paths

Before any public deployment of contribution endpoints, add:

- Authentication or invite/contributor tokens.
- Rate limits and upload limits at a reverse proxy.
- Separate permissions for contributors, reviewers, and admins.
- Sanitized client errors and structured server logs.
- Explicit privacy rules for exact coordinates, private residences, and original uploads.

The local prototype can stay simple, but public write endpoints should not remain anonymous and unbounded.

## Target Architecture

### Backend Layers

Split the Python backend into clear modules:

- HTTP interface: request parsing, response formatting, and route definitions.
- Domain services: ingestion, review, duplicate detection, inventory derivation, search, and export orchestration.
- Persistence layer: repositories for libraries, observations, photos, books, and exports.
- Integrations: EXIF, OpenAI vision, Little Free Library lookup, geocoding, and icon generation.
- Jobs/exporters: GitHub Pages export, map rendering, icon refresh, and data quality reports.

This reduces risk in `app.py` and makes future tests more targeted.

### Database and Migrations

Move from ad hoc schema changes to versioned migrations. Short term, SQLite can remain the source of truth. Long term, Postgres may be appropriate if multiple contributors, public writes, or concurrent review workflows become important.

Recommended near-term tables:

- `libraries`
- `library_identifiers`
- `ingestion_runs`
- `photo_evidence`
- `model_predictions`
- `review_decisions`
- `book_editions`
- `book_observations`
- `inventory_snapshots`
- `duplicate_candidates`

CSN should remain stable even if database row IDs change. If CSN continues to mirror insertion order, document that as a domain rule and preserve it during migrations.

### Duplicate Detection

Keep charter-number matching as strong evidence, but replace automatic proximity-only merges with duplicate candidates. A candidate record should include:

- Distance between coordinates.
- Charter match or mismatch.
- Name similarity.
- Visual/icon similarity if available.
- Observation timestamps.
- Reviewer decision: same library, different library, unsure.

Automatic merge by proximity should be conservative and auditable.

### Search

Unify search semantics across backend, Android, and GitHub Pages. SQLite FTS5 or a generated static search index would be better than separate substring implementations.

Search should eventually support:

- Title, author, genre, ISBN, and approximate spelling.
- Distance ranking.
- Active-only inventory by default.
- Optional historical search for removed books.
- Data freshness indicators.

## Privacy and Safety

The project already avoids publishing original photos, which is the right default. Next steps:

- Keep original uploaded files out of Git and public Pages builds.
- Publish only derived 144x144 icons unless explicit consent exists.
- Add a regression test that `docs/atlas-data.json` never contains `data/uploads`, original filenames, or raw upload paths.
- Separate internal evidence coordinates from public display coordinates.
- Consider coordinate rounding, geohash cells, or official-address-only display for private residences.
- Keep `CIVITAS_SERVE_UPLOADS=1` as an explicit local/debug-only setting.

## ML and Human Review

Treat model output as uncertain evidence. Add review UI support for:

- Per-field confidence.
- "Not visible" and "model hallucinated" flags.
- Image crop or photo reference for each extracted book.
- "Needs second reviewer" state.
- Charter number confidence and source image.
- Reviewer corrections as reusable evaluation data.

Create a small gold dataset of labeled photos. Track:

- Visible-book detection precision and recall.
- Title exact match and fuzzy match.
- False hallucination rate.
- Charter extraction accuracy.
- GPS acceptance/rejection accuracy.
- Reviewer edit distance by field.

## Android App

Recommended Android improvements:

- Replace destructive SQLite upgrades with real migrations.
- Allow empty-shelf observations if the central model accepts empty libraries.
- Add unit tests for EXIF parsing, local save, search, payload creation, and sync failure states.
- Add MockWebServer tests for central upload behavior.
- Restrict cleartext traffic to debug builds.
- Review backup settings so local contribution data is not accidentally backed up or leaked.
- Enable release signing/minification when moving beyond prototype distribution.

## GitHub Pages Site

The public site should remain a read-only projection of approved central data. Improvements:

- Build from a generated read model rather than live operational tables.
- Validate exported JSON before deploy.
- Add a no-raw-upload privacy check before deploy.
- Add a browser smoke test that loads the static site, opens map popups, searches by book, searches by ZIP, and verifies no console errors.
- Continue showing library icons in popups, but avoid duplicating CSN text.
- Show data freshness and observation date so users understand that shelf contents can change.

## Testing and CI

Create a single CI gate before release or deploy:

- `python -m unittest discover -s tests`
- `node --check static/app.js`
- `node --check docs/app.js`
- Export validation against a fixture database.
- Privacy assertion that public exports contain no original upload paths.
- Android unit tests.
- Android lint.
- Android debug build.
- Playwright smoke tests for local app and GitHub Pages app.

Add targeted regression tests for:

- GPS-required ingestion.
- Empty shelf acceptance.
- Duplicate threshold boundaries.
- Charter-number matching.
- Removed-book history.
- Legacy database migration.
- Malformed multipart uploads.
- Oversized files.
- Renamed non-image files.
- Invalid EXIF.
- ZIP search and geolocation failures.

## Operations and Deployment

For local development, the current `ThreadingHTTPServer` is sufficient. For public contribution endpoints, use:

- WSGI/ASGI server.
- Reverse proxy with TLS.
- Request size limits.
- Rate limiting.
- Structured logs with request IDs.
- Health/status endpoints.
- Background job queue for map/icon/Page export.
- Regular database backups.

Exporting GitHub Pages should be an explicit job or queued task, not tightly coupled to every save request.

## Suggested Roadmap

### Phase 1: Stabilize Current Prototype

- Add CI gate for existing tests, JS syntax checks, Android build, and export validation.
- Add privacy tests for public exports.
- Add Android non-destructive migrations.
- Document contribution and privacy rules clearly.

### Phase 2: Introduce Observation-Centered Schema

- Add ingestion, photo evidence, model prediction, and review decision tables.
- Preserve current public behavior using derived views or export transforms.
- Add migration tests and fixture data.

### Phase 3: Improve Review and Data Quality

- Add review UI confidence fields and correction labels.
- Add data-quality dashboard.
- Add duplicate-candidate workflow.
- Build a small gold evaluation set.

### Phase 4: Prepare for Public Contributions

- Add contributor authentication.
- Add rate limits and reverse proxy deployment.
- Add public/private coordinate policy.
- Add background export jobs.

### Phase 5: Scale Search and Intelligence

- Add canonical search index.
- Add bibliographic metadata enrichment.
- Add active-learning style review prioritization.
- Add historical inventory browsing.

## Non-Goals Until Approved

Do not implement these changes without explicit instruction:

- Do not migrate the database schema.
- Do not replace SQLite or introduce Postgres.
- Do not change public coordinate precision.
- Do not alter current ingestion behavior beyond approved patches.
- Do not add authentication or deployment infrastructure.
- Do not change Android storage behavior.
- Do not push or release based on this document alone.
