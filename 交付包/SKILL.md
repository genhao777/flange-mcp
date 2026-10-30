# 油田法兰 MCP Skill

## 适用场景

当用户要生成简单的油田管线法兰、垫片或类似带孔圆盘零件时，先把自然语言整理成明确的毫米规格，再调用 MCP 工具。

当前版本只支持：

- 带中心孔的圆形法兰；
- 等距分布的圆周螺栓孔；
- 六个参数：外径、厚度、中心孔直径、孔数、螺栓孔直径、分布圆直径。
- 一个受限的油田管线装配模板：法兰—管段—法兰短节，可选两片环形垫片。

## 推荐调用顺序

1. 调用 `part_catalog` 确认参数名、单位和默认值。
2. 如果缺少关键尺寸，先向用户询问；不要猜测。
3. 调用 `part_create` 生成实体。
4. 调用 `part_check`，逐项展示期望值、实际值和通过状态。
5. 调用 `drawing_make` 生成 DXF、PDF 和 PNG。
6. 返回产物路径、检查报告和需要人工审核的提示。
7. 如果输入使用英寸，传递 `units: "in"`；服务会在规格表和实体内部统一使用毫米。
8. 如果用户要求连接管线，保留同一个 `part_id`，在 `drawing_make` 中增加 `"assembly": {"pipe_od": 40, "pipe_id": 32, "pipe_length": 120, "include_end_flange": true, "include_gaskets": true, "gasket": {"outer_diameter": 88, "inner_diameter": 42, "thickness": 3}}` 配置，并把 `assembly` 加入 `formats`，检查五组件、四个连接面、同轴、端面贴合、螺栓孔对齐、接口间隙、`axis_continuous` 和 `min_bore_mm`。垫片外径不得超过 `pcd - bolt_diameter`，否则返回 `GASKET_COVERS_BOLT_HOLES`。

## 规格映射

| 用户说法 | 参数 |
| --- | --- |
| 外径、法兰直径 | `od` |
| 厚度 | `thickness` |
| 中心孔、通孔 | `center_hole` |
| 几个螺栓孔 | `bolt_count` |
| 螺栓孔直径 | `bolt_diameter` |
| 螺栓孔分布圆、PCD | `pcd` |

## 成功标准

- 体积相对误差不超过 `1e-6`；
- 包围盒、实体数和圆柱面数量通过；
- 产物写入同一个 `out/flange_<part_id>/` 目录；
- DXF 至少包含原生 `DIMENSION` 实体；
- PDF 是由实际 STEP 实体投影得到的矢量线稿，PNG 是同一投影的预览图；`flange_render.png` 是由同一 B-rep 三角网格着色得到的展示图，`flange_viewer.html` 提供离线旋转、缩放和面片选中。所有图纸仍需人工审核后才能用于加工。
- 组合演示会额外生成 `flange_spool.step`、`flange_spool.stl`、`flange_spool_viewer.html`、`assembly.json` 和 `delivery_manifest.json`；装配检查只覆盖本模板明确声明的连接关系，并从实际组件几何读取检查结果。
- 规则筛查返回稳定的 `fault_type` 和 `warnings`，不把工程建议包装成标准合规结论。

## 边界

当前版本不声称符合 API、GB 或其他加工标准，不支持通用装配约束求解、复杂曲面、DWG、手绘图转三维或内部盖亚系统接入。


## 投影保证

- DXF、PDF、PNG 的几何线条来自已交付 STEP 的 build123d HLR 投影；
- PDF 是矢量线稿，不把 PNG 作为 PDF 背景图；
