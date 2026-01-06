# hy_translator/core/pipeline.py

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List

from .splitter import (
    SplitOptions,
    ContextOptions,
    Segment,
    split_plain,
    split_with_limited_context,
)
from .prompt import PromptOptions, build_prompt
from .postprocess import PostProcessOptions, extract_translation


class SplitMode(str, Enum):
    PLAIN = "plain"
    CONTEXT = "context"  # prev1, optionally prev2

class OutputMode(str, Enum):
    TRANSLATIONS_ONLY = "translations_only"
    INTERLEAVED = "interleaved"


@dataclass
class AlignedPair:
    source: str
    target: str
    context: str = ""   # 仅 debug 或 UI 需要时用
    prompt: str = ""    # debug
    raw: str = ""       # debug

@dataclass
class SegmentReport:
    index: int
    source: str
    expected_context: str
    prompt: str
    raw: str
    extracted: str

    prompt_contains_context: bool
    used_contextual_template: bool  # 参考上面的信息... 这句是否出现

@dataclass
class PipelineOptions:
    split_mode: SplitMode = SplitMode.PLAIN

    # ⚠️ 用 default_factory，避免多个 PipelineOptions 共享同一个对象
    split_opt: SplitOptions = field(default_factory=SplitOptions)
    ctx_opt: ContextOptions = field(default_factory=ContextOptions)
    prompt_opt: PromptOptions = field(default_factory=PromptOptions)
    post_opt: PostProcessOptions = field(default_factory=PostProcessOptions)

    keep_debug: bool = False
    join_with: str = "\n"
    skip_empty_segments: bool = True


GenerateFn = Callable[[str], str]


def make_segments(text: str, opt: PipelineOptions) -> List[Segment]:
    if opt.split_mode == SplitMode.CONTEXT:
        return split_with_limited_context(text, split_opt=opt.split_opt, ctx_opt=opt.ctx_opt)
    return split_plain(text, opt=opt.split_opt)

@dataclass
class PipelineReport:
    split_mode: SplitMode
    reports: List[SegmentReport] = field(default_factory=list)

    def context_success_rate(self) -> float:
        candidates = [r for r in self.reports if r.expected_context.strip()]
        if not candidates:
            return 1.0
        ok = sum(
            1 for r in candidates
            if r.prompt_contains_context and r.used_contextual_template
        )
        return ok / len(candidates)

def run_pipeline(
    text: str,
    generate: Callable[[str], str],
    opt: PipelineOptions | None = None,
    return_report: bool = False,
):
    if opt is None:
        opt = PipelineOptions()

    segments = make_segments(text, opt)
    pairs: List[AlignedPair] = []

    report: PipelineReport | None = (
        PipelineReport(split_mode=opt.split_mode)
        if return_report
        else None
    )

    for i, seg in enumerate(segments):
        if opt.skip_empty_segments and not seg.text.strip():
            continue

        p_opt = PromptOptions(
            source_lang=opt.prompt_opt.source_lang,
            target_lang=opt.prompt_opt.target_lang,
            preset=opt.prompt_opt.preset,
            terminology=opt.prompt_opt.terminology,
            context=seg.context,
            src_text_with_format=opt.prompt_opt.src_text_with_format,
        )

        prompt = build_prompt(seg.text, p_opt)
        raw = generate(prompt)
        target = extract_translation(raw, opt.post_opt)

        pairs.append(
            AlignedPair(
                source=seg.text,
                target=target,
                context=seg.context if opt.keep_debug else "",
                prompt=prompt if opt.keep_debug else "",
                raw=raw if opt.keep_debug else "",
            )
        )

        if report is not None:
            expected_ctx = seg.context or ""
            prompt_contains = (
                True if not expected_ctx.strip()
                else expected_ctx.strip() in prompt
            )
            used_contextual = (
                True if not expected_ctx.strip()
                else "参考上面的信息" in prompt
            )

            report.reports.append(
                SegmentReport(
                    index=i,
                    source=seg.text,
                    expected_context=expected_ctx,
                    prompt=prompt,
                    raw=raw,
                    extracted=target,
                    prompt_contains_context=prompt_contains,
                    used_contextual_template=used_contextual,
                )
            )

    if return_report:
        return pairs, report
    return pairs


def iter_pipeline(
    text: str,
    generate: Callable[[str], str],
    opt: PipelineOptions | None = None,
):
    if opt is None:
        opt = PipelineOptions()

    segments = make_segments(text, opt)

    for seg in segments:
        if opt.skip_empty_segments and not seg.text.strip():
            continue

        p_opt = PromptOptions(
            source_lang=opt.prompt_opt.source_lang,
            target_lang=opt.prompt_opt.target_lang,
            preset=opt.prompt_opt.preset,
            terminology=opt.prompt_opt.terminology,
            context=seg.context,
            src_text_with_format=opt.prompt_opt.src_text_with_format,
        )

        prompt = build_prompt(seg.text, p_opt)
        raw = generate(prompt)
        target = extract_translation(raw, opt.post_opt)

        yield AlignedPair(
            source=seg.text,
            target=target,
            context=seg.context if opt.keep_debug else "",
            prompt=prompt if opt.keep_debug else "",
            raw=raw if opt.keep_debug else "",
        )


def join_translations(pairs: List[AlignedPair], join_with: str = "\n") -> str:
    return join_with.join(p.target for p in pairs)


def join_interleaved(pairs: List[AlignedPair], join_with: str = "\n") -> str:
    blocks: List[str] = []
    for p in pairs:
        blocks.append(p.source)
        blocks.append(p.target)
        blocks.append("")  # blank line between source/target pairs
    if blocks:
        blocks.pop()  # remove trailing blank line
    return join_with.join(blocks)

def render_output(pairs: List[AlignedPair], mode: OutputMode, join_with: str = "\n") -> str:
    if mode == OutputMode.INTERLEAVED:
        return join_interleaved(pairs, join_with=join_with)
    return join_translations(pairs, join_with=join_with)
