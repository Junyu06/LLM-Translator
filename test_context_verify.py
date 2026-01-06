from core import run_pipeline, PipelineOptions, SplitMode
from core.splitter import ContextOptions


def fake_generate(prompt: str) -> str:
    return prompt + "\n译文：OK"


def main():
    text = "短句\n也短\n这是一个比较长的句子，用来确保后续只用上一段。\n第四句"

    # 1) 关闭上文
    opt_plain = PipelineOptions(split_mode=SplitMode.PLAIN)
    pairs_plain, report_plain = run_pipeline(
        text,
        generate=fake_generate,
        opt=opt_plain,
        return_report=True,
    )
    assert report_plain.context_success_rate() == 1.0
    assert all(not r.expected_context.strip() for r in report_plain.reports)

    # 2) 开启上文，且短句触发“补上上段”
    opt_ctx = PipelineOptions(split_mode=SplitMode.CONTEXT)
    opt_ctx.ctx_opt = ContextOptions(min_context_chars=10, max_context_chars=200)
    pairs_ctx, report_ctx = run_pipeline(
        text,
        generate=fake_generate,
        opt=opt_ctx,
        return_report=True,
    )

    # 第2段应该带上第1段
    assert report_ctx.reports[1].expected_context.strip() == "短句"
    # 第3段应该带上第1+2段（因为第2段太短）
    assert report_ctx.reports[2].expected_context.strip() == "短句\n也短"
    # 第4段只需要上一段（第3段足够长）
    assert report_ctx.reports[3].expected_context.strip().endswith("这是一个比较长的句子，用来确保后续只用上一段。")

    assert report_ctx.context_success_rate() == 1.0

    print("context verify OK")


if __name__ == "__main__":
    main()
