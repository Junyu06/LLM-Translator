# Translation Correctness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve Markdown/code structure, bound oversized inputs, make postprocessing conservative, and clarify context boundaries.

**Architecture:** Add block-aware segmentation in `core/splitter.py` and use it from the desktop service for Markdown mode. Keep protected Markdown/code blocks as passthrough segments so they are never sent to the model. Validate request budgets before backend calls, and make prompt/postprocess behavior explicit enough to avoid translating context or truncating legitimate text.

**Tech Stack:** Python 3.14 `unittest`; existing dataclasses; no new dependencies.

## Global Constraints

- TDD first for behavior changes.
- Cover regression samples: indented code block, fenced code, Markdown table, blockquote, list continuation, body text containing `Translation:`, paired/unpaired quotes, and oversized input.
- Preserve original indentation and blank lines where structure matters.
- Markdown mode must split by blocks rather than sending the entire document as one segment.
- Code/table/list/blockquote protected blocks should not be destructively stripped.
- Oversized inputs must fail with user-readable errors, not silent truncation.
- Context prompt must use `<context>` and `<source>` boundaries and instruct the model not to translate context.

---

## File Map

- `core/splitter.py`: add block-aware splitter and safer line preservation.
- `core/postprocess.py`: restrict marker extraction and paired-quote stripping.
- `core/prompt.py`: add explicit context/source boundaries.
- `python_backend/models.py`: add request budget fields.
- `python_backend/services/translation_service.py`: enforce budgets, use block-aware Markdown segmentation, disable aggressive Markdown postprocess.
- `tests/test_splitter_blocks.py`: block-aware segmentation tests.
- `tests/test_postprocess.py`: marker and quote regression tests.
- `tests/test_prompt_context.py`: context/source boundary test.
- `tests/test_translation_service.py`: service-level Markdown split and budget tests.

## Task 1: Block-Aware Splitter

**Files:**
- Modify: `core/splitter.py`
- Create: `tests/test_splitter_blocks.py`

**Interfaces:**
- Add `Segment.protected: bool = False`
- Add `Segment.kind: str = "text"`
- Add `split_markdown_blocks(text: str, opt: SplitOptions = SplitOptions(strip_each_line=False, drop_empty_lines=False)) -> list[Segment]`
- Preserve existing `split_plain()` and `split_with_limited_context()` callers.

- [ ] Write failing tests for fenced code, indented code, Markdown table, blockquote, and list continuation.
- [ ] Implement block parsing that groups fenced code until closing fence, groups indented code runs, table rows, blockquotes, and list items with indented continuation lines.
- [ ] Return protected passthrough segments for code/table/list/blockquote; return normal text segments for prose blocks.
- [ ] Run `python3 -m unittest tests.test_splitter_blocks -v`.

## Task 2: Conservative Postprocess

**Files:**
- Modify: `core/postprocess.py`
- Create: `tests/test_postprocess.py`

**Interfaces:**
- Keep `extract_translation(raw, opt=PostProcessOptions())`.
- Add helper behavior, not a breaking API.

- [ ] Write failing tests showing `Translation:` inside body text is preserved.
- [ ] Write failing tests showing only paired wrapping quotes are removed; unpaired leading/trailing quotes are preserved.
- [ ] Change marker extraction to apply only when a marker appears at the beginning after optional whitespace, not via `rfind`.
- [ ] Keep whitespace cleanup behavior.
- [ ] Run `python3 -m unittest tests.test_postprocess -v`.

## Task 3: Context Prompt Boundaries

**Files:**
- Modify: `core/prompt.py`
- Create: `tests/test_prompt_context.py`

**Interfaces:**
- Keep `build_prompt(source_text, opt)` signature.

- [ ] Write failing test that contextual prompts contain `<context>...</context>` and `<source>...</source>`.
- [ ] Update contextual prompt copy to explicitly say not to translate context.
- [ ] Run `python3 -m unittest tests.test_prompt_context -v`.

## Task 4: Service Budgets and Markdown Blocks

**Files:**
- Modify: `python_backend/models.py`
- Modify: `python_backend/services/translation_service.py`
- Modify: `tests/test_translation_service.py`

**Interfaces:**
- Add `max_chars: int = 50000`, `max_segments: int = 200`, `max_segment_chars: int = 8000` to `TranslationRequest`.
- Add `_validate_request_budget(request, text)` in service.
- Use `split_markdown_blocks()` for Markdown mode.

- [ ] Write failing service tests for Markdown splitting into multiple segments with protected fenced code/table passthrough.
- [ ] Write failing service tests for oversized input and oversized segment user-readable `ValueError`.
- [ ] Implement budget checks before backend construction.
- [ ] In Markdown mode, use block-aware segments; for protected segments, passthrough without backend call.
- [ ] In Markdown mode, call `extract_translation()` with conservative options that do not remove leading labels or quotes beyond safe cleanup.
- [ ] Run `python3 -m unittest tests.test_translation_service -v`.

## Task 5: Final Validation and Merge

- [ ] Run:

```bash
python3 -m unittest discover -s tests -v
python3 core_test.py
git log --oneline -3
```

- [ ] Request code review.
- [ ] Fix any Critical/Important findings.
- [ ] Merge `worker/2026-07-07-fix-2-translation-correctness` into `main` and push if validation is green.
