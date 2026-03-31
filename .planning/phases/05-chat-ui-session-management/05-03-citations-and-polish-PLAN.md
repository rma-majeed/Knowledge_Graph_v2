---
phase: 05-chat-ui-session-management
plan: 03
type: execute
wave: 3
depends_on:
  - 05-02-chat-app-PLAN.md
files_modified:
  - app.py
autonomous: false
requirements:
  - UI-01
  - UI-02

must_haves:
  truths:
    - "Citations are rendered in a collapsible st.expander below each assistant answer"
    - "HIGH confidence citations are visually distinguished from LOW confidence (bold or badge)"
    - "Empty corpus (no documents indexed) shows a helpful guidance message, not an error"
    - "Consultant can open browser at localhost:8501 and use the interface without technical knowledge"
    - "No Python traceback appears in the browser under any error condition"
  artifacts:
    - path: "app.py"
      provides: "_render_citations() helper + polished UI with expander, page title, empty-corpus guard"
      min_lines: 100
  key_links:
    - from: "app.py _render_citations()"
      to: "st.session_state.messages[]['citations']"
      via: "called in for-loop over session state and after new response"
      pattern: "_render_citations"
    - from: "app.py for-loop"
      to: "_render_citations()"
      via: "msg.get('citations') passed to _render_citations on history re-render"
      pattern: "msg.get.*citations"
---

<objective>
Add citation display polish and UX finishing touches to app.py, then perform a human visual smoke test.

Purpose: Deliver the full success criteria for Phase 5 — formatted citations (success criterion 4), graceful empty-corpus message (success criterion 5), and overall non-technical-user readiness. This plan runs last because it modifies the working app.py produced by plan 05-02.

Output: Updated app.py with _render_citations() helper using st.expander, confidence badges, empty-corpus detection, and polished sidebar instructions. Human checkpoint confirms visual correctness in browser.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/05-chat-ui-session-management/05-RESEARCH.md
@.planning/phases/05-chat-ui-session-management/05-02-SUMMARY.md

<interfaces>
<!-- Citations dict shape from answer_question() return value -->
# citations list items:
{
    "index": int,          # citation reference number [1], [2], ...
    "filename": str,       # source document filename (e.g. "Toyota_EV_Strategy_2023.pdf")
    "page_num": int,       # page or slide number
    "confidence": "HIGH" | "LOW",
    "source": str,         # "vector" | "graph"
    "count": int,          # number of chunks from this source
}

<!-- Session state message schema (from plan 05-02) -->
{
    "role": "user" | "assistant",
    "content": str,
    "citations": list[dict],   # populated for assistant messages
    "elapsed_s": float,
}

<!-- st.expander — Streamlit 1.47.0 -->
with st.expander("Sources (3 cited)", expanded=False):
    st.markdown("content here")

<!-- Confidence badge rendering pattern -->
# HIGH: bold + checkmark — draws attention to reliable sources
# LOW: plain text — visible but not emphasized
if c["confidence"] == "HIGH":
    badge = "**HIGH**"
else:
    badge = "LOW"
st.markdown(f"**[{c['index']}]** {c['filename']} — p.{c['page_num']} &nbsp; {badge}")
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add _render_citations() helper and wire into chat history loop</name>
  <files>app.py</files>

  <read_first>
    - app.py (full file — understand current structure before modifying)
  </read_first>

  <action>
Read app.py in full first. Then make the following targeted additions:

1. Add `_render_citations()` helper function after `_friendly_error()` (before the sidebar block):

```python
def _render_citations(citations: list[dict]) -> None:
    """Render citations in a collapsible expander with confidence badges.

    HIGH confidence citations (bolded) indicate the source was cited 3+ times
    across retrieved chunks — stronger evidence. LOW confidence appears 1-2 times.
    """
    if not citations:
        return
    with st.expander(f"Sources ({len(citations)} cited)", expanded=False):
        for c in citations:
            if c.get("confidence") == "HIGH":
                badge = "**HIGH**"
            else:
                badge = "LOW"
            st.markdown(
                f"**[{c['index']}]** {c['filename']} "
                f"— p.{c['page_num']} &nbsp; {badge}"
            )
```

2. Update the chat history for-loop (where existing messages are re-rendered on each rerun) to call `_render_citations()` for assistant messages:

```python
# BEFORE (existing loop):
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# AFTER (updated loop):
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            _render_citations(msg.get("citations", []))
```

3. Add `_render_citations(citations)` call immediately after `st.markdown(answer_text)` in the new-response block (so citations appear on first render, not just on reruns):

```python
st.markdown(answer_text)
_render_citations(citations)   # <-- add this line
st.session_state.messages.append(...)
```

4. Add an empty-corpus guard after the page title / caption, before the chat history loop. This checks whether chunks.db exists and has data, and shows a setup hint if not:

```python
_db_path = Path(_DEFAULT_DB)
if not _db_path.exists():
    st.info(
        "No documents indexed yet. Run the ingestion pipeline first: "
        "`python src/main.py ingest --path <your_documents_folder>`"
    )
```

Do NOT add the info banner if the file exists — it is only for first-time setup. Do NOT use st.warning or st.error for this case; st.info is the correct tone (it is expected on first run).

5. In the sidebar, update the header/instructions to be more descriptive for non-technical users:

```python
with st.sidebar:
    st.header("Automotive Consulting Assistant")
    st.markdown(
        "Ask questions about past consulting engagements. "
        "The system searches 15+ years of project knowledge."
    )
    st.markdown(
        "**How to use:**\n"
        "1. Type your question in the chat box below\n"
        "2. Press Enter to submit\n"
        "3. Click 'Sources' under any answer to see cited documents"
    )
    st.divider()
    # ... rest of sidebar unchanged
```

Preserve all existing sidebar content (System Status, Advanced Settings, LM Studio warning). Only prepend the How-to-use instructions.
  </action>

  <verify>
    <automated>cd "C:/Users/2171176/Documents/Python/Knowledge_Graph_v2" && python -c "import ast; ast.parse(open('app.py').read()); print('app.py syntax OK')" && python -m pytest tests/test_chat_app.py -x -q -k "not lm_studio" 2>&1 | tail -8</automated>
  </verify>

  <done>
- app.py parses without syntax error
- _render_citations() function defined and called in both the history loop and the new-response block
- Empty-corpus info banner present (conditional on db file not existing)
- All 4 test_chat_app.py tests still passing
- Full prior test suite still green
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-built>
    Complete Phase 5 Streamlit chat interface with:
    - Browser chat UI accessible at localhost:8501
    - Session history (all Q&A pairs preserved on scroll)
    - Citations in collapsible expander with HIGH/LOW confidence badges
    - LM Studio status in sidebar
    - User-friendly error handling (no tracebacks)
    - Empty-corpus setup guidance for first run
  </what-built>
  <how-to-verify>
    Run from the project root:

    ```
    streamlit run app.py
    ```

    A browser tab should open at http://localhost:8501. Verify the following:

    1. PAGE LOADS: Title "Automotive Consulting Assistant" visible; chat input box present at bottom of page.

    2. SIDEBAR: "How to use" instructions visible; System Status section shows either "LM Studio: connected" (green) or the warning about LM Studio not running.

    3. EMPTY CORPUS (if data/chunks.db does not exist): Blue info banner appears suggesting the ingest step. No error or crash.

    4. QUESTION SUBMISSION (requires LM Studio running with models loaded):
       - Type a question, press Enter
       - "Thinking..." spinner appears with elapsed-time counter
       - Answer text appears in the assistant chat bubble
       - "Sources (N cited)" expander appears below the answer
       - Clicking the expander shows filename, page number, and HIGH/LOW badge for each citation

    5. CHAT HISTORY: Submit a second question. Both Q&A pairs are visible; scrolling up shows the first exchange.

    6. ERROR HANDLING: Stop LM Studio (or use a model name that doesn't exist), submit a question. Verify: a plain-English error message appears (no Python traceback, no "Exception", no "Traceback (most recent call last)").
  </how-to-verify>
  <resume-signal>Type "approved" if all 6 checks pass, or describe any issues found.</resume-signal>
</task>

</tasks>

<verification>
```bash
cd "C:/Users/2171176/Documents/Python/Knowledge_Graph_v2"

# Automated: syntax + unit tests
python -c "import ast; ast.parse(open('app.py').read()); print('app.py syntax OK')"
python -m pytest tests/test_chat_app.py -x -q -k "not lm_studio"

# Full suite
python -m pytest tests/ -x -q -k "not lm_studio" --tb=short 2>&1 | tail -5

# Manual (browser smoke test):
# streamlit run app.py
```
</verification>

<success_criteria>
- _render_citations() renders HIGH citations as bolded badge, LOW as plain text
- Citations expander appears under each assistant response on first render and on rerun (history loop)
- Empty-corpus info banner appears when data/chunks.db does not exist, no banner when it does
- Human checkpoint: all 6 visual checks pass in browser
- No Python traceback visible in browser under any error scenario
- Phase 5 requirements UI-01 and UI-02 fully satisfied
</success_criteria>

<output>
After completion, create `.planning/phases/05-chat-ui-session-management/05-03-SUMMARY.md`
</output>
