# EasyEDA Design Workbench · 嘉立创 EDA 设计工作台

一个面向 Codex 的嘉立创 EDA 专业版 skill。用同一个入口回答三个常被混在一起的问题：**原理图接对了吗？机械上能对齐吗？导出的铜真的连通了吗？** 支持已有工程的官方 Gateway 操作流程，也能在没有编辑器的机器上生成新工程草稿、跑检查。

本项目由社区维护，不是嘉立创官方产品。不捆绑桌面客户端，不要求上传工程，也不把旧版专业版自动升级为 V4。适配器和版本选择见[选型与兼容性](references/toolchain.md)。

## 从哪里开始

有 Python 3.10+ 即可运行环境自检、焊盘网名和安装孔检查。Windows 中可把以下 `python` 换成 `py`。要在 Codex 中以 skill 使用，将本仓库克隆到自己的技能目录，默认是 `~/.codex/skills/easyeda-design-workbench`（PowerShell 示例）；也可以克隆到普通目录，直接使用命令行。

```powershell
git clone https://github.com/ETO-ze/easyeda-design-workbench.git "$env:USERPROFILE/.codex/skills/easyeda-design-workbench"
cd "$env:USERPROFILE/.codex/skills/easyeda-design-workbench"
python scripts/workbench.py doctor
python scripts/workbench.py mechanics assets/mechanics-intent.json assets/mechanics-measured.json
```

新开 Codex 会话可直接说：

> 用 $easyeda-design-workbench 检查当前板。先告诉我你连上的是哪个文档，再核对 J1 的引脚和 USB 的插入方向；先不要改线。

如果只需离线检查，到这里就够了。若要生成 PCB 草稿、验证 Gerber 或阅读官方 API 文档，可按需安装固定版本的外部工具（打印计划时不下载）。生成草稿另需 Node.js，本次实测为 22；铜检查需要在运行工作台的 Python 环境内安装 Shapely 2.x，推荐使用虚拟环境。

```sh
python scripts/install_tools.py --tools eprj3 copper api-docs
python scripts/install_tools.py --tools eprj3 copper api-docs --apply
python -m pip install "shapely>=2,<3"
python scripts/workbench.py draft blink-draft
```

默认工具目录是 `~/.codex/easyeda-tools`；支持 `CODEX_HOME` 和显式的 `--tools-dir`。下载校验固定 SHA-256，已有目录不会被覆盖。只安装 `api-docs` 不会启动或连接 Gateway，在线写板需另外打开客户端、连接官方扩展并确认目标文档。无需拥有作者机器上的任何私有 skill。

**第一次连桌面编辑器：** 在专业版装好 [Run API Gateway](https://jlc-ext.com/item/oshwhub/run-api-gateway)，按[官方桥的启动步骤](https://github.com/easyeda/easyeda-api-skill/blob/998c0e304afaa813540b7446489982bc5256d37e/SKILL.md#quick-start)启动本机桥，打开要处理的文档，再运行 `python scripts/workbench.py context`。已有可用桥就复用，不要额外启动。多窗口时按返回的 ID 加 `--window ID`；如果桥选择了非默认端口，给 `doctor` 和 `context` 加相同的 `--port`。不要公开转发桥端口。

## 按任务选择

| 我想做什么 | 入口（均接在 `python scripts/workbench.py` 后） | 输出能证明什么 |
|---|---|---|
| 知道现在能做到哪一步 | `doctor` | 本机工具是否在盘、回环桥和窗口状态；不会把“有进程”报成“可写当前板”。 |
| 在线确认“你看到的是哪块板” | `context` 或 `context --window ID` | 通过 Gateway 固定的只读调用核对工程、当前文档和窗口回包；不自动切换窗口。 |
| 从引脚、器件和网络生成草案 | `draft my-board --design design.json` | 新目录中的 V4 原理图、PCB 初排、网表和报告。目标已存在则拒绝覆盖。未布铜不可直接下单。 |
| 核对显示屏、LED 等接口接线定义 | `pins backup.zip assets/oled-pins.json --pcb PCB1` | 读取旧版 EPRU 备份，用位号及**物理焊盘号**报出预期和实际网名；不会把 GPIO 编号当成焊盘号。 |
| 查安装孔偏移、孔径差 39.37 倍、USB 装反 | `mechanics intent.json measured.json` | 统一 mm/mil，给出每个孔的中心/孔径误差，并检查接口面别和插入方向。需从结构图和 PCB 分别取得输入；不代替 3D 干涉检查。 |
| 查实际铜层上的断路、短路、孔型问题 | `copper fab.zip pads.json --out copper-report.json` | 独立预期焊盘与受支持双层 Gerber/PTH/NPTH 是否一致。多层或不支持的文件不能算通过。 |

对于 `pins`、`mechanics` 和 `copper`，退出码 **0** = 所声明范围通过，**1** = 有实际差异，**2** = 输入不足或不支持。`doctor` 是能力清单，应查看 JSON 内的状态。安装孔样例是合成的；OLED 引脚表只是格式示例，套用前须核实器件的具体封装版本。

## 已验证到哪一步

| 实测对象 | 结果 |
|---|---|
| 官方离线生成器 · LED 小板 | 生成 1 页、4 个器件、4 个网络的原理图和 4 个封装的 PCB。独立核对 8 个引脚；初排后尚有 3 个多焊盘网络待布。 |
| 焊盘分配 | 在一个旧版导出样本上核对 11 个指定焊盘；错误网名的反例可复现。仓库测试使用合成数据，不发布原始工程。 |
| 机械验收 | 包含等值 mm/mil、误把数字当 mil、镜像、参考系不一致、连接器面别与插入方向等正反例。 |
| 上游铜层检查 | 26 项上游单测通过；10 个 Gerber 正反例中，3 个通过、7 个检出预设缺陷。仅覆盖受支持的双层贯穿孔模型。 |
| 真实在线编辑 | 本次在专业版 3.2.91 探测到桥，但无连接窗口；未宣称在此版本实测了写板、客户端 ERC/DRC 或制造导出。 |

```sh
python -B -m unittest discover -s tests -v
```

CI 在 Windows/Linux 运行本仓库离线测试，并在 Linux 用固定版本的工具重新生成示例和运行上游铜层正反例。它不连接真实桌面或验证实物板。

## 能做什么优化

比如要改一块带 OLED、USB-C 和三色状态灯的载板，可以先让工作台列出“模块焊盘号 → GPIO → 网络 → 外设引脚”，再让它把孔位和 USB 开口固定下来。这样到了布局阶段，连接器转了 180°、接口网名对调、或者孔径输入错了单位，都有专门的检查，不必靠截图猜。最后再用实际导出的铜层检查走线；本工作台不会把正确的网名当成布线完成。

工作台原创代码采用 [MIT](LICENSE)。外部工具分别来自[嘉立创官方](https://github.com/easyeda)和[社区铜层检查项目](https://github.com/zsy-smu/easyeda-pcb-design)，按固定版本按需下载，各自保留上游许可。
