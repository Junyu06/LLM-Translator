from __future__ import annotations

import unittest

from backend.errors import BackendRequestError
from core.pipeline import PipelineOptions, iter_translation, plan_chunks
from core.splitter import Segment, split_markdown_blocks, split_paragraphs


def prompt_for(text: str) -> str:
    return f"TRANSLATE:\n{text}"


class FakeModel:
    """Answers each request from a script and records the messages it got."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests = []

    def __call__(self, messages):
        self.requests.append(messages)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        # Stream in small pieces like Ollama does.
        for start in range(0, len(reply), 3):
            yield reply[start:start + 3]


def final(progresses):
    return progresses[-1]


class ChunkPlanTests(unittest.TestCase):
    def test_consecutive_paragraphs_share_a_chunk_and_blank_lines_do_not_split_it(self):
        segments = split_paragraphs("One.\nTwo.\n\nThree.")
        self.assertEqual(plan_chunks(segments, PipelineOptions()), [[0, 1, 3]])

    def test_code_block_ends_a_chunk(self):
        segments = split_markdown_blocks("Before.\n\n```\ncode\n```\n\nAfter.")
        self.assertEqual(plan_chunks(segments, PipelineOptions(markdown=True)), [[0], [2]])

    def test_token_budget_starts_a_new_chunk(self):
        segments = [Segment("word " * 100) for _ in range(5)]
        chunks = plan_chunks(segments, PipelineOptions(chunk_tokens=300))
        self.assertGreater(len(chunks), 1)
        self.assertEqual(sum(len(c) for c in chunks), 5)


class IterTranslationTests(unittest.TestCase):
    def test_one_request_for_a_chunk_split_back_into_paragraphs(self):
        model = FakeModel("你好。\n\n世界。")
        progresses = list(iter_translation(split_paragraphs("Hello.\nWorld."), model, prompt_for))

        self.assertEqual(len(model.requests), 1)
        self.assertEqual(model.requests[0][-1]["content"], "TRANSLATE:\nHello.\n\nWorld.")
        self.assertEqual(final(progresses).targets, ["你好。", "世界。"])
        self.assertTrue(final(progresses).finished)
        self.assertEqual(final(progresses).completed, 2)

    def test_partial_updates_fill_paragraphs_in_order(self):
        model = FakeModel("你好。\n\n世界。")
        progresses = list(iter_translation(split_paragraphs("Hello.\nWorld."), model, prompt_for))
        self.assertTrue(any(p.targets[0] and not p.targets[1] for p in progresses))

    def test_mismatched_paragraph_count_falls_back_to_one_request_per_paragraph(self):
        model = FakeModel("你好，世界。", "你好。", "世界。")
        progresses = list(iter_translation(split_paragraphs("Hello.\nWorld."), model, prompt_for))

        self.assertEqual(len(model.requests), 3)
        self.assertEqual(model.requests[1][-1]["content"], "TRANSLATE:\nHello.")
        self.assertEqual(final(progresses).targets, ["你好。", "世界。"])

    def test_fallback_requests_carry_the_previous_paragraph(self):
        model = FakeModel("合并了", "你好。", "世界。")
        list(iter_translation(split_paragraphs("Hello.\nWorld."), model, prompt_for))
        second = model.requests[2]
        self.assertEqual([m["role"] for m in second], ["user", "assistant", "user"])
        self.assertEqual(second[1]["content"], "你好。")

    def test_next_chunk_gets_the_previous_chunk_as_an_earlier_turn(self):
        opt = PipelineOptions(chunk_tokens=40)
        segments = split_paragraphs("\n".join(f"Paragraph number {i} talks about Holloway." for i in range(6)))
        chunks = plan_chunks(segments, opt)
        model = FakeModel(*["\n\n".join(f"第{i}段" for i in chunk) for chunk in chunks])

        list(iter_translation(segments, model, prompt_for, opt))

        self.assertGreater(len(model.requests), 1)
        second = model.requests[1]
        self.assertEqual([m["role"] for m in second], ["user", "assistant", "user"])
        self.assertIn("第", second[1]["content"])

    def test_code_blocks_pass_through_untouched(self):
        model = FakeModel("之前。", "之后。")
        segments = split_markdown_blocks("Before.\n\n```python\nprint('keep')\n```\n\nAfter.")
        progresses = list(iter_translation(segments, model, prompt_for, PipelineOptions(markdown=True)))
        self.assertEqual(final(progresses).targets, ["之前。", "```python\nprint('keep')\n```", "之后。"])
        self.assertTrue(all("print" not in m[-1]["content"] for m in model.requests))

    def test_markdown_list_items_stay_in_one_block(self):
        model = FakeModel("# 安装\n\n- 下载\n- 拖进应用程序")
        segments = split_markdown_blocks("# Install\n\n- Download\n- Drag into Applications")
        progresses = list(iter_translation(segments, model, prompt_for, PipelineOptions(markdown=True)))
        self.assertEqual(final(progresses).targets, ["# 安装", "- 下载\n- 拖进应用程序"])

    def test_think_block_is_not_shown_or_kept(self):
        model = FakeModel("<think>\n\n</think>\n\n你好。")
        progresses = list(iter_translation(split_paragraphs("Hello."), model, prompt_for))
        self.assertTrue(all("<think>" not in t for p in progresses for t in p.targets))
        self.assertEqual(final(progresses).targets, ["你好。"])

    def test_backend_error_propagates_after_partial_progress(self):
        model = FakeModel("你好。\n\n世界。", BackendRequestError("down", code="backend_stream_error"))
        segments = [
            Segment("Hello."),
            Segment("World."),
            Segment("```\ncode\n```", protected=True, kind="fenced_code"),
            Segment("Again."),
        ]
        progresses = []
        with self.assertRaises(BackendRequestError):
            for progress in iter_translation(segments, model, prompt_for):
                progresses.append(progress)
        self.assertEqual(progresses[-1].targets[:2], ["你好。", "世界。"])


if __name__ == "__main__":
    unittest.main()
