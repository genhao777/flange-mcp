# 油田法兰 MCP Demo

这是一个面向油田管线法兰场景的最小验证原型，覆盖参数化建模、几何核对、B-rep 投影出图、MCP 调用和可交互的装配查看。

## 先看这 4 个链接

1. [单件法兰 PDF 图纸](演示样例/单件法兰/flange.pdf)
2. [法兰短节 3D 交互查看器](演示样例/法兰短节/flange_spool_viewer.html)
3. [法兰短节装配检查报告](演示样例/法兰短节/assembly.json)
4. [独立垫片 PDF 图纸](演示样例/独立垫片/gasket.pdf)

## 当前状态

当前最小闭环已经完成：参数化实体、体积和拓扑核对、MCP stdio 工具、STEP B-rep 三视图投影，以及 DXF/PDF/PNG、等轴测展示图和离线交互式 3D 查看器交付。另有受限的“法兰—管段—法兰”装配模板，并支持两片真实环形垫片。

## 交付目录

- `src/`：MCP 服务和参数化几何代码。
- `scripts/`：建模、出图、worker、启动和验收脚本。
- `docs/task-log.md`：验收记录。现场屏幕展示稿和 AI 提示词属于演示辅助材料，不纳入交付包。
- `演示样例/单件法兰/`：单件法兰的 STEP、STL、DXF、PDF、PNG、3D 查看器和核对记录。
- `演示样例/法兰短节/`：五组件法兰短节的 STEP、STL、交互查看器、装配检查报告和交付清单。
- `演示样例/独立垫片/`：可单独生成的垫片 STEP、STL、DXF、PDF、PNG 和核对记录。

最终提交不包含 `.venv/`、`out/` 下的历史运行目录、临时缓存，以及个人简历、Word 参考材料等与项目无关的附件。

`ceshi` 是现场演示归档目录：在 part_create、part_check、drawing_make 中传入 `output_dir=C:\Users\musiu\Desktop\ceshi\油田法兰短节演示`，让 MCP 直接生成到现场目录；`out/` 只保留未指定 output_dir 时的默认运行产物。

## 运行方式

建议在本目录创建独立虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH = "$PWD\src"
python scripts\day1_baseline.py
```

默认法兰规格：外径 OD 120 mm、厚度 T 15 mm、中心孔 40 mm、螺栓孔数量 4、螺栓孔直径 12 mm、螺栓孔分布圆 PCD 90 mm。

## MCP 启动与验收

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m flange_mcp.server
python scripts\mcp_smoke.py
.\scripts\run_mcp.ps1 -SmokeTest
.\scripts\verify_release.ps1
```

MCP 服务名为 `oilfield-flange`，通过 stdio 提供 `part_catalog`、`part_create`、`part_check`、`drawing_make` 四个工具。长度参数可用毫米或英寸输入，内部统一换算为毫米。装配在 `drawing_make` 中使用 `assembly` 参数生成，也可以插入两片真实环形垫片。

`drawing worker` 从已交付的 `flange.step` 导入 B-rep，再用 `build123d.Drawing` 做 HLR 三视图投影。PDF 是矢量线稿，不是 PNG 封装；`flange_render.png` 只用于展示质感，`flange_viewer.html` 提供中文离线旋转、缩放和面片选中。装配查看器按真实组件分色，支持单独隐藏/显示和查看间距。浏览器中的旋转、自动旋转和爆炸检查只改变检查视图，不会回写 STEP、STL、PDF 或 DXF；几何修改必须重新提交参数并重新生成文件。

`part_create` 也支持 `part_type: "gasket"` 单独生成垫片，默认外径 88 mm、内径 42 mm、厚度 3 mm，并输出完整的垫片交付文件。垫片体积使用环形解析解核对，圆柱面数必须为 2。

每个零件目录保留 `run.json`，记录原始请求、解析后的毫米规格、几何摘要、警告、工具链版本和产物 SHA-256。调用 `drawing_make` 后还会生成 `delivery_manifest.json`，汇总请求、实测尺寸、装配检查、图纸回读和产物哈希。`part_check` 的 `warnings` 是演示级几何筛查，不代表 API、ASME 或国标合规结论。

改参对比可运行 `python scripts\compare_demo.py`。完整发布验收入口是 `scripts\verify_release.ps1`；现场展示材料不纳入交付包。

## 审核边界

本项目用于演示 AI 驱动的参数化三维建模和工程交付链路。图纸、模型和检查结果来自已交付 B-rep；正式加工前仍需人工工程审核。





