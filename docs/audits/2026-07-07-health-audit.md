# Translator 健康审计与 Windows 启动慢诊断

审计日期：2026-07-07  
审计范围：静态代码审查 + macOS 本机命令验证；未在 Windows 真机实测。  
执行原则：本轮只诊断，不做行为变更。
修复状态：fix-1 `ff465ab`（启动性能与可观测性）、fix-2 `d31d386`（翻译正确性）、fix-3 `af931c3`（错误处理与前端状态韧性）、fix-4 `docs/plans/2026-07-07-fix-4-pipeline-unification.md` 对应 worker 分支提交组（管线统一与收尾，最终 main SHA 见队列回写）。

## 摘要

本轮最重要的结论是：Windows 启动慢不应优先归因于 PyInstaller one-file 解压。当前 bridge 发布路径已经是 one-dir：`Translator_bridge_windows.spec:42-66` 使用 `EXE(... exclude_binaries=True ...)` + `COLLECT(...)`，`scripts/build-python-bridge.mjs:12-13` 要求生成 `src-tauri/binaries/translator-bridge/translator-bridge.exe`，`src-tauri/tauri.windows-bridge.conf.json:4-5` 也按目录打包。

更可疑的启动慢来源有四类：

1. 前端首屏 `waitForBackend()` 会主动触发 bridge health/config 路径，见 `src/App.tsx:299-314` 与 `src/lib/api.ts:239-262`。
2. `python_backend/bridge.py:13-15` 在命令分发前预先导入 translation service，导致 `health` / `get-config` 也支付核心翻译模块 import 成本。
3. Windows setup 阶段会立即启动 hotkey sidecar，且失败被吞掉，见 `src-tauri/src/main.rs:1069-1072` 与 `src-tauri/src/hotkey_windows.rs:17-26`。
4. Windows 冷启动仍可能被 WebView2 初始化、UPX 压缩产物、Defender/杀毒扫描和 sidecar 反复 spawn 放大。

功能健康方面，主要风险集中在长文/Markdown 翻译、错误处理、前端状态恢复和配置/历史数据容错。现有 Python 单元测试通过，frontend build 在安装 npm 依赖后通过；Tauri build 因本机无 Rust/Cargo 未验证。

## 启动慢诊断

### 分段路径

1. **Tauri shell 启动**
   - 入口在 `src-tauri/src/main.rs:1057`。
   - 前端资源由 `src-tauri/tauri.conf.json:6-10` 配置。
   - 主窗口由 `src-tauri/tauri.conf.json:12-20` 创建。
   - Windows 上 setup 阶段会调用 `spawn_hotkey_listener`，见 `src-tauri/src/main.rs:1069-1072`。

2. **Python bridge spawn**
   - Rust bridge 命令集中在 `src-tauri/src/main.rs:283-300`。
   - `run_bridge()` 每次 spawn 子进程并 `wait_with_output()` 等待完成，见 `src-tauri/src/main.rs:303-324`。
   - streaming 翻译路径用 `translate-stream` 单独 spawn bridge，见 `src-tauri/src/main.rs:747-760`。
   - Windows hotkey listener 也是 bridge sidecar，见 `src-tauri/src/hotkey_windows.rs:17-26`。

3. **后端 / 模型初始化**
   - `python_backend/bridge.py:13-15` 在任何命令执行前导入 `TranslationService`。
   - `python_backend/services/translation_service.py:6-20` 进一步导入 `backend` 和 `core`。
   - 实际模型请求在 `backend/ollama_backend.py:104-117` 和 `backend/ollama_backend.py:186-200` 才发生；因此 health/config 不应该需要预加载这部分。

4. **前端加载**
   - `src/App.tsx:299-314` mount 后调用 `waitForBackend()`。
   - `src/lib/api.ts:239-262` 的 `waitForBackend()` 会循环调用 `getHealth()` + `getConfig()`，默认最多 12 秒。
   - Tauri runtime 下 `getHealth()` 会走 `backend_status`，`getConfig()` 走 `get_config`，两者都可能触发 bridge。

5. **启动期热键/剪贴板触发**
   - 前端未 ready 时，热键触发会累积在 `pending_clipboard_triggers`，见 `src-tauri/src/main.rs:499-508`。
   - `frontend_ready` 会立刻 flush pending trigger，见 `src-tauri/src/main.rs:607-610`。
   - trigger 处理中有固定 140ms sleep、最多 6 次 eval retry、同步剪贴板读取，见 `src-tauri/src/main.rs:513-565`。

### Windows 特有疑点

- **PyInstaller one-file 解压：低概率。** 当前 bridge 是 one-dir，不是 one-file。不要为了解决启动慢改回 one-file；`AGENTS.md` 已明确禁止。
- **UPX + Defender/杀毒冷扫描：中等概率。** `Translator_bridge_windows.spec:51` 和 `Translator_bridge_windows.spec:63` 对 EXE/COLLECT 均启用 `upx=True`，压缩二进制和大量 sidecar 文件可能放大冷启动扫描。
- **WebView2 初始化：中等概率。** 当前 repo 中没有 WebView2 runtime 策略或启动时间戳；需要 Windows 真机计时确认。
- **bridge spawn 频率：高价值待确认。** 如果每次 health/config/translation/hotkey 都新建 `translator-bridge.exe`，Windows 上的 AV 扫描与进程冷启动会比 macOS 明显。
- **PowerShell / cmd 剪贴板路径：中等概率。** Windows 剪贴板读写分别走 `powershell Get-Clipboard` 与 `cmd /C clip`，见 `src-tauri/src/main.rs:415-421` 和 `src-tauri/src/main.rs:464-480`，这类子进程在热键路径上可能慢。
- **打包资源缺失 fallback：高风险。** `workspace_root()` 使用 build-time `env!("CARGO_MANIFEST_DIR")`，见 `src-tauri/src/main.rs:72-77`；如果 packaged bridge 资源没找到，`bridge_process()` 会 fallback 到源码路径 `python_backend/bridge.py`，见 `src-tauri/src/main.rs:283-300`。发布包中应显式报错，而不是尝试开发机路径。

### macOS 本机 profiling 佐证

- `python3 python_backend/bridge.py health`：约 0.046s，输出 `{"status": "ok", "python": "...python3.14"}`。
- `python3 python_backend/bridge.py get-config`：约 0.047s，输出配置 JSON。
- `python3 python_backend/bridge.py config`：失败；当前命令名是 `get-config`，不是 `config`。
- `npm run tauri:preflight`：失败，缺 `cargo`、`rustc`。

macOS 上 bridge 很快，不代表 Windows packaged bridge 快；但它证明了 health/config 语义上可以很轻，应该避免额外 import 和反复 spawn。

### Windows 机 5 分钟验证步骤

在 Windows 安装包环境里执行：

```powershell
$app = Get-ChildItem "$env:LOCALAPPDATA\Programs","$env:ProgramFiles" -Recurse -Filter Translator.exe -ErrorAction SilentlyContinue | Select-Object -First 1
$bridge = Get-ChildItem (Split-Path $app.FullName) -Recurse -Filter translator-bridge.exe -ErrorAction SilentlyContinue
$app.FullName
$bridge.FullName
```

检查 bridge 是否反复重启：

```powershell
Get-Process Translator,translator-bridge -ErrorAction SilentlyContinue | Select-Object Name,Id,StartTime,Path
```

操作方式：打开 app 后记录一次；触发翻译 2-3 次后再记录。如果 `translator-bridge` PID 每次变，说明 sidecar 频繁 respawn。

比较冷/热启动：

1. 重启 Windows 或结束所有 `Translator` / `translator-bridge` 进程。
2. 计时从点击 Translator 到 UI 可操作。
3. 退出后立即再次打开并计时。
4. 冷启动明显慢、热启动明显快时，优先怀疑 Defender/杀毒/WebView2 冷初始化。

检查 WebView2：

```powershell
winget list "Microsoft Edge WebView2 Runtime"
```

可选验证 Defender/AV 影响：临时对安装目录加排除后重复冷/热启动计时；如果差异显著，优先尝试 `upx=False`、签名和减少 sidecar 文件扫描面。

## Bug 清单

### High

1. **普通模式会破坏缩进、空行和代码/Markdown 结构**
   - 证据：`core/splitter.py:26-30` 使用 `splitlines()` 并默认 `strip()`；桌面 service 在 `python_backend/services/translation_service.py:53` 启用 `strip_each_line=True`。
   - 影响：代码块、缩进列表、blockquote、Markdown 表格续行会丢结构；即便 `python_backend/services/translation_service.py:95-110` 对空白段 passthrough，缩进已经在 splitter 阶段丢失。
   - 建议：splitter 保留原始 span；普通模式识别 fenced code、indented code、table、list continuation，代码段默认 passthrough 或整块处理。

2. **Markdown 模式整篇一次性送模型，超大输入无保护**
   - 证据：`python_backend/services/translation_service.py:69-70` Markdown 直接 `segments = [Segment(text=text, context="")]`；`python_backend/models.py:30-40` 没有 max chars / max segments / timeout 字段。
   - 影响：长文可能上下文溢出、长时间卡住、输出半截，且用户看不到明确限制。
   - 建议：按 Markdown block chunk，保护 code fence/table；增加输入大小、段数、单段 token 预算和用户可读的超限错误。

3. **前端历史 JSON 损坏会导致 React 首屏崩溃**
   - 证据：`src/App.tsx:191-193` 直接 `JSON.parse(saved)`，没有 try/catch 或 shape 校验。
   - 影响：只要 `localStorage.translator_history_v2` 被写坏，应用启动时 UI 可能直接不可用。
   - 建议：try/catch，校验数组结构；坏数据移到 backup key 或清除并继续启动。

4. **packaged bridge fallback 可能解析到 build-time 源码路径**
   - 证据：`src-tauri/src/main.rs:72-77` 使用 `env!("CARGO_MANIFEST_DIR")`；`src-tauri/src/main.rs:112-119` 要求源码树 `python_backend/bridge.py`；`src-tauri/src/main.rs:283-300` 在 Windows resource exe 找不到时 fallback 到脚本路径。
   - 影响：发布包资源异常时，用户看到的是奇怪的 Python/source path 启动失败，而不是明确的 packaged resource missing。
   - 建议：生产模式只使用 resource/app path；source-tree fallback 仅限 dev，并在发布包中给出清晰错误。

5. **启动期 health/config 支付 translation import 成本**
   - 证据：`python_backend/bridge.py:13-15` 顶层导入 `TranslationService`；`python_backend/services/translation_service.py:6-20` 又导入 backend/core；命令分发在 `python_backend/bridge.py:146-160` 之后才发生。
   - 影响：`health`、`get-config`、`save-config`、OCR、hotkey listener 都可能被无关翻译依赖拖慢或拖失败。
   - 建议：把 `TranslationService` / `TranslationRequest` lazy-import 到 translate 命令内部；health/config 保持 stdlib + config/models 级别。

### Medium

6. **timeout / error handling 不够结构化**
   - 证据：local streaming `backend/ollama_backend.py:104-117` 未传超时；HTTP stream `backend/ollama_backend.py:186-207` 只捕获 `HTTPError/URLError`，`json.loads` 可能裸抛；service 在 `python_backend/services/translation_service.py:123-140` 直接迭代 backend。
   - 影响：UI 很难区分模型不存在、Ollama 不可达、JSON 损坏、网络超时、单段失败。
   - 建议：统一 BackendError code；捕获 `TimeoutError`、`json.JSONDecodeError`、`OSError`；分段级事件带结构化错误和可恢复状态。

7. **postprocess 可能误删合法译文内容**
   - 证据：`core/postprocess.py:29-36` 对 marker 用 `rfind`；正文后部出现 `Translation:` / `输出:` 时会截掉前文。`core/postprocess.py:47-48` 分别删除首尾引号，不要求成对。
   - 影响：模型输出包含说明性标签或文本本身包含这些词时，译文可能被错误截断。
   - 建议：marker 只允许出现在开头或约定 wrapper 中；Markdown 模式禁用激进 postprocess；引号只在完整成对包裹时去除。

8. **API server malformed payload 可能不是 JSON 400**
   - 证据：`python_backend/api_server.py:39-45` 和 `python_backend/api_server.py:58-64` 只 catch `ValueError`；`TranslationRequest(**payload)` / `AppConfig(**merged)` 缺字段或多字段时会抛 `TypeError`。
   - 影响：无效请求可能变成 handler traceback 或连接中断。
   - 建议：同时捕获 `TypeError`，或在 request/config 层集中验证字段。

9. **stream polling 失败会让前端卡在 submitting**
   - 证据：`src/App.tsx:426-450` 的 `pollProgress()` 没有 try/catch/finally；`takeTranslationEvents()` reject 时不会清理 `isSubmitting` 与 `currentJobIdRef`。
   - 影响：一次 bridge/event 错误可能让 UI 停在翻译中，需要重启或手动恢复。
   - 建议：循环外包 try/finally；失败时清 job ref、更新 status，并允许用户重新提交。

10. **快速双触发可能启动多个 translation job**
    - 证据：`src/App.tsx:375-377` 依赖 React state `isSubmitting` 做防重入；state 更新前的连续触发仍可能进入。
    - 影响：双击复制或快速按钮操作下可能产生多个 bridge/job，放大启动/翻译延迟。
    - 建议：增加同步 `inFlightRef`，在 async 前立即置位。

11. **Windows hotkey sidecar 在 setup 中同步启动，且失败被忽略**
    - 证据：`src-tauri/src/main.rs:1069-1072` 忽略 `spawn_hotkey_listener` 结果；`src-tauri/src/hotkey_windows.rs:17-26` 会 spawn `hotkey-listener` bridge。
    - 影响：Windows 首启把 hotkey sidecar 成本放在 app setup 期；失败不可见。
    - 建议：前端 ready 后异步启动 hotkey listener；失败写入 backend/status 状态并展示。

12. **Config 损坏会静默重置**
    - 证据：`python_backend/config.py:28-31` 捕获所有异常后返回默认配置。
    - 影响：用户配置突然恢复默认时没有诊断线索。
    - 建议：保留 legacy field 过滤，但对 corrupt JSON/read error 输出 stderr 或结构化 debug 信息。

13. **上下文策略过粗且边界不清**
    - 证据：`core/splitter.py:56-73` 只取前 1-2 行并从末尾硬裁；`core/prompt.py:91` 直接拼接 context/source；Markdown 模式在 `python_backend/services/translation_service.py:47` 禁用 context。
    - 影响：长段落、引用和指代翻译容易不稳定，也有 prompt 污染风险。
    - 建议：按段落/语义块取上下文，使用 `<context>` / `<source>` 边界，并明确“不要翻译上下文”。

14. **service 复刻 core pipeline，实际桌面路径可能与 core 修复漂移**
    - 证据：`core/pipeline.py:104-140` 实现分段/prompt/postprocess；`python_backend/services/translation_service.py:94-140` 手写类似流程。
    - 影响：未来修 core 不一定修到桌面 streaming 路径。
    - 建议：抽 shared streaming pipeline，service 只负责事件包装。

### Low

15. **请求枚举和语言值缺少统一校验**
    - 证据：`python_backend/models.py:30-40` 多数请求字段是裸 string；`python_backend/services/translation_service.py:46-67` 只在部分 enum 转换时才失败。
    - 影响：拼写错误可能静默走默认或产生不一致错误。
    - 建议：在 request 构造处集中 validate，返回用户可读错误。

16. **进度条容器 CSS 缺失**
    - 证据：`src/App.tsx:536` 渲染 `.progress-container`；`src/styles.css:391` 只有 `.progress-bar`，没有 `.progress-container`。
    - 影响：进度条高度/定位不稳定，可能不可见。
    - 建议：补明确的容器高度、位置和 overflow。

17. **复制成功的延迟 status 可能覆盖新状态**
    - 证据：`src/App.tsx:542` `setTimeout(() => setStatus(t("done")), 2000)` 没有 cleanup 或版本检查。
    - 影响：用户复制后马上触发新翻译/错误，2 秒后可能被旧状态覆盖。
    - 建议：timeout ref + cleanup，或 status token/version guard。

18. **NSIS hook 按进程名 broad kill 并固定 sleep**
   - 证据：`src-tauri/windows/installer-hooks.nsh:1-13` kill `translator-bridge.exe` 后固定 `Sleep 500`。
   - 影响：升级/卸载时可能误伤同名进程，且 500ms 不一定足够。
   - 建议：优先 app-owned PID/mutex/window signal；轮询退出，设 bounded timeout。
   - 修复状态：fix-4 已移除 `KillProcess*` 和固定 `Sleep 500`，改为 bounded wait loop；本 worker 未在 Windows installer 上实测。

## 改进机会 Top 10

1. **拆分启动 health/config 与 translation bridge import**
   - 影响：高；成本：低到中。
   - 做法：lazy import translation service；Rust/前端启动只读 Rust-side config 和轻量 health。

2. **给 Windows bridge 增加启动时间戳与阶段日志**
   - 影响：高；成本：低。
   - 做法：记录 app main、setup start/end、window ready、frontend_ready、bridge spawn start/end、first translate start/end。

3. **持久化 bridge sidecar 或减少 per-command spawn**
   - 影响：高；成本：中到高。
   - 做法：如果 Windows 验证确认 PID 频繁变化，改成持久 sidecar + JSON lines 协议或本地 IPC。

4. **Markdown/block-aware splitter**
   - 影响：高；成本：中。
   - 做法：按 block 解析，保护 code fence/table/list continuation，避免逐行 strip 破坏结构。

5. **长文预算与分批策略**
   - 影响：高；成本：中。
   - 做法：max chars、max segments、per-segment token budget、超限提示、分批翻译。

6. **结构化 backend error code**
   - 影响：中高；成本：中。
   - 做法：模型不存在、Ollama 不可达、超时、JSON 损坏、依赖缺失分别映射到稳定 code。

7. **前端启动先显示可用 UI，再后台检测 backend**
   - 影响：中高；成本：中。
   - 做法：首屏用本地/Rust config；backend health 改成非阻塞状态灯。

8. **Windows 打包去 UPX + 签名验证**
   - 影响：中；成本：中。
   - 做法：试 `upx=False`，签名 app/bridge/installer，比较冷/热启动和 Defender 影响。

9. **统一 core pipeline 与 desktop streaming pipeline**
   - 影响：中；成本：中。
   - 做法：抽共享 generator，service 只做 event adapter。

10. **前端持久状态容错**
    - 影响：中；成本：低。
    - 做法：history/config parse guard、schema 校验、坏数据备份与重置。

## 已顺手修复项

无。本轮按队列要求只做诊断报告，没有改运行时代码或行为。

本轮新增文档：

- `docs/plans/2026-07-07-health-audit.md`
- `docs/audits/2026-07-07-health-audit.md`

## 环境限制与未验证项

- 未在 Windows 真机启动安装包，Windows 启动慢结论均为静态分析 + macOS profiling 推断。
- 本机没有 Rust/Cargo：`npm run tauri:preflight` 失败，缺 `cargo`、`rustc`；未运行 `npm run tauri:build` / `npm run tauri:build:windows`。
- 本机没有 `ollama` Python package：`python3 test_pipepline_local.py` 失败于 `ModuleNotFoundError: No module named 'ollama'`，随后包装为 `BackendUnavailableError: Local mode requires pip install ollama.`。
- 未实际调用本地 Ollama 模型生成翻译，因此翻译质量、模型响应时间、真实 streaming 错误恢复未验证。
- 未运行 Windows NSIS installer，也未检查 WebView2 runtime 实际安装状态。
- `npm install` 后 `npm audit` 报 4 个漏洞：1 low、2 moderate、1 high；本轮未展开依赖安全修复。

## 验证记录

环境：

- `python3 --version`：Python 3.14.3
- `/opt/homebrew/bin/node --version`：v25.8.2
- `/opt/homebrew/bin/npm --version`：11.12.1
- `cargo --version`：command not found

命令结果：

- `python3 -m unittest discover -s tests -v`：通过，6 个测试 OK。
- `python3 core_test.py`：完成，输出 joined/interleaved 示例。
- `python3 test_core_pipeline.py`：完成，输出 pairs 和 render 示例。
- `python3 test_core_smoke.py`：通过，输出 `ALL CORE SMOKE TESTS PASSED`。
- `python3 test_context_verify.py`：通过，输出 `context verify OK`。
- `python3 test_pipepline_local.py`：失败，缺 `ollama` Python package；记录为环境限制。
- `time python3 python_backend/bridge.py health`：成功，约 0.046s。
- `time python3 python_backend/bridge.py get-config`：成功，约 0.047s。
- `python3 python_backend/bridge.py config`：失败，当前合法命令为 `get-config`。
- `/opt/homebrew/bin/npm run build:frontend`：首次因 `tsc` 不存在失败；`npm install` 后通过，Vite build 约 449ms。
- `/opt/homebrew/bin/npm run tauri:preflight`：失败，缺 `cargo`、`rustc`。

队列要求验证：

```bash
test -f docs/audits/2026-07-07-health-audit.md
grep -c "启动慢诊断\|Bug 清单\|改进机会\|顺手修复\|环境限制" docs/audits/2026-07-07-health-audit.md
```

预期：第二条输出不小于 5。
