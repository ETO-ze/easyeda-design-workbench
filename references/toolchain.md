# 工具选型与兼容范围

调研基线：2026-11-21。这里的“主流”指官方入口及有公开实现和可验证用例的社区路线，不按星数排名。链接固定到当次核对的版本。安装本工作台不会替换已有插件、修改工程或升级桌面客户端。

| 方案 | 适合的工作 | 整合方式及证据 |
|---|---|---|
| [官方 easyeda-api-skill 1.1.85](https://github.com/easyeda/easyeda-api-skill/tree/998c0e304afaa813540b7446489982bc5256d37e) | 通过 Run API Gateway 操作正在打开的专业版工程 | 作为在线操作首选。文档采用固定版本；不以文档版本推断旧客户端支持全部方法。本次在 Windows 专业版 3.2.91 上测到本机桥服务；无连接窗口，未测在线写板。 |
| [官方 easyeda-eprj3-skill 1.36.1](https://github.com/easyeda/easyeda-eprj3-skill/tree/9d65dee4ad2e5dc0ae1ee3bf3e16ae824f230e13) | 从结构化器件、引脚和网络生成 V4 原理图和 PCB 初排 | 固定为本次**实测**的生成器。Node 22 上从零构建了一个 4 器件项目，再独立核对引脚分组。它生成的是一组工程文件而非单文件，交付时保留整个目录。 |
| [官方 easyeda-eprj3-skill 2.2.7](https://github.com/easyeda/easyeda-eprj3-skill/blob/8ff62c549c81e1d373f4cb274871ad1ff42b61e4/SKILL.md)、[官方 CLI skill](https://github.com/easyeda/easyeda-cli-skill/tree/d7470ddacb0a1f06bf4108756b375a30343f3208) | 离线生成器仍只做初排；另有在线命令调用兼容客户端的布线、铺铜等功能 | 升级候选，**未在本次环境实测**。2.2.7 的客户端操作路径要求 4.1.94+；CLI skill 标注 4.1.70+。以所用命令对应的要求为准，参见[专业版 CLI 文档](https://prodocs.lceda.cn/cn/api/guide/cli.html)。不要把新工具装上等同于老客户端有此能力。 |
| [官方 easyeda-format-skill](https://github.com/easyeda/easyeda-format-skill/tree/4fcab1747d47b2ae01d7f93a485859970c5cf933) | 了解专业版文件结构及记录格式 | 用作格式参考；结构正确不能证明电路连接正确。 |
| [zsy-smu/easyeda-pcb-design](https://github.com/zsy-smu/easyeda-pcb-design/tree/bc3c73699624e7aa360ff135eb900d0284d3a8df) | 独立网表对比和双层 Gerber 实际铜连通检查 | **实测** 26 项单元测试、10 个铜层正反例、1 组逻辑引脚到实体焊盘映射。可选外部引擎，不替代编辑器 DRC。 |
| [hyndex/easyeda-mcp](https://github.com/hyndex/easyeda-mcp/tree/6ca20e753fbffc70138456d830044de46a85d269) | 基于几何和确定性网表的原理图规划 | 参考了用实际引脚位置和独立网络分组检查原理图的方法，未安装此扩展。 |
| [SrijanCherupally/EasyEDA-MCP](https://github.com/SrijanCherupally/EasyEDA-MCP/tree/a8d7c658c00f6edc05598555fef14743b0fbe29a) | 社区 MCP 的交互式 PCB 操作 | 其仓库描述了走线、铺铜与制造输出。与官方 Gateway 部分重叠，列为替代适配器；本次没有验证这些操作。 |

## 选择策略

1. 已打开的生产工程：优先复用用户已有 Gateway。只有识别到目标窗口及文档、备份可恢复，才进入修改。客户端版本和文档类型不明确时先读不写。
2. 从零起草：用离线生成器生成全新的目录，在独立检查中比较预期网络与生成文件；不要向已有工程目录使用强制覆盖。
3. 制造复核：从独立设计意图或已核实的封装数据准备带坐标、层和孔型的预期焊盘表，对实际导出的 Gerber/钻孔做铜检查。不用待测 Gerber 自己推断全部期望，否则可能漏掉一致性错误。
4. 社区铜检查器当前覆盖双层、贯穿孔及受支持的简单实心光圈；内层、盲埋孔、宏光圈、铜弧或混合极性等超出范围时要报告“不支持”。不将跳过、无窗口或只做初排记成通过。
