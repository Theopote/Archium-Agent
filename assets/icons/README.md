# Archium Icon Assets

建筑汇报 PPT 语义图标库：**Lucide 风格线稿 + 建筑领域自定义 pictogram**。

## 目录结构

```text
assets/icons/
├── manifest.json          # 注册表 + domain packs
├── embeddings.json        # 离线语义向量（自动生成）
├── architecture/          # 建筑功能、程序、智慧化
├── environment/           # 景观、绿化、生态
├── traffic/               # 交通、流线、停车
├── energy/                # 节能、光伏
└── culture/               # 文化、历史、产业、旅游、社区
```

## 设计规范

| 项 | 值 |
|----|-----|
| 格式 | SVG（bundled，非 npm Lucide 依赖） |
| 风格 | 24×24 viewBox，stroke `#1a1a1a`，`fill=none`，stroke-width 1.75 |
| 许可 | MIT |
| 引用 | `icon:{canonical_name}`，如 `icon:pedestrian_flow` |
| 主题色 | 渲染时描边映射到 `DesignSystem.colors.accent`（源 SVG 保持 `#1a1a1a`） |

Lucide 图标可作为**风格参考**；本库使用自研/定制 SVG，保证离线打包与 PPTX 矢量渲染稳定。

## 主题描边 Recolor

源 SVG 统一使用 pack 默认描边 `#1a1a1a`。导出/预览时按 **DesignSystem**（经 ArtDirection 绑定）动态换色：

| 阶段 | 行为 |
|------|------|
| RenderScene 编译 | `ImageNode.icon_stroke_token = "accent"`，`icon_stroke_color` 解析自 `design.colors.accent` |
| 主题切换 | `theme_scene_resolve.resolve_scene_with_design_system()` 重解析 token，无需改 layout |
| PPTX 导出 | `materialize_recolored_icon()` 写入 `.data/icon_recolor_cache/` 缓存 |
| PNG 预览 | `recolor_icon_svg_text()` 内存换色后 rasterize |

代码入口：

- `archium.application.visual.svg_icon_recolor`
- `archium.application.visual.icon_stroke_resolve`

## 图标规模（v2.1）

共 **33** 个 SVG（roadmap 30+ 已达成）：

| 分类 | 数量 | 示例 |
|------|------|------|
| architecture | 9 | healthcare, residential, office_tower, structural_system |
| environment | 6 | ecology, water_system, natural_ventilation |
| traffic | 7 | pedestrian_flow, bicycle_lane, drop_off_zone |
| energy | 4 | energy_saving, solar_power, wind_power |
| culture | 7 | heritage, tourism, public_space, traditional_craft |

## 领域包（Domain Packs）

预置两类常见建筑项目语义组：

**医院**

| 语义 | 图标 |
|------|------|
| 医疗 | `healthcare` |
| 交通 | `public_transport` |
| 疗愈 | `healing_garden` |
| 绿化 | `green_landscape` |
| 流线 | `pedestrian_flow` |

**村庄**

| 语义 | 图标 |
|------|------|
| 文化 | `heritage` / `community` |
| 历史 | `heritage` |
| 产业 | `local_industry` |
| 生态 | `ecology` |
| 旅游 | `tourism` |

代码：`archium.application.visual.icon_domain_packs`

## 添加新图标

1. 在对应分类目录放置 SVG（遵循 stroke 规范）
2. 在 `manifest.json` 增加条目
3. 重新生成 embeddings（见 `archium/resources/architectural_icons/README.md`）
4. 在 `tests/unit/architectural_icons/` 增加 alias 匹配测试
