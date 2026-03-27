# Translator UI Design System: "Content-First Minimalism"

这套 UI 设计系统旨在通过减少视觉噪音，让用户专注于翻译内容本身。

## 1. 核心理念 (Core Principles)
- **内容为王 (Content-First)**：输入和输出区域应占据 80% 以上的视觉重心。
- **动态呼吸感 (Breathing Space)**：大圆角 (20px)、充足的留白、软阴影。
- **操作隐藏 (Action Hiding)**：非常规操作放入二级菜单或悬浮工具栏，保持界面干净。

## 2. 色彩系统 (Color Palette)
### 亮色模式 (Light)
- `App Background`: #ffffff (纯白，极致干净)
- `Surface`: #f9f9fb (浅灰，用于区分面板)
- `Accent`: #6366f1 (活力紫，主品牌色)
- `Text`: #1a1a1c (深邃黑)

### 暗色模式 (Dark)
- `App Background`: #0c0c0e (深场黑)
- `Surface`: #141417 (略浅的黑色背景)
- `Accent`: #818cf8 (高明度紫)
- `Text`: #f4f4f5 (米白色，降低视觉疲劳)

## 3. 交互规范 (Interaction)
- **输入即反馈**：翻译时使用进度条而非全屏 Loading。
- **毛玻璃 (Glassmorphism)**：弹窗和悬浮工具栏应具备 8-12px 的背景模糊，增加层次感。
- **微动效**：按钮点击时应有轻微的缩放反馈 (Scale 0.98)。

## 4. 术语转换 (User-Facing Terms)
- `local` (mode) -> **"App Engine"** (内置引擎)
- `ollama` (mode) -> **"System Server"** (系统服务)
- `use_context` -> **"Smart Context"** (智能上下文)
- `collapse_newlines` -> **"Compact Mode"** (紧凑模式)
- `output_mode` -> **"Bilingual Output"** (双语显示选项)
