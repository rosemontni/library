# Lessons Learned

This file is a living operational log for Civitas Library work. Its job is simple:

- record every confirmed mistake or tool/process failure encountered during intake, publishing, and site maintenance
- pair each case with an immediate recovery step and a prevention step
- make the next pass safer for both the human maintainer and the coding agent

If a future mistake or failure happens, add it here instead of relying on chat memory.

## Current Lessons

### 1. Processed libraries were left out of a central-database publish

What happened:

- I reported a publish as complete even though several already-processed pending libraries were still sitting in the local intake queue and had not been imported into the central atlas.

Why it matters:

- the public counts were wrong
- the atlas looked complete when it was not
- it created avoidable cleanup work and reduced trust in the release status

Recovery step:

- reconcile the pending intake queue against the central atlas and import every intended record before the next publish

Prevention step:

- before saying "publish complete," always run a three-way reconciliation:
- check pending intake files under `data/uploads`
- check the central atlas/exported snapshot
- confirm that any remaining pending items are intentionally deferred

### 2. Remote publishing left the local checkout out of sync

What happened:

- a publish succeeded through a GitHub/API fallback path, but the local checkout was not immediately brought back into sync with the published remote state

Why it matters:

- later work can be evaluated against stale local assumptions
- new intake decisions become harder to trust
- troubleshooting becomes slower because local and remote no longer describe the same project state

Recovery step:

- after any out-of-band publish, fetch and reconcile the local checkout before continuing regular intake work

Prevention step:

- treat "remote published, local not synced" as an unstable state
- do not continue normal batch processing until local and remote state are explicitly compared and aligned

### 3. Temp-photo EXIF reads failed inside the sandbox

What happened:

- attempts to read GPS EXIF from uploaded temp photos failed with `CreateProcessAsUserW failed: 5`

Why it matters:

- GPS validation is a hard intake requirement
- a failed read can look like a missing-photo problem when it is really an access problem

Recovery step:

- rerun the EXIF read with elevated access against the temp-photo path

Prevention step:

- treat EXIF reads from `%TEMP%` or any non-workspace upload path as likely to require elevated access from the start

### 4. Ad hoc Pillow EXIF parsing failed on phone-photo metadata

What happened:

- a quick Python EXIF parser failed with `AttributeError: 'int' object has no attribute 'items'`

Why it matters:

- custom parsing paths are brittle
- a bad fallback wastes time during batch review

Recovery step:

- switch to `exiftool` for authoritative GPS extraction

Prevention step:

- prefer `exiftool` over hand-rolled EXIF parsing for intake validation
- if Python fallback is needed, test it against real phone JPEGs and multiple GPSInfo representations first

### 5. The first exiftool path I tried was wrong

What happened:

- I assumed `exiftool.exe` lived under the Windows Apps shim path, but it was actually installed at `C:\Users\xliup\bin\exiftool.exe`

Why it matters:

- a correct tool can still look missing if the path is guessed instead of discovered

Recovery step:

- use `where.exe exiftool` and then call the discovered executable path

Prevention step:

- do not hard-code utility paths when a system lookup command can confirm the real location first

### 6. Shell commands ran from the wrong directory

What happened:

- some path-sensitive shell reads ran from `C:\Users\xliup` instead of the repository, which produced misleading output and missing-file errors

Why it matters:

- a command can succeed while answering the wrong question
- missing files can be misdiagnosed as repo issues instead of cwd issues

Recovery step:

- rerun the command with an explicit repo path or explicit `Set-Location -LiteralPath`

Prevention step:

- for path-sensitive commands, do not rely on ambient cwd
- use absolute paths or include `Set-Location -LiteralPath 'C:\Users\xliup\OneDrive\Documents\codex\book'` in the command itself

### 7. Parallel shell calls made cwd assumptions less reliable

What happened:

- a parallelized shell step increased the chance of trusting `workdir` behavior that did not hold consistently for the failing command path

Why it matters:

- parallelism is good for speed, but bad path assumptions can quietly poison validation work

Recovery step:

- rerun path-sensitive verification steps sequentially with explicit paths

Prevention step:

- use parallel calls for independent reads only when cwd does not matter
- for atlas verification, prefer explicit paths over speed

### 8. The local SQLite atlas inspection returned impossible results

What happened:

- `sqlite3` queries against `data/little_library_atlas.db` reported no tables or schema even though the file existed and had a valid SQLite header

Why it matters:

- a single unreliable database probe can lead to a wrong "new vs update" classification

Recovery step:

- cross-check with other sources before trusting the result:
- `docs/atlas-data.json`
- staged pending intake JSON files
- app constants and app-level database helpers

Prevention step:

- if a database answer contradicts known project state, stop and verify with a second source before using it in a user-facing conclusion

### 9. I assumed `static/atlas-data.json` existed

What happened:

- I searched both `docs/atlas-data.json` and `static/atlas-data.json`, but only the `docs` export existed in this checkout

Why it matters:

- guessed paths create noisy false failures and slow down verification

Recovery step:

- search the real exported artifact that exists in the repo

Prevention step:

- verify artifact locations before using them in commands
- prefer project constants or a file listing over assumptions about mirrored paths

### 10. A broad Windows `rg` invocation used a bad target pattern

What happened:

- a search command included `*.md` as a literal path target in a way that PowerShell/Windows did not accept for that call shape

Why it matters:

- an otherwise useful search can fail for shell-syntax reasons instead of data reasons

Recovery step:

- rerun the search with explicit files or with `rg --glob`

Prevention step:

- avoid shell-glob assumptions in PowerShell command strings
- use explicit target lists when accuracy matters more than convenience

### 11. Book-title extraction can drift into guessing when visibility is poor

What happened:

- some intake batches contained partial spines, glare, or cut-off titles that invited a best guess instead of a certainty flag

Why it matters:

- guessed titles pollute the atlas more than omitted uncertain titles

Recovery step:

- keep only the high-confidence titles and mark the rest as partially obscured

Prevention step:

- exact title if clearly visible
- partial title if strongly readable but incomplete
- omit the entry if confidence is low

### 12. Interrupted work needs explicit resume breadcrumbs

What happened:

- rate limits and tool interruptions forced work to resume later from a partially completed state

Why it matters:

- resumptions are where duplicate imports, missed items, and incorrect completion claims often happen

Recovery step:

- record the last known publish point, pending items, and local-versus-remote state before resuming

Prevention step:

- when interrupted, leave a resumable summary that includes:
- published commit or deployment run if one exists
- remaining pending items
- whether the local checkout matches the published state

### 13. Some local verification commands ignored the intended repo working directory

What happened:

- a frontend syntax check and a Python test command were launched with the repo set as `workdir`, but the process still resolved paths from `C:\Users\xliup`

Why it matters:

- a valid check can fail against the wrong path
- time gets wasted debugging nonexistent code issues

Recovery step:

- rerun the command with an explicit `Set-Location -LiteralPath 'C:\Users\xliup\OneDrive\Documents\codex\book'` in the command itself

Prevention step:

- for path-sensitive verification commands in this environment, prefer explicit `Set-Location` over trusting `workdir` alone

### 14. `python -m unittest discover -s tests` was unreliable in this environment

What happened:

- test discovery failed with `TypeError: expected str, bytes or os.PathLike object, not NoneType` before it even reached the repo tests

Why it matters:

- a discovery-layer failure can look like a test regression when the application code is fine

Recovery step:

- run the targeted module directly with `python -m unittest tests.test_app`

Prevention step:

- if discovery fails for environmental reasons, switch to module-targeted unittest invocation for local verification and keep the failing discovery mode documented instead of repeatedly rediscovering it

### 15. Photo intake encountered conflicted exports and an incorrect verification key

During IMG_8481 intake on 2026-10-04, the existing public JSON contained merge markers, so JSON parsing failed. The reviewed intake verification also initially expected `library_id` at the top level of search results; the API returns `library.id` instead. The import itself had succeeded.

Recovery: backed up the database and generated artifacts under the private intake directory, regenerated the export from SQLite, corrected the verification key, and reran the idempotent import check. Existing website source conflicts still require resolution before publication.

Prevention: inspect repository conflict status before parsing generated files, use the actual search response schema, and check the stored photo path before retrying an import after a verification failure.

### 16. Merge review exposed pantry export and AI fallback regressions

The interrupted rebase retained pantry support in the app but omitted it from the JSON and SVG generators. Failed AI enrichment also reset manually selected non-library box types. Review fixed both and added regression coverage, including capture dates in public exports and invalid calendar-date rejection.

On Windows, the new SQLite export test initially left connections awaiting garbage collection, preventing temporary-directory cleanup. Follow the existing tests' explicit garbage-collection pattern. Generated exports now use LF line endings to avoid spurious whitespace failures. Git operations requiring elevated access must use an explicit repository path because the elevated process can start elsewhere.

### 17. Reflections require a second title review

During the September 1 book-swap photo intake, a detail crop corrected three initial spine readings before publication, including The Unequal Burden of Cancer and the 2011 Federal Manager's Guide. Update both the reviewed metadata and database search text when correcting an imported title. An apostrophe also caused a syntax error in the private intake script before any database write; use matching quote styles and validate scripts before execution.

## Standing Checklist

Use this checklist before any future "all clear" statement.

### Before classifying a photo batch

- confirm GPS EXIF exists on every accepted photo
- identify surroundings versus contents photos
- extract or explicitly fail to extract the charter number
- compare charter and GPS against pending intake records
- compare charter and GPS against the published atlas or the verified central source
- keep only high-confidence book titles

### Before saying a publish is complete

- confirm the intended intake files were actually imported
- confirm no unplanned pending libraries remain in `data/uploads`
- regenerate the public export
- run the release checks
- verify the deployment run
- reconcile local and remote state if a fallback publish path was used
