from __future__ import annotations

import re
from typing import Any, Iterator, List

from backend import LOCAL_HOST, BackendError, OllamaBackend, OllamaBackendOptions
from core import (
    OutputMode,
    PipelineOptions,
    Segment,
    build_custom_prompt,
    build_prompt,
    estimate_tokens,
    iter_translation,
    pairs_from,
    parse_glossary,
    render_output,
    resolve_family,
    split_long_segments,
    split_markdown_blocks,
    split_paragraphs,
)

from ..models import SegmentResult, TranslationRequest, TranslationResponse


# Longer paragraphs and lists are cut; see split_long_segments.
LONG_PARAGRAPH_TOKENS = 1200
# A block still longer than this (one huge heading, quote or table) is refused:
# with its translation it would not fit Ollama's default 4096-token context.
MAX_BLOCK_TOKENS = 1500


class TranslationFailed(Exception):
    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


class TranslationService:
    def translate(self, request: TranslationRequest) -> TranslationResponse:
        for event in self.stream_translate(request):
            if event["event"] == "error":
                raise TranslationFailed(event["message"], event["code"])
            if event["event"] == "completed":
                payload = event["response"]
                return TranslationResponse(
                    output_text=payload["output_text"],
                    segments=[SegmentResult(**segment) for segment in payload["segments"]],
                    detected_source_lang=payload.get("detected_source_lang"),
                )
        raise RuntimeError("Translation stream ended without a completed response.")

    def stream_translate(self, request: TranslationRequest) -> Iterator[dict[str, Any]]:
        """Yield started, update, then completed or error events.

        Every event carries all segments so far, so the UI never has to work
        out which paragraph a piece of text belongs to.
        """
        text = self._normalize_text(request.text)
        if not text.strip():
            raise ValueError("Nothing to translate.")

        markdown = request.translation_mode == "markdown"
        blocks = split_markdown_blocks(text) if markdown else self._trim_blank_edges(split_paragraphs(text))
        segments = split_long_segments(blocks, LONG_PARAGRAPH_TOKENS)
        self._validate_request_budget(request, text, segments)

        detected = self._detect_source_lang(text) if request.source_lang == "auto" else request.source_lang
        family = resolve_family(request.model, request.prompt_style)
        glossary = parse_glossary(request.glossary)

        def prompt_for(source: str) -> str:
            if request.prompt_style == "custom":
                return build_custom_prompt(
                    request.custom_prompt,
                    source,
                    target_lang=request.target_lang,
                    source_lang=request.source_lang,
                    glossary=glossary,
                )
            return build_prompt(
                source,
                family=family,
                target_lang=request.target_lang,
                source_lang=request.source_lang,
                detected_lang=detected or "auto",
                markdown=markdown,
                glossary=glossary,
            )

        backend = OllamaBackend(OllamaBackendOptions(
            model=request.model.strip(),
            host=request.host.strip() if request.mode == "http" else LOCAL_HOST,
            options={"temperature": float(request.temperature)},
        ))
        history = self._context_turn(request.context, prompt_for)
        output_mode = OutputMode(request.output_mode)
        join_with = "\n\n" if markdown else "\n"

        def event(name: str, targets: List[str], done: List[bool], completed: int, total: int) -> dict[str, Any]:
            pairs = pairs_from(segments, targets)
            return {
                "event": name,
                "output_text": self._render_output(pairs, output_mode, request.collapse_newlines, join_with),
                "segments": [
                    {"source": pair.source, "target": pair.target, "done": is_done}
                    for pair, is_done in zip(pairs, done)
                ],
                "completed_segments": completed,
                "total_segments": total,
                "detected_source_lang": detected,
            }

        targets = ["" if segment.translatable else segment.text for segment in segments]
        done = [not segment.translatable for segment in segments]
        total = sum(1 for segment in segments if segment.translatable)
        completed = 0
        yield event("started", targets, done, completed, total)

        try:
            for progress in iter_translation(segments, backend.stream_chat, prompt_for, PipelineOptions(markdown=markdown, history=history)):
                targets, done, completed = progress.targets, progress.done, progress.completed
                if not progress.finished:
                    yield event("update", targets, done, completed, total)
        except Exception as exc:
            failed = event("error", targets, done, completed, total)
            failed["code"] = exc.code if isinstance(exc, BackendError) else "backend_error"
            failed["message"] = str(exc) or exc.__class__.__name__
            yield failed
            return

        finished = event("completed", targets, done, completed, total)
        finished["response"] = TranslationResponse(
            output_text=finished["output_text"],
            segments=[SegmentResult(source=s.text, target=t) for s, t in zip(segments, targets)],
            detected_source_lang=detected,
        ).to_dict()
        yield finished

    @staticmethod
    def _context_turn(context: List[dict], prompt_for) -> List[dict]:
        """The paragraphs before a re-translated one, as an earlier chat turn (about 250 tokens at most)."""
        kept: List[dict] = []
        tokens = 0
        for pair in reversed(context):
            cost = estimate_tokens(pair["source"])
            if not pair["source"].strip() or not pair["target"].strip():
                continue
            if tokens + cost > 250:
                break
            kept.insert(0, pair)
            tokens += cost
        if not kept:
            return []
        return [
            {"role": "user", "content": prompt_for("\n\n".join(pair["source"] for pair in kept))},
            {"role": "assistant", "content": "\n\n".join(pair["target"] for pair in kept)},
        ]

    def _render_output(self, pairs, mode: OutputMode, collapse_newlines: bool, join_with: str) -> str:
        output_text = render_output(pairs, mode=mode, join_with=join_with)
        if collapse_newlines:
            output_text = re.sub(r"\n{3,}", "\n\n", output_text)
        return output_text

    @staticmethod
    def _trim_blank_edges(segments: List[Segment]) -> List[Segment]:
        start, end = 0, len(segments)
        while start < end and segments[start].kind == "blank":
            start += 1
        while end > start and segments[end - 1].kind == "blank":
            end -= 1
        return segments[start:end]

    def _validate_request_budget(
        self,
        request: TranslationRequest,
        text: str,
        segments: List[Segment],
    ) -> None:
        max_chars = max(0, int(request.max_chars))
        max_segments = max(0, int(request.max_segments))
        max_segment_chars = max(0, int(request.max_segment_chars))
        translatable = [segment for segment in segments if segment.translatable]

        if max_chars and len(text) > max_chars:
            raise ValueError(
                f"Input is too large to translate ({len(text)} characters; limit is {max_chars})."
            )

        if max_segments and len(translatable) > max_segments:
            raise ValueError(
                f"Too many translation segments ({len(translatable)} segments; limit is {max_segments})."
            )

        for index, segment in enumerate(translatable, start=1):
            tokens = estimate_tokens(segment.text)
            if tokens > MAX_BLOCK_TOKENS:
                raise ValueError(
                    f"Block {index} is too long to translate in one request (about {tokens} tokens; "
                    f"limit {MAX_BLOCK_TOKENS}). Break it into shorter paragraphs."
                )

        if max_segment_chars:
            for index, segment in enumerate(translatable, start=1):
                if len(segment.text) > max_segment_chars:
                    raise ValueError(
                        f"Translation segment is too large at segment {index} "
                        f"({len(segment.text)} characters; limit is {max_segment_chars})."
                    )

    def _normalize_text(self, text: str) -> str:
        return (
            text.replace("\r\n", "\n")
            .replace("\r", "\n")
            .replace(" ", "\n")
            .replace(" ", "\n")
            .replace("\u0085", "\n")
            .replace(" ", " ")
        )

    def _detect_source_lang(self, text: str) -> str | None:
        """Guess the main language by counting scripts, so one quoted word does not decide."""
        kana = hangul = han = latin = 0
        for ch in text:
            code = ord(ch)
            if 0x3040 <= code <= 0x30FF:
                kana += 1
            elif 0xAC00 <= code <= 0xD7AF:
                hangul += 1
            elif 0x4E00 <= code <= 0x9FFF:
                han += 1
            elif ch.isascii() and ch.isalpha():
                latin += 1
        # One CJK character carries about as much as a five-letter word.
        cjk = kana + hangul + han
        if cjk == 0 and latin == 0:
            return None
        if cjk * 5 < latin:
            return "en"
        if hangul > han and hangul > kana:
            return "ko"
        if kana >= max(2, cjk // 10):
            return "ja"
        return "zh"
