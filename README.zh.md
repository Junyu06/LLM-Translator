# Translator (Ollama Desktop)

[English Readme](./README.md)

本项目是一个桌面翻译工具：连按两次复制 → 读取剪贴板（文字直接用，图片先做 OCR）→ 交给 Ollama 上的模型翻译 → 在界面里显示译文。
它不训练模型，只调用 Ollama 里已有的模型做推理。

![Translator 主界面](./docs/images/main-window-markdown-mode.png)

## 功能

- 全局热键：macOS 是 Cmd+C Cmd+C，Windows 是 Ctrl+C Ctrl+C。结果显示在鼠标旁边的小窗里（复制、在主窗口打开、按 Esc 回到原来的应用）；关掉这个设置则打开主窗口
- 只看译文，或者对照：每段原文下面跟着它的译文
- 每一段可以：就地显示原文、复制、单独重翻
- 术语表：给术语定固定译法，只有文中出现的术语才发给模型
- Markdown 模式保留标题、列表、引用和表格（按 GitHub 的样式显示），代码原样不动
- 剪贴板里是图片时，热键、剪贴板按钮、托盘菜单、粘贴到原文框，四个入口都会先做 OCR
- Ollama 可以在本机，也可以在别的机器上

## 翻译怎么做

小型翻译模型看到整段上下文时，人名和术语前后更一致，也比一段一个请求快。所以 Translator：

1. 先把一句话被拆成几行的文本（PDF 复制、OCR 结果）合回段落。
2. 把连续的段落凑成约 700 token 一块，每块一次请求发出去，段落之间空一行；上一块最后几段的原文和译文作为前一轮对话带上。
3. 把译文按段切开，和原文一一配对。模型合并或拆分了段落时，这一块改成一段一段重翻，对照不会错位。

提示词按各模型的模型卡来写。模型名认不出来时，可以在设置里手动指定家族，也可以写自定义模板，占位符有 `{text}`、`{target_lang}`、`{target_lang_zh}`、`{glossary}`。

| 模型家族 | 从模型名里识别 | 提示词 |
|---|---|---|
| Index-Translate（哔哩哔哩） | `index-translate` | `请将以下文本翻译为{目标语言}，直接输出翻译结果，不要进行任何解释。` |
| Hy-MT / HY-MT / Hunyuan-MT（腾讯） | `hy-mt`、`hunyuan-mt` | `将以下文本翻译为{目标语言}，注意只需要输出翻译后的结果，不要额外解释：` |
| 其他模型 | | 一句普通的英文指令 |

术语表按各家族文档里的写法发：Index-Translate 用 `要求：术语使用固定译法（…）`，Hy-MT 用 `参考下面的翻译：{原文} 翻译成 {译文}`。

Markdown 用 markdown-it-py 分块，和界面显示用的是同一套 CommonMark 规则。代码、HTML 块、分隔线、链接定义不发给模型；引用式链接先改写成行内链接。

请求都带 `think: false`。Ollama 把 Index-Translate 当作推理模型，不带这个参数时渲染出的输入和模型训练时的格式不一致。

## OCR

- macOS：系统 Vision OCR，自动识别语言
- Windows：WinRT OCR（依赖系统 OCR 语言包）

剪贴板里同时有文字和图片时（Office 会这样放），用文字；文字只是这张图的文件名或网址时，用图片。

## 配置

- macOS：`~/Library/Application Support/Translator/ui_config.json`
- Windows：`%APPDATA%/Translator/ui_config.json`
- 配置文件读不出来时，Translator 把它挪到旁边一个不覆盖旧备份的 `.corrupt` 文件，然后用默认配置。

## 架构

- `src/`：React 界面
- `src-tauri/`：Tauri 外壳：窗口、托盘、全局热键，以及调用 Python bridge 的命令
- `python_backend/bridge.py`：每个命令一个进程（`translate-stream`、`read-clipboard`、`list-models` 等），通过 stdout 输出 JSON
- `core/`：分段、提示词、分块翻译管线
- `backend/`：Ollama HTTP 客户端
- `ui_mac/ocr.py`、`ui_windows/`：OCR 和 Windows 热键监听

正式版把用 PyInstaller 打好的 bridge 放进 app 的资源目录：`npm run build:macos`、`npm run build:windows`（见 `AGENTS.md`）。macOS 上不带它的版本（`npm run tauri:dev`、直接 `tauri build`）从本仓库 checkout 的 `.venv` 调用 bridge；编译时设置 `TRANSLATOR_BACKEND_ROOT` 可以指向别的 checkout。

## 开发验证

```bash
python3 -m unittest discover -s tests -v
npm run build:frontend
cargo check --manifest-path src-tauri/Cargo.toml
npm run tauri:dev
```

`python3 python_backend/api_server.py` 在 8765 端口用 HTTP 提供同样的后端，配合 `npm run dev` 可以在浏览器里跑界面。

设置 `TRANSLATOR_STARTUP_LOG=1`，并可选设置 `TRANSLATOR_STARTUP_LOG_FILE=<path>`，可以查看 Python bridge 启动阶段日志。

## 限制

- 翻译质量取决于模型
- OCR 依赖系统语言包
- OCR 按 Vision 返回的顺序给出各行，多栏截图可能交错

## Roadmap

- 翻译图片里的文字，并把译文贴回图上
- 用 Vision 的 `RecognizeDocumentsRequest` 做带文档结构（段落、分栏）的 OCR
