# Translator UI Design System: "Content-First Minimalism" (V2)

这套 UI 设计系统旨在通过极致的细节打磨和逻辑布局，为翻译工具建立一套兼具“生产力”与“美感”的视觉标准。

## 1. 核心视觉理念 (Design Soul)
- **对称与平衡 (Symmetry)**：采用 `1fr auto 1fr` 的导航栏布局，确保核心操作（如语言切换）处于视觉绝对中心。
- **呼吸感 (Space)**：通过大圆角 (20px)、充足的内边距 (32px settings padding) 和细致的边框替代粗重的线条。
- **原生高级感 (Native Feel)**：设置项模仿 macOS 系统偏好设置，采用左右对齐布局，输入框文字右对齐且使用等宽字体。

## 2. 色彩与主题 (Theme Engine)
采用 `data-theme` 属性控制，支持 `Light`, `Dark`, `System` 三种模式。

| 元素 | 亮色模式 (Light) | 暗色模式 (Dark) |
| :--- | :--- | :--- |
| **App Background** | `#ffffff` | `#0c0c0e` |
| **Surface (Panels)** | `#f9f9fb` | `#141417` |
| **Accent (Primary)** | `#6366f1` | `#818cf8` |
| **Text (Primary)** | `#1a1a1c` | `#f4f4f5` |
| **Text (Muted)** | `#64748b` | `#a1a1aa` |

## 3. 组件规范 (Components)

### 3.1 语言切换器 (Lang Switcher)
- **容器**：药丸状圆角，固定高度，内含对称的选择框。
- **选择框**：`min-width: 110px`，文字居中对齐，废弃简写（使用 Full Name）。
- **交互**：悬浮时变换边框色，交换按钮具备 0.2s 旋转反馈。

### 3.2 设置面板 (Preferences)
- **布局**：`settings-row` 结构。左侧为 `Name + Description`，右侧为 `Widget (Input/Toggle/Segment)`。
- **输入框**：内置于背景，右对齐，等宽字体，焦点时带有紫色 Halo 阴影。
- **动作按钮**：`height: 48px`，强阴影，明显的点击反馈。

### 3.3 历史抽屉 (History Drawer)
- **交互**：右侧平滑滑入 (`translateX`)，自带半透明遮罩。
- **管理**：支持实时搜索过滤、单条滑动/悬浮删除、一键确认清空。

## 4. 国际化策略 (Internationalization)
- **双语支持**：内置 `I18N` 字典（EN/ZH），支持 UI 全量切换。
- **术语去工程化**：使用用户友好的词汇，如 `Internal Engine` 而非 `local`, `Side-by-Side` 而非 `bilingual`。

## 5. 交互动效 (Motion)
- **进入动画**：Modal 使用 `Scale Fade-in` (0.2s)，Drawer 使用 `Slide-in` (0.3s)。
- **微反馈**：按钮点击时 `scale(0.98)`，切换开关平滑滚动。
- **字体响应**：支持 `12px - 26px` 全动态缩放，布局通过相对单位自动适配。
