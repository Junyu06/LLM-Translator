# Translator (Ollama Desktop)

Translator is a local desktop translation tool built on top of Ollama.

Its core workflow is:

**Global hotkey → Read clipboard → Send text to local Ollama → Display translation in UI**

This project does **not** train or fine-tune models.  
It only performs inference by calling quantized models (e.g. GGUF) already available in Ollama.

[中文说明](./README.zh.md)

---

## Problem It Solves

Traditional translation workflows require switching applications, pasting text, and waiting for results.

Translator reduces this friction to a single action:  
**copy text twice to get an instant translation**, making it well suited for daily reading and work scenarios.

---

## Features

- Global hotkey trigger  
  - Windows: `Ctrl + C, Ctrl + C`  
  - macOS: `Cmd + C, Cmd + C`
- Two output modes:
  - `translations_only`
  - `interleaved`
- Layout switching:
  - vertical / horizontal
- Context-aware segmented translation (`Use Context`)
- OCR support for image clipboard content (see below)
- Local-first design:
  - Uses local Ollama by default
- HTTP mode support:
  - Allows connecting to remote or NAS-hosted Ollama services

---

## Architecture Overview

**UI Layer (platform-specific)**  
→ Listens for global hotkeys  
→ Reads clipboard content  
→ Displays translation UI

**Backend / Inference Layer**  
→ Local Ollama service  
→ Loads quantized models  
→ Returns translated text

This project does **not** include any training or fine-tuning pipeline.

---

## Translation Quality Strategy

- Uses strict translation prompts to minimize non-translation output
- Improves stability through segmentation and post-processing
- The goal is to achieve a daily-use experience close to DeepL  
  (without exaggerated quality claims)

---

## OCR Support

- **macOS**: Uses system Vision OCR
- **Windows**: Uses WinRT OCR (requires installed system OCR language packs)

Notes:
- If the required OCR language pack is not installed, image clipboard text may not be recognized
- OCR is only triggered for image clipboard content
- Plain text clipboard usage is unaffected

---

## Platform Notes

- On **Windows**, the “Local” mode internally uses HTTP (`127.0.0.1`)  
  to avoid potential blocking issues with the Python client
- On **macOS**, the local Ollama client is used directly

---

## Configuration Persistence

- **macOS**:  
  `~/Library/Application Support/Translator/ui_config.json`
- **Windows**:  
  `%APPDATA%/Translator/ui_config.json`

---

## Limitations & Trade-offs

- Translation quality depends on the selected model
- Long-text quality depends on segmentation strategy
- OCR relies on system language packs and may require manual installation

---

## Roadmap

- Improved long-text segmentation and context control
- Glossary / terminology control
- Further backend abstraction to support alternative inference engines
