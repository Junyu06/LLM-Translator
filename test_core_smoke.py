from core.splitter import split_plain, split_with_limited_context, SplitOptions, ContextOptions
from core.prompt import build_prompt, PromptOptions, PromptPreset, TerminologyHint
from core.postprocess import extract_translation
from core.lang import normalize_lang, display_lang


def fake_llm(prompt: str, mode: str) -> str:
    """
    模拟不同“模型输出”风格，用来压测 postprocess。
    """
    if mode == "clean":
        return "This is a local translation engine."
    if mode == "with_marker":
        return "译文：This is a local translation engine."
    if mode == "echo_prompt":
        return prompt + "\n译文：This is a local translation engine."
    if mode == "multi_marker":
        return "译文：foo\n译文：This is a local translation engine."
    if mode == "quoted":
        return "“This is a local translation engine.”"
    if mode == "messy":
        return f"{prompt}\nI will translate it.\n译文: This is a local translation engine.\n(Explanation omitted)"
    return "This is a local translation engine."


def run_case(title: str, source_text: str, opt: PromptOptions, fake_mode: str):
    prompt = build_prompt(source_text, opt)
    raw = fake_llm(prompt, fake_mode)
    cleaned = extract_translation(raw)

    print("\n" + "=" * 80)
    print("CASE:", title)
    print("source_lang:", opt.source_lang, "target_lang:", opt.target_lang, "preset:", opt.preset)
    print("\nPROMPT:\n", prompt)
    print("\nRAW:\n", raw)
    print("\nCLEANED:\n", cleaned)


def main():
    # 0) lang 工具 sanity
    assert normalize_lang("ZH-cn") == "zh"
    assert normalize_lang("English") == "en"
    assert display_lang("ja") == "Japanese"

    # 1) splitter：默认去空行 + strip
    text = "第一行\n\n  第二行  \n第三行\n"
    segs = split_plain(text, SplitOptions(strip_each_line=True, drop_empty_lines=True))
    assert [s.text for s in segs] == ["第一行", "第二行", "第三行"]
    assert all(s.context == "" for s in segs)
    print("split_plain OK:", [s.text for s in segs])

    # 2) splitter：带有限上文
    ctx_segs = split_with_limited_context(
        "短句\n这是一个比较长的句子，用来触发只用上一段的情况。\n第三句",
        ctx_opt=ContextOptions(min_context_chars=10, max_context_chars=200),
    )
    assert ctx_segs[0].context == ""
    assert ctx_segs[1].context == "短句"
    assert ctx_segs[2].context.endswith("这是一个比较长的句子，用来触发只用上一段的情况。")
    print("split_with_limited_context OK")

    # 2) prompt AUTO 路由：含中文 -> ZH 模板；不含中文 -> EN 模板
    run_case(
        "AUTO zh->en should use ZH_XX template",
        "這是一個運行在本地的強大翻譯引擎。",
        PromptOptions(source_lang="zh", target_lang="en", preset=PromptPreset.AUTO),
        "echo_prompt",
    )
    assert "将以下文本翻译为English" in build_prompt(
        "這是一個運行在本地的強大翻譯引擎。",
        PromptOptions(source_lang="zh", target_lang="en", preset=PromptPreset.AUTO),
    )

    run_case(
        "AUTO en->ja should use XX_XX template",
        "This is a powerful local translation engine.",
        PromptOptions(source_lang="en", target_lang="ja", preset=PromptPreset.AUTO),
        "with_marker",
    )
    assert "Translate the following segment into Japanese" in build_prompt(
        "This is a powerful local translation engine.",
        PromptOptions(source_lang="en", target_lang="ja", preset=PromptPreset.AUTO),
    )

    # 3) terminology 模板
    run_case(
        "TERMINOLOGY template",
        "这块显卡很强。",
        PromptOptions(
            source_lang="zh",
            target_lang="en",
            preset=PromptPreset.TERMINOLOGY,
            terminology=TerminologyHint("显卡", "GPU"),
        ),
        "messy",
    )
    assert "显卡 翻译成 GPU" in build_prompt(
        "这块显卡很强。",
        PromptOptions(
            source_lang="zh",
            target_lang="en",
            preset=PromptPreset.TERMINOLOGY,
            terminology=TerminologyHint("显卡", "GPU"),
        ),
    )

    # 4) contextual 模板
    run_case(
        "CONTEXTUAL template",
        "它的定价策略是什么？",
        PromptOptions(
            source_lang="zh",
            target_lang="en",
            preset=PromptPreset.CONTEXTUAL,
            context="上文介绍了某公司产品线与定价策略。",
        ),
        "multi_marker",
    )
    assert "参考上面的信息" in build_prompt(
        "它的定价策略是什么？",
        PromptOptions(
            source_lang="zh",
            target_lang="en",
            preset=PromptPreset.CONTEXTUAL,
            context="上文介绍了某公司产品线与定价策略。",
        ),
    )

    # 5) formatted 模板（只验证 prompt 结构）
    run_case(
        "FORMATTED_ZH template",
        "",
        PromptOptions(
            source_lang="en",
            target_lang="zh",
            preset=PromptPreset.FORMATTED_ZH,
            src_text_with_format="Hello <sn>World</sn>!",
        ),
        "clean",
    )
    assert "<source>Hello <sn>World</sn>!</source>" in build_prompt(
        "",
        PromptOptions(
            source_lang="en",
            target_lang="zh",
            preset=PromptPreset.FORMATTED_ZH,
            src_text_with_format="Hello <sn>World</sn>!",
        ),
    )

    # 6) postprocess 典型鲁棒性
    for mode in ["clean", "with_marker", "echo_prompt", "multi_marker", "quoted", "messy"]:
        raw = fake_llm("原文：X\n译文：", mode)
        cleaned = extract_translation(raw)
        assert cleaned != ""
        print(f"postprocess mode={mode} -> {cleaned}")

    print("\nALL CORE SMOKE TESTS PASSED ✅")


if __name__ == "__main__":
    main()
