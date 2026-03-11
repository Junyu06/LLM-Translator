from __future__ import annotations

import re

from backend import OllamaBackend, OllamaBackendOptions, OllamaMode
from core import AlignedPair, OutputMode, PipelineOptions, PromptOptions, SplitMode, SplitOptions, render_output
from core.postprocess import extract_translation
from core.prompt import build_prompt
from core.splitter import split_plain, split_with_limited_context

from ..models import SegmentResult, TranslationRequest, TranslationResponse


class TranslationService:
    def translate(self, request: TranslationRequest) -> TranslationResponse:
        text = self._normalize_text(request.text).strip()
        if not text:
            raise ValueError("Nothing to translate.")

        split_mode = SplitMode.CONTEXT if request.use_context else SplitMode.PLAIN
        prompt_opt = PromptOptions(
            source_lang=request.source_lang,
            target_lang=request.target_lang,
        )
        split_opt = SplitOptions(strip_each_line=True, drop_empty_lines=False)
        opt = PipelineOptions(
            split_mode=split_mode,
            prompt_opt=prompt_opt,
            split_opt=split_opt,
            skip_empty_segments=False,
        )

        backend_opt = OllamaBackendOptions(
            mode=OllamaMode(request.mode),
            model=request.model.strip() or OllamaBackendOptions().model,
            host=request.host.strip() or OllamaBackendOptions().host,
        )
        backend = OllamaBackend(backend_opt)
        output_mode = OutputMode(request.output_mode)

        if split_mode == SplitMode.CONTEXT:
            segments = split_with_limited_context(text, split_opt=opt.split_opt, ctx_opt=opt.ctx_opt)
        else:
            segments = split_plain(text, opt=opt.split_opt)

        pairs: list[AlignedPair] = []
        for seg in segments:
            if not seg.text.strip():
                pairs.append(AlignedPair(source=seg.text, target=seg.text))
                continue
            seg_opt = PromptOptions(
                source_lang=opt.prompt_opt.source_lang,
                target_lang=opt.prompt_opt.target_lang,
                preset=opt.prompt_opt.preset,
                terminology=opt.prompt_opt.terminology,
                context=seg.context,
                src_text_with_format=opt.prompt_opt.src_text_with_format,
            )
            prompt = build_prompt(seg.text, seg_opt)
            raw = backend.generate(prompt)
            target = extract_translation(raw, opt.post_opt)
            pairs.append(AlignedPair(source=seg.text, target=target))

        output_text = render_output(pairs, mode=output_mode)
        if request.collapse_newlines:
            output_text = re.sub(r"\n{3,}", "\n\n", self._normalize_text(output_text))

        return TranslationResponse(
            output_text=output_text,
            segments=[SegmentResult(source=pair.source, target=pair.target) for pair in pairs],
            detected_source_lang=self._detect_source_lang(text) if request.source_lang == "auto" else request.source_lang,
        )

    def _normalize_text(self, text: str) -> str:
        return (
            text.replace("\r\n", "\n")
            .replace("\r", "\n")
            .replace("\u2028", "\n")
            .replace("\u2029", "\n")
            .replace("\u0085", "\n")
            .replace("\u00a0", " ")
        )

    def _detect_source_lang(self, text: str) -> str | None:
        if not text.strip():
            return None
        for ch in text:
            code = ord(ch)
            if 0x3040 <= code <= 0x30FF:
                return "ja"
            if 0xAC00 <= code <= 0xD7AF:
                return "ko"
            if 0x4E00 <= code <= 0x9FFF:
                return "zh"
        return "en"

