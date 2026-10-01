import unittest

from core.splitter import split_paragraphs


def texts(text):
    return [segment.text for segment in split_paragraphs(text)]


class ReflowTests(unittest.TestCase):
    def test_pdf_lines_broken_mid_sentence_are_joined(self):
        text = (
            "Large language models are typically served with a fixed context window, and the\n"
            "memory required for the key-value cache grows linearly with both the number of\n"
            "concurrent requests and the length of each sequence. In practice this means that\n"
            "a server tuned for short chat turns can fail abruptly."
        )
        self.assertEqual(len(texts(text)), 1)
        self.assertIn("window, and the memory required", texts(text)[0])

    def test_one_paragraph_per_line_is_kept(self):
        text = "First paragraph ends here.\nSecond paragraph ends here too.\nThird."
        self.assertEqual(texts(text), ["First paragraph ends here.", "Second paragraph ends here too.", "Third."])

    def test_short_heading_lines_are_not_joined(self):
        text = "Release notes\nFixed\nThe cache no longer drops entries when a key is evicted twice."
        self.assertEqual(len(texts(text)), 3)

    def test_list_items_are_not_joined(self):
        text = (
            "We changed three things in this release of the gateway and the scheduler\n"
            "- the queue is bounded\n"
            "- retries back off exponentially"
        )
        self.assertEqual(len(texts(text)), 3)

    def test_wrapped_chinese_lines_join_without_space(self):
        text = "我们组上周把内部的翻译工具从混元换成了 Index，主要是看中它对网络\n用语的处理，测试下来效果还不错。"
        self.assertEqual(texts(text), ["我们组上周把内部的翻译工具从混元换成了 Index，主要是看中它对网络用语的处理，测试下来效果还不错。"])

    def test_blank_lines_are_kept_as_passthrough(self):
        segments = split_paragraphs("One.\n\nTwo.")
        self.assertEqual([(s.text, s.kind) for s in segments], [("One.", "text"), ("", "blank"), ("Two.", "text")])
        self.assertFalse(segments[1].translatable)


if __name__ == "__main__":
    unittest.main()
