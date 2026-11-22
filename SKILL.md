---
name: easyeda-design-workbench
description: 用于嘉立创 EDA 专业版（EasyEDA Pro）原理图、PCB 初排与布线、API Gateway 操作、引脚或投板检查，以及板壳装配中元件 3D 模型缺失、USB 开口错位、外壳层或导出 STL 尺寸异常等任务。
---

# 嘉立创电路设计工作台

先判断用户想要的交付物：原理图草案、现板修改、指定网络核对、布线或可下单文件。选择与任务有关的入口。以下 PowerShell 命令的工作目录可以是用户的工程目录。

准备连接桌面或评估在线能力时，从本技能目录执行 `python scripts/workbench.py doctor`（Windows 也可用 `py`）。它只读本机工具清单和回环网关，不启动编辑器，也不选择或保存文档。若只复查已导出的焊盘、结构尺寸或壳体 STL，直接用对应离线命令，无需运行 `doctor` 或开启 Gateway。以下示例按默认工具目录书写；设置了 `CODEX_HOME` 时请使用该根目录。安装可选的固定依赖见 [README](README.md)。不要根据依赖在盘推断编辑器动作已通过。

## 已有工程，走编辑器

从技能目录执行 `python scripts/workbench.py context` 可读取当前文档身份（只调用两个固定查询）。多个连接窗口时需显式指定 `--window ID`；若桥不在默认端口，加 `--port 49621` 等实际端口。读不到文档或回包不一致时停止，不向工程写入。

若存在，读取同级 `easyeda-api/SKILL.md`，用现有 Run API Gateway。没有这个本地适配器时，依照[官方 API skill](https://github.com/easyeda/easyeda-api-skill/tree/998c0e304afaa813540b7446489982bc5256d37e)在**本机回环地址**配置桥接和窗口；安装了本工作台的 `api-docs` 可在工具目录直接读取其 `SKILL.md`。有可选的 guardian 时还可以运行：

```powershell
$skills = Join-Path $env:USERPROFILE '.codex/skills'
py "$skills/easyeda-project-guardian/scripts/probe_easyeda_bridge.py" --timeout 0.4
```

以返回的已连接窗口、项目 UUID、活动文档 UUID 和类型定位目标。有多个窗口时按用户选定的工程定位。可选的同级 `easyeda-project-guardian` 能处理快照、锁、差异、回读及保存；没有它时，先备份工程，记下文档标识和待改对象，检查活动文档未变，先改一个对象并按 UUID 回读，再扩大范围。如无法确认目标或恢复路径，保持只读。若连接窗口数为零，先做离线版本核对、引脚表和布局计划。按需读取工具目录 `api-docs-1.1.85/references/` 中的类，对照本机客户端版本和运行时能力后调用。已有正常工作的桥不应被下载的版本替换。

| 当前工作 | 应用步骤与交付证据 |
|---|---|
| 从要求到原理图 | 对每个功能块列出供电电压、接口、关键型号和「位号.物理脚号 → 网络」。多单元器件区分单元名和物理引脚。用实际库符号的边界与引脚尖端布图，依信号流分块；块内优先短线、跨块用有导线连接的端口。用 `easyeda-schematic-audit` 对照编译网表与期望端点，同时检查重叠、穿越符号、虚接。 |
| SCH → PCB | 对比两侧位号、封装、引脚到焊盘的映射。模块的 GPIO、封装焊盘号、排针序号分列。LED 分别核对限流电阻、A/K 和控制极性。 |
| 板框和摆件 | 使用 `easyeda-cardwallet-placement` 的朝向和碰撞检查方法，按当前板的结构图建立约束。先验证板框层的闭合轮廓、孔中心和钻孔直径，再核对 USB 插入方向、允许外伸、屏幕净高及实际安装面。局部检查时注明正视或背视。 |
| 走线和收尾 | 从同级目录读取 `easyeda-pcb-routing/SKILL.md`。基于实际焊盘和项目规则，先处理关键回路再处理普通网。本用户偏好 PCB 拐角采用 45°；检查相邻线段转角、换层过孔和参考面。检查剩余飞线、短路、间距，需铺铜时重建并检查回流。复用自动布线器应先在副本验证对已有线和锁定线的影响。 |
| 制造输出 | 分别核验编辑器 DRC 明细、Gerber 板框/铜层、PTH/NPTH 钻孔、BOM、坐标面别与 1 脚方向。标注结果所属工程版本、遗漏对象与所需实物测试。 |

机械输入优先用 mm，边界转换时记录原值。PCB API 的 1 mil = 0.0254 mm，所以 Ø3.2 mm 约为 125.98 mil。原理图 API 和离线文件的坐标各按对应接口或格式约定。对旧版 ERC 的模糊布尔返回，保留原值并将详细违规数列为待核实。部分导出接口可能触发注解或保存，先核对实际版本的行为。

表中列出的设计审计、摆件和布线技能是**可选**本地增强，不随本仓库分发。若不存在，用表内的相同验收项和官方 API 在工程副本上逐项核对，并报告未覆盖项；不要寻找不存在的脚本，也不要宣称在线步骤已执行。PCB 默认优先 45°，以用户和实际工艺约束为准。

## 新工程，离线从 design.json 生成

本机固定了官方生成器 `easyeda-eprj3-skill v1.36.1`。示例为独立的 V4 目录工程。现有 V3 桌面工程采用上面的 Gateway 路径。默认不把离线草稿写进已有工程目录。

```powershell
$engine = Join-Path $env:USERPROFILE '.codex/easyeda-tools/eprj3-v1.36.1'
$spec = Join-Path $engine 'examples/designs/blink.json'  # 实际项目换成已核实的 design.json
$dest = Join-Path (Get-Location) 'blink-draft'
if (Test-Path $dest) { throw '请选择新的草稿目录' }
node "$engine/scripts/make-board.js" --design $spec --dir $dest
```

阅读 `$engine/SKILL.md` 获取设计输入格式。用带脚号的器件表定义电路，用数据手册或已核实的库封装确定方向。读取生成的 `project-report.md`、`build.json` 和 `.tmp/netlist-audit.json`，逐网比对期望引脚与实际连通组。报告 PCB 封装数、待布铜网络数以及评分覆盖到的阶段。该引擎的 placed-only 检查跳过未布线和缺覆铜项；上板前还需实际走线和客户端验证。

## 核对旧版 PCB 备份的指定引脚

提供单个 `.epru` 或其 ZIP、板名/UUID，以及 UTF-8 JSON 对照表，例如 `{"J1":{"1":"GND","2":"+3V3"}}`。真实 OLED 样例见 `assets/oled-pins.json`。在含多个 PCB 的备份中优先使用 UUID。

```powershell
$workbench = Join-Path $env:USERPROFILE '.codex/skills/easyeda-design-workbench'
py "$workbench/scripts/check_pcb_pins.py" ".\board-backup.zip" "$workbench/assets/oled-pins.json" --pcb PCB1
```

退出码 0 表示指定焊盘网络匹配，1 表示观察到差异，2 表示输入或目标无法判定。输出给出具体位号、焊盘号、期望网络与文件记录的实际网络。留意快照日期，另外检查原理图网络与已布铜连通。

## 结构和实际铜层：两个独立的检查

- `python scripts/workbench.py mechanics intent.json measured.json`：意图来自结构图，实测值来自明确面别与原点的 PCB 测量或导出。用位号核对每个孔的坐标、钻孔直径和连接器朝向；样例在 `assets/mechanics-*.json`。不接受单位不明的数据，不推算“也许镜像以后能装”。它不是 PCB 轮廓提取器或 3D 干涉检查器。
- `python scripts/workbench.py copper fab.zip pads.json --out copper-report.json`：对**已经导出**的受支持双层 Gerber 检查实铜和跨层连接。独立期望的物理焊盘 JSON 格式见工具目录的 `easyeda-pcb-design-bc3c736/references/copper-tool.md`。只凭网名或只看 3D 预览，不能替代本步。报告文件使用新路径。

## 整机装配、元件 3D 和外壳

当用户要看装配好的元件层、外壳层，或报告“有料号但看不到模型”“导出只有柱子”“成品大了一圈”时，先读[原生装配与导出验收](references/native-assembly.md)。区分生产 PCB 和不投板的装配页；分别报告元件存在、关键部位保真、壳体几何、实物试装的结果。若要用真实导出的两件壳 STL 复跑外廓检查，见 [StopKey：4.2 寸屏、面板键和 USB-C](references/stopkey-r1.md)。`shell-size` 只比较同基准 STL 的外包络，不能证明开孔、布线净空或可打印。

选择可选工具或升级 V4 环境时读 [工具与版本](references/toolchain.md)。交付时说清已经生成什么、由哪个工具检查、哪些步骤仍需编辑器或实物。
