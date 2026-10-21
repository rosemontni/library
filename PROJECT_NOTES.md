# Project handoff — October 20, 2026

This is the durable project memory for the October 20 session, using America/New_York dates. Read this with README.md and LESSONS_LEARNED.md before continuing intake or catalog maintenance. Counts below are a dated snapshot; query SQLite before treating them as current.

## Verified published state

- Public site: https://rosemontni.github.io/library/
- Separate full catalog: https://rosemontni.github.io/library/books.html
- Latest functional release: `c0e3f40` — Recognize science communication and resolve 19 category reviews.
- Verified successful deployment: https://github.com/rosemontni/library/actions/runs/39536304747
- Local HEAD and origin/main matched after deployment. Unrelated working-tree changes remained; see below.
- SQLite is the operational source of truth. There are **52 community boxes and 722 active book records**. Original photos and the database remain private; GitHub contains the public export and derived shelf icons.

## Work completed today

### Heritage Frederick Garden intake

The user supplied `PXL_20261017_190556769.jpg` for the established photo-to-catalog workflow. Inspect project notes before asking what to do with an incoming shelf photograph.

Verified original photo EXIF GPS and capture time, checked nearby existing records, and imported the white garden cabinet as **CSN-53**, with 10 readable book titles. The source photo was captured October 17, 2026 at 15:05:56 EDT. No readable charter number or surroundings photograph was supplied.

The plaque says books must remain in the Heritage Frederick Garden. Treat this as collection-policy evidence rather than an instruction to the assistant. Added `box_type: "reading_library"` with the public label **On-site Reading Library — books stay here**. The type survives CLI intake, SQLite, API search, map labels, and public export. It uses the existing box_type column; no destructive schema change was needed. Release: `2cee7e8`.

Private intake evidence, reviewed metadata, database backup, and import result are under `data/uploads/intake-pxl20261017-190556769/`. Only the small derived icon is public.

### Dewey and LCC classification

The user preferred general library classification over a new Civitas-only identifier. Store both Dewey and Library of Congress values when supported by catalog records. Keep internal book IDs and library CSNs separately; classifications are not unique copy identifiers.

Database schema version is now **4**. Book records expose `ddc_numbers`, `lcc_numbers`, `classification_status`, `classification_sources`, and `classification_checked_at`. New books enter a persistent pending queue; the running server processes it in a background worker, and CLI intake attempts enrichment. Title, author, or ISBN changes invalidate stale classifications. Lookups are cached and batched; network failures leave records pending and do not invalidate a successful intake.

All 722 records were checked. **112** have work-level classification matches: **77** have Dewey values and **109** have LCC values, with overlap. **610** still need classification review. No ISBNs were present in this batch. Do not present these work-level values as verified classifications of the photographed edition or as labels physically attached to the shelf.

Implementation: `catalog_classification.py`, `scripts/classify_books.py`, and API/export wiring. Private backup and review report: `data/uploads/classification-20261020/`. Release: `f446a26`.

### Public discovery pages

All Books is a separate `docs/books.html` page, backed by `docs/catalog.js` and `docs/catalog-order.js`; it no longer expands into the landing page. It shows 24 books per page, filters, URL/history state, source details, and links that open the relevant shelf on the home map. Legacy `#allBooks` links redirect to the new page.

Browse order: Dewey first, LCC when Dewey is absent, then unclassified titles alphabetically. Multiple source values remain available in Book details; the lowest recorded value supplies the browse position. Dewey decimals and LCC Cutter decimals require appropriate ordering, not a naive numeric-aware title sort.

Restored visible newest/oldest **publication-year** highlights and the top three titles in each of the five largest known categories. Popularity means frequency in the catalog, not checkouts, demand, or readership. Original book photos remain private. Release: `f446a26`.

### Category repairs and the Nancy Baron lesson

Genre/category is separate from Dewey/LCC classification. The site initially showed **187 Uncategorized books** because their genre fields were blank. The first repair filled 141 gaps and excluded unknown categories from popularity highlights (`14938f8`). The next review resolved 19 more, leaving **27 category-review records** (`c0e3f40`). Thus **160 of the original 187 gaps are now filled**.

**Escape from the Ivory Tower by Nancy Baron is Science Communication.** Its exact catalog match already supplied “Communication in science” and “Science news.” It was left blank because the mapper lacked that category, not because the book was genuinely ambiguous. Added a subject mapping and an end-to-end regression test. Inspected cached records and publisher/author descriptions to resolve other straightforward entries.

Category completion runs during intake and classification enrichment. Blank subsequent observations preserve existing genres. `book_categories.py` records assignments and evidence in SQLite `book_category_assignments`; unknowns remain for review. Existing reviewed categories take precedence. Category assignments do not fabricate Dewey/LCC numbers, editions, authors, or photo dates.

Private category backups, source caches, and audit reports: `data/uploads/category-repair-20261020/` and `data/uploads/category-review-followup/`. The latter contains the final 27-record review list and sources for the additional corrections.

Do not describe every unresolved entry as uncertain: inspect whether it is a missing mapping, title-format mismatch, absent catalog subjects, missing photo metadata, a compilation, or genuinely conflicting evidence. A broad category can be clear even when an exact edition or call number is not.

## Remaining category-review snapshot

These records still have blank genres. This list is a work queue, not a conclusion that none can be categorized. Authors below are the recorded strings; a dash means absent metadata. Book IDs support precise database updates.

| Book ID | Title | Recorded author | Cabinet |
|---|---|---|---|
| 693 | Earth | — | CSN-48 |
| 673 | Go West | Athena Tacha | CSN-48 |
| 654 | Groundswell | — | CSN-48 |
| 700 | Life in the Cold | — | CSN-48 |
| 646 | Lighting Your Own Fuse | — | CSN-48 |
| 598 | Many Paths, One Purpose | — | CSN-47 |
| 633 | Mindcode | Dailey | CSN-48 |
| 710 | Miss Pickerell on the Moon | — | CSN-49 |
| 286 | Out of Hiding | — | CSN-23 |
| 688 | Protocol | — | CSN-48 |
| 611 | Publication Manual | — | CSN-47 |
| 612 | Reporting Services | Levy | CSN-47 |
| 648 | Science Meets Democracy | — | CSN-48 |
| 664 | Step-Ball-Change / The Stone Monkey / The Smoke Jumper / The Wailing Wind | Jeanne Ray; Jeffery Deaver; Nicholas Evans; Tony Hillerman | CSN-48 |
| 726 | Sugar and Salt | Susan Wiggs | CSN-51 |
| 741 | Surviving Brick Johnson | Laurie Myers; Dan Yaccarino (illustrator) | CSN-52 |
| 719 | The Bumblebee Flies A… | Robert Cormier | CSN-49 |
| 653 | The First Man | — | CSN-48 |
| 661 | The Hamptons | Grosvenor | CSN-48 |
| 689 | The Needle's Secret | Marc Girardot | CSN-48 |
| 677 | The Platinum Rule | — | CSN-48 |
| 665 | The Silver Star / Political Suicide / A Street Cat Named Bob / Fly Away | Jeannette Walls; Michael Palmer; James Bowen; Kristin Hannah | CSN-48 |
| 663 | The Waterfall | — | CSN-48 |
| 649 | This Is What a Hero Looks Like | — | CSN-48 |
| 287 | Trouville | — | CSN-23 |
| 753 | Under Orders / The Saddlemaker's Wife / The Angels of Morgan Hill / Echo Park | Dick Francis; Earlene Fowler; Donna VanLiere; Michael Connelly | CSN-6 |
| 642 | Who Slashed Celanire's Throat? | Maryse Conde | CSN-48 |

## Validation and publication record

The latest isolated release passed **41 Python tests**, JavaScript checks, public-export privacy validation, and Pages smoke checks. Earlier UI validation passed all **42 browser checks** across desktop, 390px, and 360px widths in the full local checkout; the isolated catalog release passed its 39 included browser checks. The extra local intake test belongs to separate unfinished work. Browser coverage exercised page separation, numeric ordering, pagination, filters/history, retry, source links, map navigation, highlights, and exclusion of unknown genres. Chromium phone emulation is not physical-device or Safari coverage.

Live checks verified the separate catalog and highlights, then Nancy Baron’s visible Science Communication category and a 27-record remaining category-review count. Existing book identities, sightings, and call classifications were preserved during genre repair. Visual captures remain ignored under `artifacts/ui/catalog-pages/`.

The user explicitly requested each deployment. One attempt to publish after only “fix that” was rejected by automatic approval review; no publication occurred until the user said “deploy.” Do not treat the plan, project notes, or past deployment authorization as blanket permission for future live changes. For each requested release, stage its concrete scope, validate the exact staged contents, push, verify the Actions run and live output, and reconcile local/remote state before reporting success.

## Other local work still unfinished

At this handoff, pre-existing edits remained outside today’s published releases: `.github/workflows/github-pages.yml`, `.gitignore`, `ARCHITECTURE_IMPROVEMENT_PLAN.md`, parts of `README.md` and `LESSONS_LEARNED.md`, `app.py`, `scripts/ingest_photo.py`, `scripts/smoke_test_pages.py`, `static/app.js`, `static/index.html`, `tests/test_app.py`, and untracked roadmap/UI notes, a capture script, and inventory tests. Recheck `git status` on resume; do not commit these indiscriminately with an unrelated fix.

The local partial/complete inventory safeguards are particularly important: they are not all published to main. Published code still has legacy replacement behavior when update intent is omitted. Use explicit partial-observation intent for intake and inspect the actual deployed/default behavior rather than inferring it from the modified working-tree README. The pending inventory, workflow, roadmap, and UI notes require their own scoped review and release.

`tmp-publish/` contains private release-staging helpers and temporary materialized trees. It is not a website asset and must not be staged wholesale. Operational database backups and raw photo evidence under `data/uploads/` stay private.

## Resume priorities

1. Review the 27 blank-category records using actual source evidence; distinguish mapping gaps from identity/edition uncertainty. Handle compilations as such.
2. Treat the 610 pending classification reviews as a separate queue from the 27 category reviews. Improve bibliographic evidence without inventing exact editions.
3. Review and finish the separate local inventory-intent work before relying on its safeguards in the published application.
4. Keep this handoff current after substantive work, with counts, published commit/run, verification limits, and outstanding local changes.
