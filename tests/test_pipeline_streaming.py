from __future__ import annotations

import unittest

from backend.errors import BackendRequestError
from core.pipeline import OutputMode, PipelineOptions, PipelineStreamUpdate, SplitMode, iter_streaming_pipeline
from core.prompt import PromptPreset


class StreamingPipelineTests(unittest.TestCase):
    def test_streaming_pipeline_emits_partial_and_completed_updates(self) -> None:
        opt = PipelineOptions(split_mode=SplitMode.PLAIN, skip_empty_segments=False)

        def stream_generate(prompt: str):
            self.assertIn("你好", prompt)
            yield "译文：Hel"
            yield "lo"

        updates = list(iter_streaming_pipeline("你好", stream_generate, opt=opt))

        self.assertIsInstance(updates[0], PipelineStreamUpdate)
        self.assertEqual([update.segment_status for update in updates], ["streaming", "streaming", "completed"])
        self.assertEqual(updates[-1].pairs[0].target, "Hello")

    def test_streaming_pipeline_passthroughs_markdown_protected_blocks(self) -> None:
        opt = PipelineOptions(
            split_mode=SplitMode.MARKDOWN,
            prompt_opt=PipelineOptions().prompt_opt,
            skip_empty_segments=False,
        )
        opt.prompt_opt.preset = PromptPreset.MARKDOWN

        updates = list(
            iter_streaming_pipeline(
                "```python\nprint('keep')\n```",
                lambda prompt: iter(["should not be called"]),
                opt=opt,
            )
        )

        self.assertEqual(len(updates), 1)
        self.assertEqual(updates[0].segment_status, "passthrough")
        self.assertEqual(updates[0].pairs[0].target, "```python\nprint('keep')\n```")

    def test_streaming_pipeline_yields_error_update_then_reraises(self) -> None:
        opt = PipelineOptions(split_mode=SplitMode.PLAIN, skip_empty_segments=False)

        def stream_generate(prompt: str):
            raise BackendRequestError("bad json", code="invalid_backend_json")
            yield ""

        stream = iter_streaming_pipeline("hello", stream_generate, opt=opt)
        updates = []

        with self.assertRaises(BackendRequestError):
            while True:
                updates.append(next(stream))

        self.assertEqual(updates[-1].segment_status, "error")
        self.assertEqual(updates[-1].error.code, "invalid_backend_json")


if __name__ == "__main__":
    unittest.main()
