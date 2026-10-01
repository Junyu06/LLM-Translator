"""Translate segments a chunk at a time and keep each translation paired with its source.

Small translation models translate several paragraphs in one request more
consistently (names, terms, pronouns) and faster than one request per
paragraph with neighbouring paragraphs pasted in as "context". So the
pipeline groups consecutive paragraphs into chunks, translates each chunk in
one request with paragraphs separated by blank lines, and splits the
translation back into paragraphs. When the paragraph count does not match,
that chunk falls back to one request per paragraph so pairs never drift.

The tail of the previous chunk goes along as an earlier chat turn, which
carries names and terms across chunk boundaries.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Iterator, List

from .postprocess import extract_translation, strip_reasoning
from .splitter import Segment

ChatStream = Callable[[List[dict]], Iterator[str]]
PromptFor = Callable[[str], str]


class OutputMode(str, Enum):
    TRANSLATIONS_ONLY = "translations_only"
    INTERLEAVED = "interleaved"


@dataclass
class PipelineOptions:
    # Source budget per request. Prompt, previous turn and output must fit the
    # 4096-token default context of Ollama; translation output is about as long
    # as the source in tokens.
    chunk_tokens: int = 700
    max_chunk_segments: int = 40
    history_tokens: int = 250
    markdown: bool = False


@dataclass
class AlignedPair:
    source: str
    target: str


@dataclass
class Progress:
    targets: List[str]
    done: List[bool]
    completed: int
    total: int
    finished: bool = False


def estimate_tokens(text: str) -> int:
    wide = sum(1 for ch in text if unicodedata.east_asian_width(ch) in "WF")
    return int(wide / 1.2 + (len(text) - wide) / 3.5) + 1


def plan_chunks(segments: List[Segment], opt: PipelineOptions) -> List[List[int]]:
    """Group translatable segments into chunks. Code blocks end a chunk; blank lines do not."""
    chunks: List[List[int]] = []
    current: List[int] = []
    tokens = 0
    for index, segment in enumerate(segments):
        if segment.protected and segment.kind != "blank":
            if current:
                chunks.append(current)
            current, tokens = [], 0
            continue
        if not segment.translatable:
            continue
        cost = estimate_tokens(segment.text)
        if current and (tokens + cost > opt.chunk_tokens or len(current) >= opt.max_chunk_segments):
            chunks.append(current)
            current, tokens = [], 0
        current.append(index)
        tokens += cost
    if current:
        chunks.append(current)
    return chunks


_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+|(?<=[。！？；])")


def split_long_segments(segments: List[Segment], max_tokens: int) -> List[Segment]:
    """Cut paragraphs too long for one request into sentence groups.

    A paragraph whose source and translation together exceed Ollama's default
    context would be silently truncated, so it is translated in parts, each
    shown as its own pair.
    """
    result: List[Segment] = []
    for segment in segments:
        if not segment.translatable or segment.kind != "text" or estimate_tokens(segment.text) <= max_tokens:
            result.append(segment)
            continue
        part = ""
        for sentence in (s for s in _SENTENCE_END_RE.split(segment.text) if s.strip()):
            joined = f"{part} {sentence}".strip() if part and not _ends_cjk(part) else part + sentence
            if part and estimate_tokens(joined) > max_tokens:
                result.append(Segment(text=part.strip()))
                part = sentence
            else:
                part = joined
        if part.strip():
            result.append(Segment(text=part.strip()))
    return result


def _ends_cjk(text: str) -> bool:
    return bool(text) and unicodedata.east_asian_width(text[-1]) in "WF"


def split_output(content: str, markdown: bool) -> List[str]:
    """Split a chunk translation back into paragraphs.

    Normal-mode paragraphs never contain a line break, so any line break
    separates paragraphs. Markdown blocks can span lines, so only blank lines do.
    """
    if markdown:
        return [part.strip() for part in re.split(r"\n\s*\n", content) if part.strip()]
    return [line.strip() for line in content.splitlines() if line.strip()]


def _visible(content: str) -> str:
    """What to show while a reply is still streaming: nothing inside an open <think> block."""
    stripped = content.lstrip()
    if stripped.startswith("<think>") and "</think>" not in stripped:
        return ""
    return strip_reasoning(stripped)


def iter_translation(
    segments: List[Segment],
    chat: ChatStream,
    prompt_for: PromptFor,
    opt: PipelineOptions | None = None,
) -> Iterator[Progress]:
    opt = opt or PipelineOptions()
    targets = ["" if segment.translatable else segment.text for segment in segments]
    done = [not segment.translatable for segment in segments]
    total = sum(1 for segment in segments if segment.translatable)
    completed = 0
    history: List[dict] = []

    def snapshot(finished: bool = False) -> Progress:
        return Progress(list(targets), list(done), completed, total, finished)

    def stream(messages: List[dict], on_text: Callable[[str], None]) -> Iterator[str]:
        content = ""
        for piece in chat(messages):
            content += piece
            on_text(_visible(content))
            yield content

    def clean(raw: str, index: int) -> str:
        return extract_translation(raw, segments[index].text, keep_format=opt.markdown)

    for chunk in plan_chunks(segments, opt):
        sources = [segments[index].text for index in chunk]
        request = {"role": "user", "content": prompt_for("\n\n".join(sources))}

        def spread(visible: str, chunk: List[int] = chunk) -> None:
            parts = [visible] if len(chunk) == 1 else split_output(visible, opt.markdown)
            for slot, index in enumerate(chunk):
                targets[index] = parts[slot] if slot < len(parts) else ""
            if len(parts) > len(chunk):
                targets[chunk[-1]] = "\n".join(parts[len(chunk) - 1:])

        content = ""
        for content in stream(history + [request], spread):
            yield snapshot()

        reply = strip_reasoning(content)
        parts = [reply] if len(chunk) == 1 else split_output(reply, opt.markdown)
        if len(parts) == len(chunk):
            pairs = list(zip(chunk, parts))
            for index, part in pairs:
                targets[index] = clean(part, index)
                done[index] = True
            completed += len(chunk)
            history = _previous_turn(chunk, segments, targets, prompt_for, opt)
            yield snapshot()
            continue

        # The model merged or split paragraphs: translate this chunk one paragraph at a time.
        for index in chunk:
            targets[index] = ""
        for index in chunk:
            request = {"role": "user", "content": prompt_for(segments[index].text)}

            def show(visible: str, index: int = index) -> None:
                targets[index] = visible

            content = ""
            for content in stream(history + [request], show):
                yield snapshot()
            targets[index] = clean(content, index)
            done[index] = True
            completed += 1
            history = [request, {"role": "assistant", "content": targets[index]}]
            yield snapshot()

    yield snapshot(finished=True)


def _previous_turn(
    chunk: List[int],
    segments: List[Segment],
    targets: List[str],
    prompt_for: PromptFor,
    opt: PipelineOptions,
) -> List[dict]:
    """The last paragraphs of a chunk and their translations, as one earlier chat turn."""
    tail: List[int] = []
    tokens = 0
    for index in reversed(chunk):
        cost = estimate_tokens(segments[index].text)
        if tokens + cost > opt.history_tokens:
            break
        tail.insert(0, index)
        tokens += cost
    if not tail:
        return []
    return [
        {"role": "user", "content": prompt_for("\n\n".join(segments[i].text for i in tail))},
        {"role": "assistant", "content": "\n\n".join(targets[i] for i in tail)},
    ]


def pairs_from(segments: List[Segment], targets: List[str]) -> List[AlignedPair]:
    return [AlignedPair(source=segment.text, target=target) for segment, target in zip(segments, targets)]


def join_translations(pairs: List[AlignedPair], join_with: str = "\n") -> str:
    return join_with.join(p.target for p in pairs)


def join_interleaved(pairs: List[AlignedPair], join_with: str = "\n") -> str:
    parts = []
    total = len(pairs)
    for i, p in enumerate(pairs):
        src = p.source
        tgt = p.target
        if not src.strip() and not tgt.strip():
            parts.append(("", True))
            continue
        parts.append((src, False))
        parts.append((tgt, False))
        add_sep = True
        if i + 1 < total:
            nxt = pairs[i + 1]
            if not nxt.source.strip() and not nxt.target.strip():
                add_sep = False
        if add_sep:
            parts.append(("", True))  # blank line between source/target pairs
    if parts and parts[-1][1]:
        parts.pop()
    return join_with.join(text for text, _ in parts)


def render_output(pairs: List[AlignedPair], mode: OutputMode, join_with: str = "\n") -> str:
    if mode == OutputMode.INTERLEAVED:
        return join_interleaved(pairs, join_with=join_with)
    return join_translations(pairs, join_with=join_with)
