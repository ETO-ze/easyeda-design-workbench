# 嘉立创专业版：在整机里看见元件，并验证壳真的做出来了

适用于已有生产 PCB，另有线接屏、面板键、开盖预览或 USB 侧开口的设计。以下菜单与 API 调用形态在 **3.2.91 半离线**的 StopKey 案例核过；在线库、其他版本或别的壳体方向，应以实际菜单、返回和导出几何为准。只看普通 PCB 3D，不一定能看到外壳。

## 先分清哪个板页可以投板

| 对象 | 放在哪里 | 怎么核对 |
|---|---|---|
| 真正焊在载板上的芯板、电阻、电容、连接器 | 原理图及其生产 PCB | 用位号比对封装、坐标、面别、旋转、网表和生产 BOM。模型名字不是料号。 |
| 用线接在 J1/J2 上的屏、面板键 | 整机装配页；原理图保留接口和线序。若项目有整机物料清单，另列外购件 | 在标明「装配参考－禁止投板」的板页复制板上摆位，给板外件建立**无焊盘**的装配参考，关闭加入 PCB BOM 和原理图转板。核对生产页没多出位号、孔或网络。 |
| 上下壳与螺柱 | 原生 3D 外壳层；若还要打印，把打印母版单独标明 | 用实际制造板导出 Gerber、钻孔和贴装坐标；不要从装配参考页生成订单。打印件和原生参数壳不一定是同一套几何。 |

进入工程先用工作台的 `context` 核对窗口、工程、当前板页，再在副本做一次单件绑定。生产板和装配页看起来相似，切页后要重新确认目标。若操作超时，先只读检查它是否已经生效，再决定下一步，不盲目重建工程、模型或库条目。

## 有料号、STEP 也在磁盘，为何还是空？

采购码说明“买哪一件”，模型库条目说明“去哪里找几何”，位号绑定才说明“这件几何装在哪个封装”。三者不是同一项。型号相近但 USB 朝向或高度不同的模型，比缺模更容易误导。

1. 先试一个带明显非对称特征的位号（例如 USB-C 的金属口）。在 **文件 → 新建 → 3D 模型** 看本机实际模式：若半离线客户端提示本地目录，把相应 STEP/STP 放进**它显示的目录**，在 **库 → 3D 模型** 选本地目录并刷新；若显示在线导入对话框，则走已授权的模型库流程。[官方创建 3D 库说明](https://prodocs.lceda.cn/cn/3d-model/file-new-3d-model/)
2. 在库中选择实际模型行。本例由 `eda.lib_SelectControl.getSelectedLibraryRowInfo()` 读回选中项，再在 **工具 → 3D 模型管理器** 或本版支持的绑定接口中关联位号；对齐 PCB 顶面、1 脚及 USB 插入轴，保存、重新打开再回读。这里的本地库引用包含目录，不能把另一台电脑的绝对路径或自造的 UUID 当可移植标识。换电脑后若空模，重选同名文件。在线创建返回 `null` 或空结果时不算导入成功。[官方 3D 模型管理器](https://prodocs.easyeda.com/en/pcb/tools-3d-model-manager/)
3. 把**已绑定**和**确有网格**分开验收。前者按位号读 `getState_Model3D()`；后者在装配页导出元件 OBJ，禁用自动生成替代模型。在该版已验证的调用形态是 `eda.pcb_ManufactureData.get3DFile('AssemblyParts', 'obj', ['Component Model'], 'Parts', false)`。取得实际文件后，按 CPL 位置、边界和特征定位：USB 金属口是否在对的板边？屏的有效区是否朝窗？按钮帽和焊耳是否分处面板两侧？不能仅数 OBJ 文件、材质或物体名称，它们与位号并非一一对应。

**只读回读例子（3.2.91）**：在本机指定的 Gateway 窗口运行。先从 `context` 结果填入已核对的工程和目标 PCB 标识，重开 PCB 后，在底部库再次选中要对比的 **3D 模型**行。示例只返回位号和判定值（布尔值或 `null`），不打印可能含磁盘路径的模型引用。

```javascript
const expectedProject = "<工程 UUID>", expectedPcb = "<装配页 PCB UUID>", ref = "U1";
const p = await eda.dmt_Project.getCurrentProjectInfo();
const d = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (p?.uuid !== expectedProject || d?.parentProjectUuid !== expectedProject ||
    d?.uuid !== expectedPcb || d?.documentType !== 3) throw Error("目标 PCB 未确认");
const hits = (await eda.pcb_PrimitiveComponent.getAll()).filter(c => c.getState_Designator() === ref);
if (hits.length !== 1) throw Error("目标位号缺失或重名");
const model = hits[0].getState_Model3D();
const row = await eda.lib_SelectControl.getSelectedLibraryRowInfo();
return {ref, bound: Boolean(model?.uuid),
  sameModel: row?.uuid && model?.uuid ? row.uuid === model.uuid : null,
  sameLibrary: row?.libraryUuid && model?.libraryUuid ? row.libraryUuid === model.libraryUuid : null};
```

`sameModel` 比的是库选中行和位号引用各自的 **uuid**，不是器件采购号；`sameLibrary` 比所属库。返回 `null` 表示缺少一方、无法比较；`false` 表示不同。即使两项都是 `true`，仍要用上一步的 OBJ 检查几何是否真实存在。

## 有外壳对象，却只导出螺丝柱

先在该版客户端用 **放置 → 3D 外壳－边框** 建一个最小闭合壳，在 **视图 → 3D 外壳预览** 看它，再导出并重新打开。板框是生产外形，外壳边框是壳壁的基准；画铜线、画 11 板框层或画普通机械轮廓都不能替代外壳图元。[官方外壳边框](https://prodocs.lceda.cn/cn/pcb/place-3d-shell-outline/) · [官方外壳预览](https://prodocs.lceda.cn/cn/pcb/view-preview-3d-shell/)

本例中 52 为元件模型，53 是外壳边框，54/55 为上下壳；其中 **54 在实物上是后盖，55 是带屏窗的前壳**。换设计要先看图层名称和装配方向。想从背面看元件时只关闭 54 的眼睛，保留 52、55；看完可恢复。隐藏不等于删除。

若 API 能回读 `SHELL`、`BOSS`，STL 却只有柱子，不要继续堆螺柱。在同版本 GUI 创建一个确认能导出的壳和一个侧槽，对照工程副本的原生记录。本例成功的 `SHELL` 有闭合路径和顶层字段 `thickness`、`bottomHeight`、`topInnerHeight`、`bottomInnerHeight`；侧槽是 `SHELL_ENTITY`，有 `type: "SLOT"`、`slotOptions`，且 `refs` 指向实际侧面基准线（`CREASE`）。改写一个通用布尔属性或另造一条 `CONNECT` 没有产出本例所需侧槽。**这些是诊断线索，不是跨版本固定模板。**

## 验收什么，就测什么

| 要回答的问题 | 拿什么测 | 不能据此断言 |
|---|---|---|
| 装配后的外形尺寸对吗？ | 用 `get3DShellFile('Case', 'stl')` 或 GUI 导出；保留同一装配原点、不自动排盘。对每轴取所有壳件的最大坐标减最小坐标，工作台命令 `shell-size` 可复查。 | 包围盒相同不代表有壁、有孔，甚至不代表壳封闭。 |
| USB、屏窗或 D 形孔真的开了吗？ | 在导出网格上从靠近相应壁面的外侧做剖面或取射线：孔中心应通，紧邻孔沿的实壁应有料。只查入口附近，勿把射到远侧后盖误判成堵孔。D 孔还要测平边方向；USB 查侧壁、上下沿及插头外壳。 | “中间透了”不证明孔有正确的位置和宽度；抽样不等于整机无干涉。 |
| 螺钉能装、线能过吗？ | 按坐标与深度测孔截面，区分 PCB 通孔、塑料导孔、后盖间隙孔；以详细模型核对焊耳、压线和插头包络，必要时先打印试片。 | 切片成功不等于真件装得上；简化 OBJ 不能证明焊接线束与后盖的净空。 |

如果导出比目标长宽各多一个壁厚，先确认图纸给的是**成品外廓**，且本版确实以中心线对称生壁。满足这两个条件才把中心线每边内收半壁厚；孔、PCB 和窗口基准不动。若切片器已将两件分别贴地或居中，应先恢复到装配原点，不能把两件厚度直接相加。[带实测数值、图解和可复跑文件的 StopKey 案例](stopkey-r1.md)
