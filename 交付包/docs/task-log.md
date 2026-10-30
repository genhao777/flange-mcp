# 任务记录

## 2026-10-24

### 计划

- 建立独立项目目录；
- 定义法兰六参数；
- 先完成 build123d 几何和解析体积核对；
- 暂不扩展到 MCP、图纸和内部系统接入。

### 已完成

- 创建核心项目骨架；
- 创建法兰参数模型、参数校验和解析体积计算；
- 创建第一天验收脚本。

### 已验证

- 在独立环境安装 build123d；
- 确认 build123d 版本和布尔建模结果；
- 确认 STEP/STL 导出；
- 记录真实运行时间和输出。


### 真实验证结果

- 独立环境：Python 3.12.14，build123d 0.13.0，ezdxf 1.4.5，pydantic 2.14.1；
- 体积：144010.60724055616 mm³；
- 体积相对误差：2.0209504712467812e-16；
- 包围盒：120 × 120 × 15 mm；
- 实体数：1；
- 圆柱面数：6；
- STEP 和 STL 已生成到 out/flange_day1/；
- 第一阶段验收脚本返回 ok=true。
- check.json 已生成到 out/flange_day1/。

## 第二天和第三天真实结果

- 参数变化：默认四孔法兰和 160 mm 外径、六孔变体均通过；
- 非法参数：中心孔过大、PCD 越界、零孔、非整数孔数均被拒绝；
- MCP SDK：1.30.0；
- MCP stdio 客户端发现四个正式工具；
- part_create、part_check、drawing_make 完整调用均返回成功；
- DXF 回读到 5 个原生 DIMENSION 实体；
- PDF、PNG、DXF、STEP、STL 和 JSON 可写入同一个零件目录。


## 2026-10-25 继续推进

- 增加参数变化、非法参数和独立输出目录验收；
- 完成 DXF、PDF、PNG 第一版出图，DXF 含 5 个原生 DIMENSION；
- 接通四个 MCP 工具；
- build123d 和 ezdxf/Pillow 均通过独立 worker 子进程执行，避免阻塞 MCP stdio；
- 完成真实 stdio 冒烟测试；
- 回归结果：day1=0，day2=0，mcp=0，compileall=0。
- 新增 scripts/run_mcp.ps1，一键启动和 SmokeTest 均通过。

## 2026-10-25 投影与规格语义修复

- drawing_make 从已交付 flange.step 导入实体，不再按 spec 用 PIL 重画几何；
- PNG、PDF、DXF 共用 build123d.Drawing 的 HLR 可见线和隐藏线；
- PNG 和 PDF 改为第一角三视图，PDF 使用 ReportLab 矢量路径；
- PDF 结构检查：无 /Subtype /Image、无 /DCTDecode，包含矢量路径和字体；
- part_check 无显式 spec 时读取本次 part_create 保存的规格，改参数后仍为绿色；
- projection_regression 证明 3 孔和 4 孔 B-rep 的顶视图边数量分别为 5 和 6。

## 2026-10-25 最终回归

- projection_regression=0；
- MCP SmokeTest=0；
- compileall=0；
- 最新产物 934bbfd7 的 PDF 无 /Subtype /Image、无 /DCTDecode；
- 最新 DXF 包含 5 个 DIMENSION，图层包含 HIDDEN 和 VISIBLE；
- drawing.json 标记 projection_source=delivered STEP B-rep via build123d.Drawing。

## 2026-10-25 演示前串行验收

- 串行运行 day1、day2、projection_regression 和 mcp_smoke，全部返回 0；
- MCP 冒烟使用非默认规格 `140 / 18 / 45 / 4×12 / PCD100`；
- `part_check` 从已保存规格校验并返回 `ok=true`；
- drawing 回报 3 个投影视图、5 个原生 DXF DIMENSION，STEP 实测规格与请求规格一致；
- 现场可先运行 `scripts/run_mcp.ps1 -SmokeTest`，Codex 客户端接入留到项目本体冻结后再做。
- A3 PDF 增加了简洁标题栏，重新渲染检查通过；PDF 仍保持无位图对象、无 DCTDecode。

## 2026-10-25 试用期增强项

- 增加 `flange_render.png` 等轴测展示图：由 STEP B-rep 三角网格着色生成，作为演示封面，不替代技术图纸；
- 增加英寸输入和毫米归一化，支持 `units=mm/in` 及常见单位别名；
- 增加几何筛查 `fault_type` 和 `warnings`，覆盖外缘边距、中心孔与螺栓孔间隙、相邻螺栓孔间隙；
- 增加 `run.json` 审计清单，记录原始请求、解析规格、几何摘要、上下文信息、版本和产物哈希；
- 增加可选油田上下文字段：`line_id`、`service`、`nominal_size`、`pressure_class`、`material`；这些字段不声称完成标准合规计算。

## 2026-10-25 增强回归

- MCP SmokeTest 扩展为 6 次调用：默认改参成功、出图成功、英寸归一化成功、油田上下文保留成功、非法输入返回 `BOLT_EDGE_DISTANCE_INVALID`；
- 最新主产物 `37175e6b` 的 `run.json` 已包含 STEP、STL、DXF、PDF、PNG、展示图、核对报告和图纸报告的 SHA-256；
- 等轴测展示图完成一次遮挡排序修复，最终视觉检查通过；
- day1=0，day2=0，projection_regression=0，compileall=0。

## 2026-10-25 工单展示与改参对比

- 油田上下文会随零件进入技术 PNG、A3 PDF 和等轴测展示图标题区域；
- 新增 `scripts/compare_demo.py`，通过同一个 MCP 服务生成 4 孔与 6 孔案例，并输出体积、外径、厚度和孔数差异；
- 发布验收脚本再次通过，MCP 仍保持四个工具，没有增加新的服务。

## 2026-10-25 Codex 接入

- 已注册全局 MCP 服务 `oilfield-flange`；
- 传输：stdio；命令：项目 `.venv\Scripts\python.exe -m flange_mcp.server`；
- 已用 `codex mcp get` 和 `codex mcp list` 验证配置存在且启用；
- 当前会话若未立即显示工具，重新打开或刷新 Codex 会话即可。
- Codex CLI 只读实测已调用 `oilfield-flange.part_catalog`，成功返回 `perforated_flange` 及单位、上下文字段。

## 2026-10-25 PDF 尺寸标注补齐

- ReportLab PDF 增加图面尺寸标注线、延长线、箭头和实测文字；
- 主视图标注 OD，右视图标注 T，俯视图标注中心孔、PCD 和螺栓孔径；
- 视觉检查确认尺寸位于对应视图附近，PDF 仍为矢量线稿；
- 完整发布验收再次通过。

## 2026-10-25 离线交互式 3D 查看器

- `drawing_make` 默认增加 `flange_viewer.html`；
- 查看器内嵌 STEP B-rep 三角网格，不依赖 CDN、FreeCAD 或网络；
- 支持鼠标拖拽旋转、滚轮缩放、自动旋转和点击选中面片；
- 保留 STEP、DXF、PDF 和 2D PNG 的相对链接，便于从一个窗口继续检查产物。


## 2026-10-25 法兰短节装配扩展

- 对照实习生要求中的管接头、套管短节和“可下载三维模型 + 可转动查看”方向，增加受限的 `flanged_spool` 装配模板；
- 保持 MCP 工具数量为四个，装配作为 `drawing_make` 的可选 `assembly` 参数，不增加新的服务工具；
- 装配由前端法兰、同轴管段和同规格端部法兰组成；
- `assembly.json` 回读组件数、连接面数、同轴、端面贴合和螺栓孔阵列对齐；
- 额外产物为 `flange_spool.step`、`flange_spool.stl` 和中文 `flange_spool_viewer.html`；
- `mcp_smoke.py` 已加入装配调用，完整发布验收通过；
- 现场演示脚本改为“我说”和“我发给 Codex”两类话术，并在开场增加 MCP 接入确认。

## 2026-10-25 三维查看器交互与视觉改版

- 旋转逻辑明确为水平拖拽绕 Y 轴、垂直拖拽绕 X 轴，Shift + 水平拖拽绕 Z 轴；
- 增加坐标轴指示、当前 X/Y/Z 角度读数、正视图、俯视图和右视图按钮；
- 重新整理深色工业风界面、网格背景、状态徽章和信息卡片，减少测试页观感；
- 重新生成装配查看器并通过完整发布验收。

## 2026-10-26 旋转中心与画布清理

- 旋转前读取 STEP B-rep 的体积几何中心，法兰单件和法兰短节装配都围绕实际实体中心旋转；
- 移除三维画布上的标题、提示、徽章、坐标轴文字和控制按钮，避免遮挡模型；
- 控制按钮和轴向提示统一移到右侧信息栏；
- 自动旋转改为单一动画循环，反复点击不会叠加转速；
- X 轴拖拽范围放宽到完整翻转，便于查看法兰背面和管段底部；
- 生成 `flange_edd2aa90` 查看器并通过 Node 脚本语法校验。

## 2026-10-26 油田装配最小闭环增强

- 新增 `GasketSpec`，支持在法兰短节两端插入真实环形垫片；带垫片装配包含 5 个组件和 4 个连接面；
- 装配检查改为从组件 B-rep 的包围盒、接口间隙、轴线偏移、圆柱面孔阵列和内孔净空读取结果；
- `drawing_make` 增加 `delivery_manifest.json`，汇总请求、实测尺寸、检查结果、产物路径和 SHA-256；
- 更新 `part_catalog`、技能说明和演示脚本，补充法兰—垫片—管段场景；
- 直接 B-rep 回归验证已通过：同轴、四个接口零间隙、孔阵列对齐和内孔净空均为通过；错误垫片内径返回 `GASKET_INTERFACE_INVALID`。
- 已生成可直接演示的 `out/flange_gasket_demo` 样例，包含 5 组件装配 STEP、PDF、DXF、PNG、中文查看器、`assembly.json`、`delivery_manifest.json` 和 `run.json`。

## 2026-10-27 装配查看器组件控制

- 装配查看器按真实组件 B-rep 分组着色，区分法兰、垫片和管段；
- 右侧增加组件单独显示/隐藏和爆炸间距控制，画布本身仍不放文字遮挡；
- `drawing.json` 会显式列出 `delivery_manifest.json`，交付目录索引保持完整；
- `Desktop\\ceshi` 已重新生成并通过装配检查、文件完整性和 JavaScript 语法校验。

## 2026-10-27 查看范围与视图语义

- 缩小右侧栏并把模型适配比例从 `2.45` 调整为 `2.1`，让 3D 模型在画布中占比更大；
- 改为根据当前旋转、组件可见性和查看间距动态计算投影包围范围，模型始终适配画布；
- 额外生成 `flange_spool_viewer_latest.html`，避免本地文件标签页继续复用旧缓存；
- 右侧说明明确：旋转、自动旋转和查看间距只改变浏览器检查视图，不会修改 STEP、STL、PDF 或 DXF；
- `ceshi` 已重新生成新版查看器并通过脚本语法、装配检查和交付清单索引校验。

## 2026-10-27 装配实测逻辑加固

- 装配检查读取 STEP B-rep 圆柱面的轴线和半径，实测管段外径、内径、壁厚、长度、法兰孔中心、PCD 和孔径；
- 同轴检查比较实际轴线方向与轴线偏移，端面检查保留带符号接口间隙，孔阵列检查比较两端孔中心坐标并拒绝数量、孔径或 PCD 不符的情况；
- `assembly.json` 增加 `bore_segments`、`bolt_pattern`、`pipe_dimensions_pass` 和 `interface_gap_max_mm`，合格样例的五组件装配仍全部通过。

## 2026-10-28 三维查看器美术质感

- 画布改为深蓝黑工业展台背景，增加柔和环境光、地面阴影和边缘暗角；
- 法兰、管段、垫片使用冷钢、深铜和低饱和米金材质色，并根据 B-rep 面法线和深度做金属明暗；
- 普通三角边线降低透明度，选中面片保留金色高亮，减少“测试网格”观感；
- 组件列表增加与模型一致的颜色标记，`ceshi` 已重新生成并通过 Node 脚本语法检查。

## 2026-10-27 五项实习化增强最终验收

- 运行 `scripts/verify_release.ps1`，几何、参数容错、投影拓扑、Python 编译和 MCP 端到端五项验收全部通过；
- 端到端验收覆盖中文 MCP 工具发现、改参生成、英寸转毫米、非法输入 `fault_type`、三视图五个尺寸回读、三组件装配和五组件垫片装配；
- 运行 `scripts/compare_demo.py` 生成 `parameter_compare.json`，记录四孔到六孔规格变化及体积差异；
- 在 `Desktop\\ceshi` 写入 `demo_acceptance.json`，按几何核对、投影图纸、交互查看器、油田装配、参数化与错误处理五项汇总证据。

## 2026-10-28 垫片独立零件与 GB 图纸收口

- 垫片装配增加螺栓孔覆盖硬约束，默认外径按 `PCD - 螺栓孔径` 解析，错误返回 `GASKET_COVERS_BOLT_HOLES`；
- 法兰 PDF/PNG 改为主视图、俯视图、左视图的第一角布局，使用仿宋回退字体、中文视图标签、GB/T 10609.1 风格标题栏和第一角投影符号；
- `part_create` 支持 `part_type=gasket`，独立生成垫片 STEP、STL、PNG、DXF、PDF 和解析体积检查；几何与图纸分别通过 worker 进程执行，避免 MCP 主进程阻塞；
- 装配报告增加 `axis_continuous`、`flange_pipe_clearance_mm` 和 `min_bore_mm`，保留旧字段以兼容现有演示脚本；
- `verify_release.ps1` 通过，覆盖独立垫片创建、检查、图纸和非法参数场景。
## 2026-10-30 演示输出归档整理

- 出图 worker 只保留 `flange_spool_viewer.html`，移除重复的 `_full` 和 `_latest` 查看器产物；
- 演示提示词要求通过 output_dir 让本次最终文件直接生成到 `Desktop\\ceshi\\油田法兰短节演示\\`，按模型、图纸、报告分类并使用清晰文件名；
- `out/` 继续保留原始运行产物，`ceshi/` 用作现场展示归档目录；
- 交付包补齐正式演示脚本、屏幕展示稿、AI 提示词和验收记录。

