from core import run_pipeline, PipelineOptions, SplitMode
from backend import OllamaBackend, OllamaBackendOptions, OllamaMode

backend = OllamaBackend(OllamaBackendOptions(
    mode=OllamaMode.LOCAL,
    model="gemma3:27b",
    options={"temperature": 0.0},
))

opt = PipelineOptions(split_mode=SplitMode.PLAIN, keep_debug=True)
opt.prompt_opt.source_lang = "zh"
opt.prompt_opt.target_lang = "en"

pairs = run_pipeline("这是一段测试代码。\nIt should be translated into English.", backend.generate, opt)

for i, p in enumerate(pairs):
    print("\n" + "="*60)
    print("SEG", i)
    print("PROMPT:\n", p.prompt)
    print("RAW:\n", p.raw)
    print("EXTRACTED TARGET:\n", p.target)