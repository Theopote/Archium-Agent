# Design System

`DesignSystem` 是可版本化的视觉规范：页面尺寸、边距、网格、字体、颜色、间距、图片与页脚策略、布局阈值。

## 模型位置

- Domain：`archium/domain/visual/design_system.py`
- 默认预设：`archium/domain/visual/defaults.py`（`default_presentation_design_system()`）
- 仓储：`DesignSystemRepository`（JSON payload）
- 主题桥接（遗留模板路径）：`design_system_to_pptx_theme()`

## 默认预设：architecture-board

从既有 `pptxgen/core/theme.mjs` 的 `architecture-board` 令牌迁移而来：

| 项 | 默认值 |
|----|--------|
| 页面 | 10 × 5.625 in（16:9） |
| 边距 | 上/下 0.45，左/右 0.7 |
| 网格 | 12 栏 column grid |
| 正文字号 | 16 pt |
| 图片 | 图纸 `contain` + 保比例；照片可 `cover` |

## 主要子系统

| 子系统 | 作用 |
|--------|------|
| `PageSystem` | 宽高、边距、安全区 |
| `GridSystem` | 栏数、沟槽、网格类型 |
| `TypographySystem` | display / title / subtitle / heading / body / caption / metric / footnote / source |
| `ColorSystem` | 命名色；`resolve(token)` |
| `SpacingSystem` | xs…xxl 语义间距 |
| `ImageStyleSystem` | fit / crop / 图纸保比例 |
| `FooterStyleSystem` | 页脚与页码 |
| `LayoutThresholds` | 最小字号、主视觉面积比、留白上下限 |

## 与 ArtDirection / Style Preset 的分工

| 对象 | 回答的问题 |
|------|------------|
| DesignSystem | 「用什么令牌与阈值？」 |
| **Style Preset** | 「哪种建筑事务所气质？」（可执行令牌覆盖） |
| ArtDirection | 「这套汇报的视觉概念、语气与策略是什么？」 |

### Style Preset（v0.3）

- Domain：`archium/domain/visual/style/`
- 六个内置：`architecture_minimal` / `technical` / `luxury` / `academic` / `urban` / `landscape`
- 默认：`architecture_technical`
- 通过 `ArtDirection.style_preset_id` 绑定；`apply_style_overlays` 在 ArtDirection 自由文本启发式之前应用
- **不**改写持久化 DesignSystem 行；布局生成与 RenderScene 编译使用内存覆盖结果

ArtDirection 引用一个 `design_system_id`，并可绑定 `style_preset_id` 与策略叙述（色彩/字体/图纸/节奏等），但不改写绝对坐标。

详见 [Presentation Engine v0.3](../roadmap/presentation-engine-v0.3.md)。

## 配置覆盖

Settings（环境变量）可覆盖校验阈值，例如：

- `LAYOUT_MIN_BODY_FONT_PT`
- `LAYOUT_MIN_CAPTION_FONT_PT`
- `LAYOUT_MIN_SOURCE_FONT_PT`
- `LAYOUT_MIN_HERO_AREA_RATIO`
- `LAYOUT_MIN_WHITESPACE_RATIO` / `LAYOUT_MAX_WHITESPACE_RATIO`

详见 [configuration-reference](../configuration-reference.md)。

## Round 1 边界

- 不做组织品牌模板导入或 PPT 母版逆向。
- 遗留 `theme.mjs` 命名主题仍服务 PresentationSpec 路径；视觉编排以 DesignSystem 为准。
