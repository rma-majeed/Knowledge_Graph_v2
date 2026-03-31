# Phase 5: Chat UI & Session Management — Validation

**Phase:** 05-chat-ui-session-management
**Requirements covered:** UI-01, UI-02
**Plans:** 05-01 (Wave 1), 05-02 (Wave 2), 05-03 (Wave 3)

---

## Automated Validation

### Quick run (excludes LM Studio integration tests)

```bash
cd "C:/Users/2171176/Documents/Python/Knowledge_Graph_v2"
pytest tests/test_chat_app.py -x -q -k "not lm_studio"
```

Expected: 4 tests passing (xfail stubs from plan 05-01 become passing after plans 05-02 and 05-03).

### Full suite (all phases, no LM Studio)

```bash
cd "C:/Users/2171176/Documents/Python/Knowledge_Graph_v2"
pytest tests/ -x -q -k "not lm_studio" --tb=short
```

Expected: All tests passing. Phase 5 adds tests/test_chat_app.py to the suite; all prior phase tests remain green.

### Syntax and import check

```bash
cd "C:/Users/2171176/Documents/Python/Knowledge_Graph_v2"
python -c "
import ast
ast.parse(open('app.py').read())
print('app.py syntax OK')
"
```

Expected: prints "app.py syntax OK" and exits 0.

---

## Manual Validation (browser smoke test)

Run from project root:

```bash
streamlit run app.py
```

A browser tab should open automatically at http://localhost:8501.

### Checklist

| # | Check | How to Verify | Pass |
|---|-------|---------------|------|
| 1 | Page loads | Title "Automotive Consulting Assistant" visible; chat input at bottom | [ ] |
| 2 | Sidebar instructions | "How to use" steps 1-3 visible; LM Studio status shown | [ ] |
| 3 | Empty corpus guidance | If data/chunks.db absent: blue info banner with ingest instructions; no crash | [ ] |
| 4 | Question submission | Type question, press Enter; spinner appears; answer shown in chat bubble | [ ] |
| 5 | Citations expander | "Sources (N cited)" expander below answer; clicking shows filename, page, HIGH/LOW | [ ] |
| 6 | Session history | Submit second question; both Q&A pairs visible; first exchange still readable on scroll | [ ] |
| 7 | Error handling | Stop LM Studio, submit question; plain-English error shown; no Python traceback in browser | [ ] |

All 7 checks must pass before Phase 5 is marked complete.

---

## Requirements Traceability

| Requirement | Success Criterion | Validated By |
|-------------|-------------------|--------------|
| UI-01 | Consultant accesses system via browser at simple URL (no CLI) | Manual check #1: page loads at localhost:8501 |
| UI-01 | Consultant types question, sees synthesized answer with citations | Manual checks #4, #5: submission + expander |
| UI-01 | User-friendly error messages; no stack traces | Manual check #7: error handling |
| UI-02 | Chat history shows all previous Q&A pairs; user can scroll back | Manual check #6: session history |

---

## Phase Completion Gate

Phase 5 is complete when:

- [ ] `pytest tests/ -x -q -k "not lm_studio"` exits 0 (all 4 chat app tests passing)
- [ ] All 7 browser smoke test checks pass
- [ ] ROADMAP.md Phase 5 entry updated to "Complete"
- [ ] UI-01 and UI-02 marked `[x]` in REQUIREMENTS.md
