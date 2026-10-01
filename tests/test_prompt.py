import unittest

from core.prompt import ModelFamily, build_custom_prompt, build_prompt, detect_family, parse_glossary, resolve_family, terms_in


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


class GlossaryTests(unittest.TestCase):
    def test_parse_accepts_common_separators_and_skips_comments(self):
        text = "# terms\ncontext window = 上下文窗口\nOllama => Ollama\nGGUF → GGUF\nfoo\tbar\nno separator\n = empty"
        self.assertEqual(
            parse_glossary(text),
            [("context window", "上下文窗口"), ("Ollama", "Ollama"), ("GGUF", "GGUF"), ("foo", "bar")],
        )

    def test_only_terms_in_the_text_are_used_and_latin_matches_whole_words(self):
        glossary = [("medium", "中档"), ("cat", "猫"), ("模型", "model")]
        self.assertEqual(terms_in("The Medium setting of the catalog. 模型", glossary), [("medium", "中档"), ("模型", "model")])

    def test_index_uses_its_terminology_wording(self):
        prompt = build_prompt("Raise the context window to 8K.", family=ModelFamily.INDEX, target_lang="zh",
                              glossary=[("context window", "上下文窗口"), ("unused", "x")])
        self.assertEqual(
            prompt,
            "请将以下文本翻译为中文。要求：术语使用固定译法（context window 固定译为“上下文窗口”），"
            "保留原文结构，直接输出翻译结果，不要进行任何解释：\n\nRaise the context window to 8K.",
        )

    def test_hy_uses_its_reference_wording(self):
        prompt = build_prompt("the medium setting", family=ModelFamily.HY, target_lang="zh", glossary=[("medium setting", "思考档位")])
        self.assertTrue(prompt.startswith("参考下面的翻译：\nmedium setting 翻译成 思考档位\n\n将以下文本翻译为中文"))

    def test_no_terms_leaves_the_training_prompt_unchanged(self):
        self.assertEqual(
            build_prompt("Hello.", family=ModelFamily.INDEX, target_lang="zh", glossary=[("medium", "中档")]),
            build_prompt("Hello.", family=ModelFamily.INDEX, target_lang="zh"),
        )


class PromptStyleTests(unittest.TestCase):
    def test_a_picked_style_overrides_the_model_name(self):
        self.assertEqual(resolve_family("my-own-quant:q4", "index"), ModelFamily.INDEX)
        self.assertEqual(resolve_family("index-translate:2b", "auto"), ModelFamily.INDEX)
        self.assertEqual(resolve_family("index-translate:2b", "generic"), ModelFamily.GENERIC)

    def test_custom_template_fills_placeholders(self):
        prompt = build_custom_prompt("Into {target_lang} ({target_lang_zh}):\n{text}", "Hi {x}", target_lang="zh")
        self.assertEqual(prompt, "Into Chinese (中文):\nHi {x}")

    def test_custom_template_without_text_placeholder_appends_the_text(self):
        self.assertEqual(build_custom_prompt("Translate to {target_lang}.", "Hi", target_lang="ja"), "Translate to Japanese.\n\nHi")

    def test_custom_template_text_is_not_treated_as_placeholders(self):
        prompt = build_custom_prompt("{text}", "Use {target_lang} here", target_lang="zh")
        self.assertEqual(prompt, "Use {target_lang} here")

    def test_custom_template_gets_glossary(self):
        with_slot = build_custom_prompt("Terms:\n{glossary}\n{text}", "a medium cat", target_lang="zh", glossary=[("medium", "中档")])
        self.assertEqual(with_slot, "Terms:\nmedium = 中档\na medium cat")
        without_slot = build_custom_prompt("Translate.", "a medium cat", target_lang="zh", glossary=[("medium", "中档")])
        self.assertTrue(without_slot.startswith("Refer to the following translations:\nmedium = 中档\n\nTranslate."))


if __name__ == "__main__":
    unittest.main()
