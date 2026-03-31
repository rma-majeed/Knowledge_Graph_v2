---
phase: 05-chat-ui-session-management
plan: "01"
subsystem: test-infrastructure
tags:
  - tdd
  - xfail
  - streamlit
  - app-stub
dependency_graph:
  requires: []
  provides:
    - app.py stub (NotImplementedError placeholder)
    - tests/test_chat_app.py (4 xfail stubs for UI-01, UI-02)
  affects:
    - tests/test_chat_app.py (stubs become passing after 05-02 and 05-03)
tech_stack:
  added: []
  patterns:
    - xfail(strict=False) stub pattern (established in Phases 2-4)
    - AppTest.from_file pattern for Streamlit unit tests
    - sys.path guard for project root resolution
key_files:
  created:
    - app.py
    - tests/test_chat_app.py
  modified: []
decisions:
  - xfail(strict=False) stubs for test scaffold — keeps test intent visible; stubs auto-pass once implementation lands
metrics:
  duration_minutes: 10
  completed_date: "2026-03-31"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 0
---

# Phase 5 Plan 01: Test Infrastructure Summary

**One-liner:** xfail test scaffold with 4 Streamlit AppTest stubs (UI-01, UI-02) and NotImplementedError app.py placeholder for Wave 1 TDD pattern.

---

## What Was Built

Wave 1 test scaffold for Phase 5 Chat UI & Session Management, following the exact xfail-stub pattern established in Phases 2-4.

### app.py (project root)
Minimal stub that:
- Includes the sys.path guard (`_PROJECT_ROOT` injection) so `from src.query.pipeline import answer_question` resolves when `streamlit run app.py` executes from project root
- Raises `NotImplementedError` when run — all AppTest calls fail predictably until plan 05-02 replaces this file
- Can be constructed with `AppTest.from_file("app.py")` without ImportError

### tests/test_chat_app.py
4 xfail stubs covering:
1. `test_app_renders_empty_chat` — UI-01: empty state on first load
2. `test_chat_input_triggers_response` — UI-01: question submission triggers answer_question()
3. `test_chat_history_persists` — UI-02: session state retains multiple messages
4. `test_lm_studio_error_shows_friendly_message` — UI-01: error handling without stack trace exposure

---

## Verification Results

```
pytest tests/test_chat_app.py -x -q -k "not lm_studio"
  1 deselected, 3 xfailed  (no errors, no import failures)

app.py parses OK

pytest tests/ -x -q -k "not lm_studio"
  31 passed, 3 deselected, 3 xfailed, 37 xpassed
```

All success criteria met:
- 4 stubs collected without import errors or collection errors
- `lm_studio` marker filters cleanly (no PytestUnknownMarkWarning — marker registered in conftest.py)
- app.py syntactically valid with sys.path guard
- Full prior test suite (phases 1-4) still green

---

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1: app.py stub | cacb1e1 | feat(05-01): add app.py stub with sys.path guard and NotImplementedError |
| Task 2: xfail test stubs | 436c91a | test(05-01): add xfail stubs for UI-01 and UI-02 chat app tests |

---

## Deviations from Plan

None — plan executed exactly as written.

---

## Known Stubs

| File | Stub | Reason |
|------|------|--------|
| app.py | `raise NotImplementedError` | Intentional Wave 1 placeholder — plan 05-02 implements the real Streamlit app |
| tests/test_chat_app.py | 4x `raise NotImplementedError` | Intentional xfail stubs — become passing after plans 05-02 and 05-03 |

These stubs are intentional Wave 1 scaffolding, not incomplete work. They are tracked here for the verifier.

## Self-Check: PASSED
