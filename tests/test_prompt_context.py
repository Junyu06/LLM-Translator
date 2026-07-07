import unittest

from core.prompt import PromptOptions, PromptPreset, build_prompt


class PromptContextTests(unittest.TestCase):
    def test_contextual_prompt_wraps_context_and_source_and_excludes_context_from_translation(self):
        prompt = build_prompt(
            "Translate this sentence.",
            PromptOptions(
                target_lang="zh",
                preset=PromptPreset.CONTEXTUAL,
                context="Previous sentence for reference.",
            ),
        )

        self.assertIn("<context>\nPrevious sentence for reference.\n</context>", prompt)
        self.assertIn("<source>\nTranslate this sentence.\n</source>", prompt)
        self.assertIn("Do not translate the content inside <context>", prompt)
        self.assertLess(
            prompt.index("</context>"),
            prompt.index("<source>\nTranslate this sentence.\n</source>"),
        )


if __name__ == "__main__":
    unittest.main()
