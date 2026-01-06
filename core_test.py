from core.pipeline import run_pipeline, PipelineOptions, SplitMode, join_translations, join_interleaved

def fake_generate(prompt: str) -> str:
    # 模拟模型输出：故意带 "译文："，测试 postprocess
    return "译文：This is a test translation."

opt = PipelineOptions(split_mode=SplitMode.CONTEXT, keep_debug=False)
pairs = run_pipeline("第一段\n第二段\n第三段", generate=fake_generate, opt=opt)

print("=== joined translations ===")
print(join_translations(pairs))

print("\n=== interleaved ===")
print(join_interleaved(pairs))