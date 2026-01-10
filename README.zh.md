# Translator (Ollama Desktop)

[English Readme](./README.md)

本项目是一个本地翻译桌面工具，核心流程是：全局热键触发 → 读取剪贴板 → 发送到本地 Ollama → UI 显示译文。  
它不训练模型，只调用 Ollama 中的量化模型（如 GGUF）进行推理。

## 解决的问题

传统翻译流程需要来回切换应用、粘贴、等待结果。本项目把这个流程缩短为“复制两次即可翻译”，适合日常阅读与工作场景。

## 功能特性

- 全局热键触发（Windows: Ctrl+C Ctrl+C；macOS: Cmd+C Cmd+C）
- 两种输出模式：`translations_only` / `interleaved`
- 支持布局切换（vertical / horizontal）
- 支持上下文分段翻译（Use Context）
- OCR 识别图片粘贴文本（见下方说明）
- 本地优先：默认使用本机 Ollama
- 可切换 HTTP 模式，支持远程或 NAS 上的 Ollama 服务

## 架构概览（文字说明）

UI 层（平台相关）
→ 监听热键、读取剪贴板、弹出 UI

Backend / 推理层
→ 本地 Ollama 服务
→ 加载量化模型
→ 返回译文

本项目不包含训练或微调流程。

## 翻译质量策略

- 使用严格翻译提示词，尽量只输出译文
- 通过分段与后处理提升稳定性
- 目标是日常使用体验接近 DeepL，但不做夸大承诺

## OCR 说明

- macOS：使用系统 Vision OCR
- Windows：使用 WinRT OCR（依赖系统 OCR 语言包）
- 如果系统未安装对应 OCR 语言包，图片粘贴可能无法识别
- OCR 仅在图片粘贴时触发，不影响纯文本粘贴

## 平台说明

- Windows 端的 “Local” 模式内部会走 HTTP（127.0.0.1），用于避免 Python 客户端在 Windows 上卡住的情况
- macOS 端直接使用本地客户端

## 配置持久化

- macOS：配置存储在 `~/Library/Application Support/Translator/ui_config.json`
- Windows：配置存储在 `%APPDATA%/Translator/ui_config.json`

## 限制与取舍

- 翻译质量依赖所选模型
- 长文本质量依赖分段策略
- OCR 依赖系统语言包，可能需要手动安装

## Roadmap

- 更好的长文本分段与上下文控制
- 术语表/词汇控制
- 进一步抽象后端，方便切换到其他引擎
