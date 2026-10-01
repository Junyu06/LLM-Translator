import unittest

from core.prompt import ModelFamily, build_prompt, detect_family


class PromptTests(unittest.TestCase):
    def test_family_detection(self):
        self.assertEqual(detect_family("index-translate:2b-q4_K_M"), ModelFamily.INDEX)
        self.assertEqual(detect_family("IndexTeam/Index-Translate-9B"), ModelFamily.INDEX)
        self.assertEqual(detect_family("kaelri/hy-mt2:1.8b-q4_K_M"), ModelFamily.HY)
        self.assertEqual(detect_family("demonbyron/HY-MT1.5-1.8B"), ModelFamily.HY)
        self.assertEqual(detect_family("qwen3:8b"), ModelFamily.GENERIC)

    def test_index_uses_its_training_prompt(self):
        prompt = build_prompt("Hello.", family=ModelFamily.INDEX, target_lang="zh")
        self.assertEqual(prompt, "请将以下文本翻译为中文，直接输出翻译结果，不要进行任何解释。\n\nHello.")

    def test_index_names_the_source_language_only_when_the_user_picked_it(self):
        prompt = build_prompt("Hello.", family=ModelFamily.INDEX, target_lang="zh", source_lang="en")
        self.assertTrue(prompt.startswith("请将以下英语文本翻译为中文"))

    def test_hy_uses_chinese_prompt_with_chinese_language_names(self):
        prompt = build_prompt("你好", family=ModelFamily.HY, target_lang="en", detected_lang="zh")
        self.assertEqual(prompt, "将以下文本翻译为英语，注意只需要输出翻译后的结果，不要额外解释：\n\n你好")

    def test_hy_uses_english_prompt_without_chinese(self):
        prompt = build_prompt("Hallo", family=ModelFamily.HY, target_lang="en", detected_lang="de")
        self.assertTrue(prompt.startswith("Translate the following text into English."))

    def test_markdown_prompts_ask_to_keep_formatting(self):
        self.assertIn("保留 Markdown 格式", build_prompt("# Hi", family=ModelFamily.INDEX, target_lang="zh", markdown=True))
        self.assertIn("Keep the Markdown formatting", build_prompt("# Hi", family=ModelFamily.GENERIC, target_lang="zh", markdown=True))


if __name__ == "__main__":
    unittest.main()
