from __future__ import annotations

import re
from typing import Any, Iterator

from backend import OllamaBackend, OllamaBackendOptions, OllamaMode
from core import AlignedPair, OutputMode, PipelineOptions, PromptOptions, SplitMode, SplitOptions, render_output
from core.postprocess import extract_translation
from core.prompt import build_prompt
from core.splitter import split_plain, split_with_limited_context

from ..models import SegmentResult, TranslationRequest, TranslationResponse


class TranslationService:
    def translate(self, request: TranslationRequest) -> TranslationResponse:
        response: TranslationResponse | None = None
        for event in self.stream_translate(request):
            if event.get("event") == "completed":
                payload = event["response"]
                response = TranslationResponse(
                    output_text=payload["output_text"],
                    segments=[SegmentResult(**segment) for segment in payload.get("segments", [])],
                    detected_source_lang=payload.get("detected_source_lang"),
                )

        if response is None:
            raise RuntimeError("Translation stream ended without a completed response.")
        return response

    def stream_translate(self, request: TranslationRequest) -> Iterator[dict[str, Any]]:
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

        detected_source_lang = (
            self._detect_source_lang(text) if request.source_lang == "auto" else request.source_lang
        )
        total_segments = len(segments)
        pairs: list[AlignedPair] = []

        yield {
            "event": "started",
            "total_segments": total_segments,
            "completed_segments": 0,
            "detected_source_lang": detected_source_lang,
            "output_text": "",
            "active_segment_index": None,
            "active_segment_source": None,
            "active_segment_target": "",
            "segment_status": "queued",
        }

        for index, seg in enumerate(segments):
            if not seg.text.strip():
                pairs.append(AlignedPair(source=seg.text, target=seg.text))
                yield self._update_event(
                    pairs=pairs,
                    output_mode=output_mode,
                    collapse_newlines=request.collapse_newlines,
                    detected_source_lang=detected_source_lang,
                    completed_segments=index + 1,
                    total_segments=total_segments,
                    partial=False,
                    active_segment_index=index + 1,
                    active_segment_source=seg.text,
                    active_segment_target=seg.text,
                    segment_status="passthrough",
                )
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

            raw = ""
            for chunk in backend.stream_generate(prompt):
                raw += chunk
                yield self._update_event(
                    pairs=pairs + [AlignedPair(source=seg.text, target=raw)],
                    output_mode=output_mode,
                    collapse_newlines=request.collapse_newlines,
                    detected_source_lang=detected_source_lang,
                    completed_segments=index,
                    total_segments=total_segments,
                    partial=True,
                    active_segment_index=index + 1,
                    active_segment_source=seg.text,
                    active_segment_target=raw,
                    segment_status="streaming",
                )

            target = extract_translation(raw, opt.post_opt)
            pairs.append(AlignedPair(source=seg.text, target=target))
            yield self._update_event(
                pairs=pairs,
                output_mode=output_mode,
                collapse_newlines=request.collapse_newlines,
                detected_source_lang=detected_source_lang,
                completed_segments=index + 1,
                total_segments=total_segments,
                partial=False,
                active_segment_index=index + 1,
                active_segment_source=seg.text,
                active_segment_target=target,
                segment_status="completed",
            )

        response = TranslationResponse(
            output_text=self._render_output(pairs, output_mode, request.collapse_newlines),
            segments=[SegmentResult(source=pair.source, target=pair.target) for pair in pairs],
            detected_source_lang=detected_source_lang,
        )
        yield {
            "event": "completed",
            "response": response.to_dict(),
            "output_text": response.output_text,
            "completed_segments": total_segments,
            "total_segments": total_segments,
            "detected_source_lang": detected_source_lang,
            "active_segment_index": None,
            "active_segment_source": None,
            "active_segment_target": "",
            "segment_status": "completed",
        }

    def _update_event(
        self,
        *,
        pairs: list[AlignedPair],
        output_mode: OutputMode,
        collapse_newlines: bool,
        detected_source_lang: str | None,
        completed_segments: int,
        total_segments: int,
        partial: bool,
        active_segment_index: int | None,
        active_segment_source: str | None,
        active_segment_target: str,
        segment_status: str,
    ) -> dict[str, Any]:
        return {
            "event": "update",
            "output_text": self._render_output(pairs, output_mode, collapse_newlines),
            "completed_segments": completed_segments,
            "total_segments": total_segments,
            "detected_source_lang": detected_source_lang,
            "partial": partial,
            "active_segment_index": active_segment_index,
            "active_segment_source": active_segment_source,
            "active_segment_target": active_segment_target,
            "segment_status": segment_status,
            "segments": [{"source": pair.source, "target": pair.target} for pair in pairs],
        }

    def _render_output(self, pairs: list[AlignedPair], mode: OutputMode, collapse_newlines: bool) -> str:
        output_text = render_output(pairs, mode=mode)
        if collapse_newlines:
            output_text = re.sub(r"\n{3,}", "\n\n", self._normalize_text(output_text))
        return output_text

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
