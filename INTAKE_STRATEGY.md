# Intake Strategy

This note captures the design discussion about reducing token spend by preferring local, programmatic intake steps before OpenAI vision calls.

## Goal

Use local evidence first, then invoke AI only when it adds clear value. The main target is the browser intake flow, which had been the most token-hungry path because uploads were analyzed immediately.

## Problem Summary

- The browser capture flow uploaded photos and called `/api/analyze-photo` immediately.
- The backend then sent `saved_books or all_saved` to OpenAI before the contributor reviewed anything.
- This made first-pass AI the default for duplicates, obvious updates, empty shelves, and manual-review cases.

## Review Outcome

A software-engineer review judged the broader plan realistic only if it stays tightly scoped:

- Realistic:
  - make the browser intake flow behave more like the reviewed CLI and Android workflows
  - move low-cost routing decisions ahead of AI
  - keep AI available as an assist, not the default
- Not Phase 1:
  - local OCR for titles or charter plaques
  - image fingerprint caching
  - full workflow unification across browser, CLI, and Android
  - replacing AI title extraction with deterministic local extraction

## Lowest-Hanging Fruit

These were identified as the best cost-saving changes with minimal quality risk:

1. Create a local draft first instead of auto-running AI.
2. Run existing-library proximity and charter matching before AI.
3. Keep AI optional and explicit in the UI.
4. Reuse the saved upload set for optional AI enrichment instead of requiring a new upload pass.

## Phase 1 Scope

Phase 1 is intentionally limited to browser UX and routing changes only.

Included:

- `POST /api/photo-draft` for local-first draft creation
- explicit `Run AI extraction` follow-up action
- early duplicate/proximity hinting in the draft response
- preservation of saved upload paths so the draft remains reviewable and saveable without re-upload
- continued support for empty shelves and non-library box types

Excluded:

- OCR and local text extraction
- background enrichment
- cost telemetry
- image cache layers
- prompt redesign beyond what is needed to support the new flow

## Quality Guardrails

The local-first browser flow must keep these invariants:

- photo EXIF GPS remains mandatory for accepted photo evidence
- zero-book libraries remain valid
- `library`, `art_gallery`, and `free_pantry` continue to work in the same draft/save pipeline
- AI failure cannot block a valid manual save
- existing-library matching can guide review but must not silently force an update without normal save-time checks

## Phase 1 Implementation Shape

Browser UX:

- rename the first action from AI analysis to local draft creation
- show a draft review state immediately after GPS/photo processing
- show AI enrichment as an optional second step

Backend routing:

- keep legacy `/api/analyze-photo` compatibility
- add a local-first draft route for new uploads
- add a second route that enriches an already-saved draft from its saved upload paths
- keep save-time matching and inventory logic unchanged

## Why This Is the Right Cut

This phase reduces token consumption without betting project quality on new OCR or heuristic extraction work. It changes when AI is used, not what the atlas ultimately accepts. That makes it the safest place to start.
