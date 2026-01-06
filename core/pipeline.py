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


@dataclass
class AlignedPair:
    source: str
    target: str
    context: str = ""   # 仅 debug 或 UI 需要时用
    prompt: str = ""    # debug
    raw: str = ""       # debug


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


def run_pipeline(text: str, generate: GenerateFn, opt: PipelineOptions | None = None) -> List[AlignedPair]:
    if opt is None:
        opt = PipelineOptions()

    segments = make_segments(text, opt)
    pairs: List[AlignedPair] = []

    for seg in segments:
        if opt.skip_empty_segments and not seg.text.strip():
            continue

        # ✅ 这里就是“联动点”：splitter 产出 context，prompt 自动吃进去
        p_opt = PromptOptions(
            source_lang=opt.prompt_opt.source_lang,
            target_lang=opt.prompt_opt.target_lang,
            preset=opt.prompt_opt.preset,

            terminology=opt.prompt_opt.terminology,
            context=seg.context,  # <-- splitter 联动到 prompt
            src_text_with_format=opt.prompt_opt.src_text_with_format,
        )

        prompt = build_prompt(seg.text, p_opt)
        raw = generate(prompt)
        target = extract_translation(raw, opt.post_opt)

        pairs.append(AlignedPair(
            source=seg.text,
            target=target,
            context=seg.context if opt.keep_debug else "",
            prompt=prompt if opt.keep_debug else "",
            raw=raw if opt.keep_debug else "",
        ))

    return pairs


def join_translations(pairs: List[AlignedPair], join_with: str = "\n") -> str:
    return join_with.join(p.target for p in pairs)


def join_interleaved(pairs: List[AlignedPair], join_with: str = "\n") -> str:
    blocks: List[str] = []
    for p in pairs:
        blocks.append(p.source)
        blocks.append(p.target)
    return join_with.join(blocks)