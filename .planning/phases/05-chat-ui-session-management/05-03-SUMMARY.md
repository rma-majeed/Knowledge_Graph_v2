---
phase: 05-chat-ui-session-management
plan: 03
subsystem: ui
tags: [streamlit, citations, expander, confidence-badges, ux]

# Dependency graph
requires:
  - phase: 05-02-chat-app
    provides: app.py with answer_question() integration and session history
  - phase: 04-query-engine-answer-generation
    provides: answer_question() returning citations list with HIGH/LOW confidence
provides:
  - _render_citations() helper with st.expander and confidence badges
  - Empty-corpus info banner for first-run guidance
  - Updated sidebar with How-to-use instructions for non-technical consultants
  - Citations displayed in both history re-render and new-response block
affects:
  - human-verify checkpoint (browser smoke test)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_render_citations() helper decoupled from chat loop — called in both history re-render and new-response block"
    - "HIGH/LOW confidence badge pattern: HIGH bolded (**HIGH**), LOW plain text"
    - "Empty-corpus guard via Path.exists() check on data/chunks.db before chat history loop"

key-files:
  created: []
  modified:
    - app.py

key-decisions:
  - "Citations rendered in st.expander (collapsed by default) to keep UI clean — consultants can expand when needed"
  - "HIGH badge uses **bold** markdown for visual emphasis; LOW stays plain text to avoid false urgency"
  - "Empty-corpus guard uses st.info (not st.warning/st.error) — first run is expected, not an error condition"

patterns-established:
  - "Citation helper pattern: _render_citations(citations) accepts list[dict] and is a no-op if empty"
  - "How-to-use sidebar instructions prepended before divider/System Status so consultants see them first"

requirements-completed:
  - UI-01
  - UI-02

# Metrics
duration: 6min
completed: 2026-03-31
---

# Phase 5 Plan 03: Citations and Polish Summary

**Collapsible citation expanders with HIGH/LOW confidence badges wired into Streamlit chat history, plus empty-corpus guidance and non-technical sidebar instructions**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-03-31T05:27:16Z
- **Completed:** 2026-03-31T05:32:17Z
- **Tasks:** 2 (1 auto + 1 human checkpoint — all complete)
- **Files modified:** 1

## Accomplishments

- Added `_render_citations()` helper that renders a collapsible `st.expander` with HIGH/LOW confidence badges per citation
- Wired citations into both the chat history re-render loop and the new-response block (first render)
- Added empty-corpus `st.info` banner when `data/chunks.db` does not exist — no banner when file exists
- Updated sidebar with numbered How-to-use instructions for non-technical automotive consultants
- All 71 tests pass (31 passed, 40 xpassed) after changes

## Task Commits

1. **Task 1: Add _render_citations() helper and wire into chat history loop** - `e4f42e5` (feat)
2. **Task 2: Human visual smoke test** - APPROVED by user (all 6 visual checks passed)

## Files Created/Modified

- `app.py` — Added `_render_citations()` helper (lines 96-113), updated history loop (lines 168-172), wired citations to new-response block (line 204), added empty-corpus guard (lines 152-159), updated sidebar How-to-use instructions (lines 124-130)

## Decisions Made

- Citations rendered in `st.expander` collapsed by default — consultants expand only when they want to verify sources
- `HIGH` badge uses `**bold**` markdown; `LOW` stays plain text — asymmetric emphasis reflects confidence asymmetry
- Empty-corpus guard uses `st.info` (blue, neutral tone) not `st.warning/st.error` — first run is an expected state

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Visual Smoke Test Results (Task 2 Human Checkpoint)

**Status: APPROVED** — User confirmed all 6 checks passed on 2026-03-31.

| Check | Description | Result |
|-------|-------------|--------|
| 1 | Page loads — title and chat input visible | PASS |
| 2 | Sidebar How-to-use instructions + System Status visible | PASS |
| 3 | Empty-corpus blue info banner (or no banner when db exists) | PASS |
| 4 | Question submission: spinner, answer, Sources expander, HIGH/LOW badges | PASS |
| 5 | Chat history: both Q&A pairs visible on second question | PASS |
| 6 | Error handling: plain-English message, no Python traceback | PASS |

## Next Phase Readiness

Phase 5 is fully complete. All 5 phases of the Automotive Consulting GraphRAG Agent v1.0 are done.

---
*Phase: 05-chat-ui-session-management*
*Completed: 2026-03-31*
