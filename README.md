# Translator (Ollama Desktop)

Translator is a desktop translation tool built on top of Ollama.

![Translator main window](./docs/images/main-window-markdown-mode.png)

Its core workflow is:

**Copy twice → read the clipboard (text, or an image through OCR) → translate with an Ollama model → show the translation**

This project does **not** train or fine-tune models.
It only runs inference against models already available in Ollama.

[中文说明](./README.zh.md)

---

## Features

- Global hotkey: `Cmd+C Cmd+C` on macOS, `Ctrl+C Ctrl+C` on Windows
- Translation only, or side by side with each source paragraph above its translation
- Markdown mode keeps headings, lists, quotes and tables, and leaves code untouched
- Images on the clipboard go through system OCR from every entry point: the hotkey, the clipboard button, the tray menu, and pasting into the source box
- Ollama on this machine or on another host

## How translation works

Small translation models keep names and terms consistent across a passage when they see the whole passage, and they are faster that way than with one request per paragraph. So Translator:

1. Joins lines broken in the middle of a sentence (text copied from a PDF, OCR output) back into paragraphs.
2. Groups consecutive paragraphs into chunks of about 700 tokens and sends each chunk in one request, paragraphs separated by blank lines. The last paragraphs of the previous chunk go along as an earlier chat turn.
3. Splits the reply back into paragraphs and pairs each with its source. If the model merged or split paragraphs, that chunk is translated again one paragraph at a time, so pairs never drift.

Prompts follow each model's card:

| Model family | Detected from the model name | Prompt |
|---|---|---|
| Index-Translate (bilibili) | `index-translate` | `请将以下文本翻译为{目标语言}，直接输出翻译结果，不要进行任何解释。` |
| Hy-MT / HY-MT / Hunyuan-MT (Tencent) | `hy-mt`, `hunyuan-mt` | `将以下文本翻译为{目标语言}，注意只需要输出翻译后的结果，不要额外解释：` |
| Anything else | | A plain English instruction |

Requests send `think: false`. Ollama treats Index-Translate as a reasoning model, and without the flag the prompt it renders differs from the format the model was trained on.

## OCR

- **macOS**: system Vision OCR
- **Windows**: WinRT OCR (requires the system OCR language packs)

When the clipboard holds both text and a picture (Office does this), the text wins. A picture wins when the only text is its file name or URL.

## Configuration

- **macOS**: `~/Library/Application Support/Translator/ui_config.json`
- **Windows**: `%APPDATA%/Translator/ui_config.json`

If the config file is unreadable, Translator moves it aside with a no-clobber `.corrupt` suffix and loads defaults.

## Architecture

- `src/`: React UI
- `src-tauri/`: Tauri shell: window, tray, global hotkey, and the commands that run the Python bridge
- `python_backend/bridge.py`: one process per command (`translate-stream`, `read-clipboard`, `list-models`, …), JSON over stdout
- `core/`: splitting, prompts, chunked translation pipeline
- `backend/`: Ollama HTTP client
- `ui_mac/ocr.py`, `ui_windows/`: OCR and the Windows hotkey listener

On macOS the app runs the bridge from a checkout of this repository with its `.venv`. By default that is the checkout the app was built from; set `TRANSLATOR_BACKEND_ROOT` at build time to point at another one. Windows builds bundle the bridge (see `AGENTS.md`).

## Development

```bash
python3 -m unittest discover -s tests -v
npm run build:frontend
cargo check --manifest-path src-tauri/Cargo.toml
npm run tauri:dev
```

`python3 python_backend/api_server.py` serves the same backend over HTTP on port 8765 for running the UI in a browser with `npm run dev`.

Set `TRANSLATOR_STARTUP_LOG=1` and optionally `TRANSLATOR_STARTUP_LOG_FILE=<path>` to inspect Python bridge startup stages.

## Limitations

- Translation quality depends on the model
- OCR relies on system language packs
- Markdown tables are translated but render as plain text

## Roadmap

- Glossary / terminology control
- Re-translate or copy a single paragraph
- A small quick-translate window for the hotkey
