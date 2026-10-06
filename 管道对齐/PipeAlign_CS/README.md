# PipeAlign · 管道标高对齐（OpenPlant Modeler C# AddIn）

按一根**基准管**的标高，把一批**目标管**的管底 / 管中心 / 管顶对齐过去。

UI 按 `../ui-share` 改为480×960逻辑像素的竖版面板：纵向参数、2×2目标操作、滚动管道卡片、等宽右对齐数值和固定底栏。Z位移由基准自动计算，不显示禁用输入框。卡片支持Ctrl/Shift多选移除，悬停查看完整管号/连接/跳过原因；底部摘要截断时可悬停查看全文。保留SDK宿主与消息队列读取，未引入网页运行依赖。独立WinForms布局渲染已检查，真实OPM停靠与高DPI仍需验证。

2026-10-04 新增锁 Z 移动：水平管及相连管件随动、竖直直管伸缩、另一端固定；自动预览，点击应用直接执行，正常成功不弹窗。使用与宿主验收限制见 [锁Z移动与撤销修复](../锁Z移动与撤销修复_2026-10-04.md)。

本工程是 [`管道对齐插件开发指南.md`](../管道对齐插件开发指南.md) 的 C# 实现，
独立于仓库里另一个 C# AddIn（`型钢构件及支吊架模型生成工具_CS`），两者**没有代码依赖**，
只共用同一套 Bentley 程序集引用与工程约定。

```text
PIPEALIGN                     打开窗口（模式取配置文件里的默认值）
PIPEALIGN BOTTOM|CENTER|TOP   以指定对齐模式打开窗口
PIPEALIGN ZMOVE               锁 Z 移动，立管伸缩、远端固定
PIPEALIGN DEBUG               只读打印选中管道的调试数据，不修改模型
PIPEALIGN DEBUG DUMP          同上，并追加全部 EC 属性
PIPEALIGN OPTIONS             把当前运行参数写回配置文件
```

---

## 1. 快速开始

### 1.1 编译

```powershell
cd 管道对齐\PipeAlign_CS
dotnet build PipeAlign.csproj -c Release
```

默认 Bentley 根目录为 `D:\Program Files\Bentley\OpenPlant 2024\OpenPlantModeler`，
换机器时用 `/p:BentleyRoot="..."` 覆盖：

```powershell
dotnet build PipeAlign.csproj -c Release /p:BentleyRoot="C:\Program Files\Bentley\OpenPlant 2024\OpenPlantModeler"
```

产物：`bin\Release\net48\PipeAlign.dll`。

### 1.2 加载

与仓库另一个 C# AddIn 的方式一致（不经过 Python Editor）：

1. 把产物目录加入 `MS_ADDINPATH`（用分号分隔多个目录）；
2. 启动 OPM，键入 `MDL LOAD PipeAlign`；
3. 键入 `PIPEALIGN` 打开窗口。

有一个现成的辅助脚本，只做"复制 + SHA256 校验 + 打印加载步骤"，不去改任何机器级设置：

```powershell
# PowerShell 7
pwsh -File Deployment\install_to_addinpath.ps1
# Windows PowerShell 5.1
powershell -File Deployment\install_to_addinpath.ps1

# 指定目标目录
pwsh -File Deployment\install_to_addinpath.ps1 -TargetDirectory 'D:\OPM_Addins\PipeAlign'
```

> ⚠️ 该 `.ps1` 必须保存为 **UTF-8 with BOM**。Windows PowerShell 5.1 会把无 BOM 的脚本按
> ANSI 读取，脚本里的中文会变成乱码并直接导致语法错误。用编辑器改完这个脚本后请确认 BOM 还在。

升级 DLL 前必须先关掉 OPM —— 已加载的程序集无法被覆盖。

第一次在新环境使用时，**建议先跑 `PIPEALIGN DEBUG`**（只读，不改模型），
确认能识别 `PIPE`、能拿到中心线与外径、移动能力探测是否通过，再去做对齐。

> 2026-10-04：本轮审计与修复结果见 [评估报告](../管道对齐功能评估_2026-10-04.md)。新版已编译并通过离线回归，尚未在 OPM 中复测。

### 1.3 使用步骤

1. 打开一个**三维、公制**的 DGN 模型；
2. `PIPEALIGN` 打开窗口；
3. 点【选择基准管】，在模型里点一根**水平直管**；
4. 选对齐方式（管底 / 管中心 / 管顶）与表面模式（管道外表面 / 保温层外表面）；
5. 点【选择目标管】后连续左键多选；也可以先在模型里选中一批管道再点【从选择集添加】；
6. 点【预览 / 刷新】：窗口表格逐根显示当前标高、目标标高、ΔZ、连接关系与状态，
   同时在模型里用**临时线**画出当前中心线（蓝）与对齐后中心线（红）；
7. 核对无误后点【应用】。整批操作**一次 Undo 可撤消**。

---

## 2. 这个插件最重要的设计：不用没被证实的单位去改模型

开发指南 §18 要求"优先用 OpenPlant SDK 的业务对象接口修改位置"，但**官方文档没有保证**
这些接口返回 / 接受什么单位。`BMECObject.GetNthPoint` 的原生重载参数名是 `pPointInGlobalUors`
（暗示 UOR），而托管重载与 `Transform3d` 的平移分量是否同一单位体系，只能实测。
**猜错单位的后果不是"移动失败"，而是把管道挪到几百米之外。**

因此本插件的读取与移动是这样分工的：

```text
读取阶段（EC 实例的生存期内，一次完成）
  ├─ 用元素曲线 / 显示几何 / COM 链独立读出中心线（毫米）—— 这条通道永远可信
  ├─ 读 EC 属性（外径 / 保温 / 管线号…），并用「属性 LENGTH ↔ 几何长度」标定属性单位
  └─ 探测移动能力（OpenPlant/OpenPlant2024ObjectProbe.cs）
        ├─ 用 GetNthPoint 两点距离 ÷ 几何长度 推断 API 坐标单位
        ├─ 再用"端点标高 × 单位 == 几何中心标高"二次核对（两处都吻合才算证实）
        └─ 同样核对 Transform3d.Translation 是否与管轴端点重合
                     ↓  只有被证实的能力才会写进 PipeInfo.MoveProbe
移动阶段（Services/PipeMoveService.cs）
  ├─ 按 Level 1 → Level 2 →（可选）Level 3 依次尝试
  ├─ 每次调用后**用独立几何通道复核**标高是否真的变了
  ├─ 复核不过 → 把这一级的影响退回去 → 试下一级
  └─ 三级都不过 → 记为失败，并**立即停止后续修改**（指南 §29）
```

推论（很重要）：

* 在**你没有实测过**的 OPM 版本 / 项目上，插件第一次运行时如果探测不通过，
  它会**拒绝移动并说明原因**，而不是猜一个单位去写模型。这是有意的。
* 探测结论只对**当次读取的那根管道**有效，不做跨模型的缓存。
* 复核通道与移动通道完全独立，所以"接口返回成功但模型没变"这种情况会被如实报告为失败。

三级策略对应指南 §18：

| 级别 | 实现 | 说明 |
| --- | --- | --- |
| Level 1 | `BMECObject.SetLinearPoints` | 按管轴两端点直接改位置。**需要探测证实单位**。 |
| Level 2 | `BMECObject.Transform3d` 平移分量 +ΔZ | **需要探测证实与几何同源**。 |
| Level 2b | `TRANSFORMATION_MATRIX.M11` + `IDgnECInstance.WriteChanges()` | 独立尝试，必须证明 API 单位与 EC/几何基线一致；前一级事务回退之后才能尝试。 |
| Level 3 | `Element.ApplyTransform(TransformInfo)` | **默认关闭**（`AllowGraphicsTransformFallback=false`）。指南 §19 明确禁止把它当正式实现：它只改图形，OpenPlant 数据与轴测图会停在旧标高。打开后结果里会带 ⚠️ 提示。 |

---

## 3. 移动范围：只移动选中 / 连同连通对象一起移动

V1 按指南 §22 采用 Safe Mode：只处理**水平直管**（`|ΔZ| ≤ HorizontalToleranceMm`，默认 1 mm，
**配置可改**）；不处理斜管、弯头、三通、异径管、阀门、法兰、支吊架、仪表、设备管口（指南 §3.2）；
参考文件里的管道只读。

在此之上，"移动范围"决定**一根管道挪动时，它的连通对象怎么办**：

| 范围 | 行为 | 适用 |
| --- | --- | --- |
| **只移动选中的管道**（默认） | 目标管只要连到"本批不会一起移动的对象"就**跳过**并给出中文原因。连到**基准管**也算固定连接（基准管不动）。 | 孤立的管段、或只想改一根 |
| **连同连通对象一起移动**（Move Group，指南 §23） | 从选中的管道出发沿连接关系展开**整组**，组内所有对象用**同一个 ΔZ** 一起平移。 | 真实管线（几乎没有孤立管段） |

Move Group 的成员策略（配置可改，默认值如下）：

* **一起移动**：管道、管件（弯头 / 三通 / 异径管 / 管箍 / 管嘴…）、法兰类、阀门。
* **边界**：设备管口、支吊架、仪表、**未知类**。
* 遇到边界 → **拒绝整组**（指南 §24："如果会产生断开，程序停止操作"），并在界面上逐条列出
  是哪个对象的哪个口连到了什么。**刻意不做"能移多少移多少"的裁剪** —— 那会正好在边界处
  留下断口，比不移动更糟。
* 连接关系读不到、成员读不出来、组超过 `MoveGroupMaxMembers` → 同样拒绝整组。
  不猜移动范围：猜错范围就是断口。
* 行首带「＋」的是自动带进来一起移动的对象，界面上会与用户选中的区分开。

**支吊架默认不跟着走**：管道挪了、支吊架跟着挪，等于把它从结构生根处拽下来。
若项目确认这里的支吊架应随管移动，把 `MoveGroupMovableKinds` 加上 `SUPPORT` 即可。

> ⚠️ Move Group 的可靠性取决于**连接关系读得准**。读取器同时用两个来源：
> `Port.IsConnected` / `Port.ConnectedTo` 与 `BMECObject.ConnectedComponents`，
> 合并去重后使用；来源与条数都写进日志（`连接关系：…；对象来源 …；端口 N 个（已连 M）；ConnectedComponents K 个`）。
> 若某根管在 OPM 里明明连着邻管却报"无连接"，请把这一行发我 —— 那说明两个来源都没给数据，
> 需要换用 OpenPlant 的关系查询 API。

**这意味着**：在"只移动选中"模式下，"两根相连的管道想把其中一根挪平"会被拒绝（这是指南的有意设计）；
要用 Move Group 模式，它会把该管段整组一起平移。

---

## 4. 运行参数

配置文件 `PipeAlign.options.txt`，查找顺序：

1. **DLL 同目录**（随插件分发，项目统一口径用这个）；
2. `%LOCALAPPDATA%\PipeAlign\PipeAlign.options.txt`（单个用户覆盖）。

文件不存在时使用内置默认值且**不报错**。任一键写错只忽略该行并在日志里提示，不会让插件打不开。
用 `PIPEALIGN OPTIONS` 可把当前生效的设置写回用户目录那份。

| 键 | 默认 | 含义 |
| --- | --- | --- |
| `HorizontalToleranceMm` | `1.0` | 水平管判定容差：中心线两端高差不大于该值即视为水平管 |
| `AlignmentToleranceMm` | `0.001` | `abs(ΔZ)` 不大于该值即视为"本来就对齐，不移动" |
| `DefaultAlignmentMode` | `BOTTOM` | `PIPEALIGN` 不带参数时的对齐模式 |
| `DefaultSurfaceMode` | `PIPE` | 启动时的表面模式（程序不会自动猜测） |
| `MaxTargetPipes` | `200` | 单次操作允许的最大目标管数量 |
| `AllowGraphicsTransformFallback` | `false` | 是否允许回落到 DGN 图形变换（会破坏数据一致性） |
| `TopologyCheckMode` | `STRICT` | 连接校验严格程度：`STRICT` / `BESTEFFORT` / `OFF` |
| `MoveScope` | `SINGLE` | 移动范围：`SINGLE`（只移动选中的）/ `GROUP`（Move Group，连同连通对象） |
| `MoveGroupMovableKinds` | `PIPE,FITTING,FLANGE,VALVE` | GROUP 模式下允许一起平移的类别 |
| `MoveGroupBoundaryKinds` | `NOZZLE,INSTRUMENT,SUPPORT,UNKNOWN` | GROUP 模式下视为边界、遇到即拒绝整组的类别 |
| `MoveGroupMaxMembers` | `200` | GROUP 一次最多展开多少个对象 |
| `DumpEcProperties` | `false` | 是否把全部 EC 属性写进 Message Center（仅排查用） |

---

## 5. 目录职责

```text
PipeAlign_CS/
├─ App/
│   ├─ PipeAlignAddIn.cs            AddIn 宿主（MdlTaskID = PipeAlign）
│   └─ PipeAlignSession.cs          一次会话的全部状态与依赖装配
├─ Registration/
│   ├─ commands.xml                 Key-in 表（逻辑资源名固定为 CommandTable.xml）
│   └─ Keyins.cs                    命令入口
├─ Domain/                          纯领域模型，不引用任何 Bentley 类型
│   ├─ AlignmentMode.cs             BOTTOM / CENTER / TOP
│   ├─ SurfaceMode.cs               PIPE / INSULATION
│   ├─ PipeAxis.cs                  中心线（mm）
│   ├─ PipeInfo.cs                  统一管道数据模型（指南 §7）
│   ├─ PipeTopology.cs              连接关系 + 连接对象归类
│   ├─ PipeTopologyCheckMode.cs     拓扑校验严格程度
│   ├─ PipeMoveProbe.cs             该元素上探测到的移动能力与单位
│   ├─ PipeMoveAttempt.cs           三级策略的层级与尝试结果
│   ├─ PipeAlignOptions.cs          运行参数（含解析，纯计算可断言）
│   ├─ AlignmentRequest.cs          基准管 + 目标管集合 + 模式
│   ├─ AlignmentPlan.cs             每根目标管的 ΔZ 或跳过原因
│   └─ AlignmentResult.cs           执行结果与正式日志格式
├─ Data/
│   ├─ PipeEcPropertyNames.cs       EC 属性规范名（来自已验证的 Python 读取库）
│   ├─ PipeReadOptions.cs           读取选项
│   ├─ PipeElementReader.cs         元素 → PipeInfo（EC 读取的崩溃规避都在这）
│   ├─ PipeGeometryReader.cs        中心线：曲线 / 显示几何 / COM / 包围盒近似
│   ├─ PipeGeometryVerifier.cs      移动后的独立几何复核
│   ├─ LocatedElement.cs            元素身份（含所属模型引用）
│   ├─ DgnUnitServiceFactory.cs     唯一读 ModelInfo 的地方
│   └─ PipeAlignOptionsStore.cs     配置文件读写
├─ Services/                        计算与执行
│   ├─ ElevationCalculator.cs       唯一的标高算法入口（指南 §16）
│   ├─ PipeValidationService.cs     水平 / 只读 / 锁定 / 拓扑校验（中文原因）
│   ├─ PipeAlignPlanner.cs          计划生成 + Safe Mode 拓扑不动点过滤
│   ├─ PipeMoveService.cs           执行：分级 + 复核 + 回退 + 撤销组 + 失败即停
│   ├─ LengthUnitCalibrator.cs      EC 长度属性单位标定（移植自已验证的 Python 实现）
│   ├─ IUnitService.cs / UnitService.cs   毫米 ↔ UOR
│   └─ IPipeGeometryVerifier.cs     复核接口
├─ OpenPlant/                       版本适配层（指南 §20）
│   ├─ IOpenPlantObjectProbe.cs
│   ├─ OpenPlant2024ObjectProbe.cs  连接关系 + 移动能力探测
│   ├─ IOpenPlantPipeAdapter.cs
│   └─ OpenPlant2024PipeAdapter.cs  Level 1 / 2 / 3 的实际调用
├─ Tools/
│   ├─ PipePickTool.cs              基准管 / 目标管的点取工具
│   └─ PipeAlignPreviewSession.cs   临时预览线（当前 / 对齐后中心线）
├─ UI/
│   └─ PipeAlignDialog.cs           非模态窗口（Adapters + WindowManager）
├─ Deployment/
│   └─ install_to_addinpath.ps1     复制 DLL + SHA256 校验 + 打印加载步骤
└─ Infrastructure/
    ├─ PipeAlignLog.cs              Message Center 摘要 + 文件详细日志
    └─ PipeDebugReport.cs           PIPEALIGN DEBUG 的报告
```

依赖方向：`UI/Tools → Services → Domain`，`UI/Tools → Data → Domain`；
`Domain` 与大部分 `Services` **不引用 Bentley**，因此可以被
[`../Development/PipeAlignCheck`](../Development/PipeAlignCheck/) 离线链接与断言。

### 5.1 四条踩坑铁律（改代码前必读）

1. **EC 实例绝不带出遍历**：`DgnECManager.FindInstances` 返回的实例只在这次遍历过程中有效。
   物化后留用、或返回给别的函数稍后再访问，会让 OPM **访问违例、进程直接消失**（catch 不到）。
   所以 `PipeElementReader.ReadEc` 里的"查询 → 遍历 → 取值"全部在一个函数内完成，
   产出的只有纯数据（`AllProperties` / `Topology` / `MoveProbe`）。
2. **不拿可能不存在的属性名去问 Bentley**：`ECValue.GetValue()` 查一个该实例没有的属性
   会让 OPM 直接崩掉。所以先枚举实例上实际存在的属性，只读其中存在的那些。
3. **EC 读取不在点取工具的回调里做**：实测在 `OnDataButton` 回调内部访问 EC 实例会让 OPM 崩溃。
   因此 `PipePickTool` 只把元素 ID 入队，真正的读取由 `PipeAlignDialog.ProcessPendingPicks`
   在 `BeginInvoke` 排到消息队列之后执行（另有 150 ms 定时器兜底，但**绝不**退化成在回调里直接读）。
4. **元素身份必须带着模型引用一起传**：`ElementId` 只在它自己那个文件的 ID 空间里有效，
   参考文件里的管道与活动模型里的元素完全可能同号。`PipeInfo.Source` 存的就是
   `LocatedElement`（模型引用 + 元素 ID），重新读取（`ReloadPipes`、`PIPEALIGN DEBUG`）时
   必须原样带回，否则会读成另一个构件，甚至把参考元素误判成可改。
   判等 / 去重一律用 `PipeIdentity.Key(pipe)`，不要自己写 `ElementId` 比较。

---

## 6. 日志与排查

* **正式日志**（指南 §30）：短摘要，写进 Message Center 与
  `%LOCALAPPDATA%\PipeAlign\PipeAlign_debug_log.txt`，形如：

  ```text
  PipeAlign started.
  Reference pipe: P-101.
  Alignment mode: BOTTOM.
  Surface mode: PIPE.
  Reference elevation: 4890.500 mm.
  Target pipes: 8.
  Moved pipes: 7.
  Already aligned: 0.
  Skipped pipes: 1.
  Failed pipes: 0.
  ```

* **详细日志**（逐根管的几何、EC、单位标定、移动能力探测、逐级尝试记录）只写文件，不刷屏。
* EC 全量属性只在 `PIPEALIGN DEBUG DUMP` 或配置项 `DumpEcProperties=true` 时输出。
* 排查顺序建议：
  1. `PIPEALIGN DEBUG` —— 先确认能不能识别 PIPE、能不能拿到中心线与外径、单位标定是否可信、
     移动能力探测（`移动能力探测：` 那一行）是否通过；
  2. 看 `%LOCALAPPDATA%\PipeAlign\PipeAlign_debug_log.txt` 尾部的"逐级尝试记录"；
  3. 再判断是 `TopologyCheckMode` 太严，还是该版本的提交 / 更新步骤还没接上。

---

## 7. 离线自检

纯计算层可以在没有 OPM 的机器上跑（对应指南 §38 的 T01～T20 与 §34 的算例）：

```powershell
dotnet run --project 管道对齐\Development\PipeAlignCheck\PipeAlignCheck.csproj -c Release
```

它**链接**（不是复制）`PipeAlign_CS\Domain\` 与纯计算 `Services\` 的源文件，
因此断言的对象就是插件真正跑的那份代码。

配套的开发期工具（同样不参与主工程编译）：

```powershell
# 只读元数据转储：确认 Bentley 程序集的真实类型与方法签名，不加载、不执行目标程序集
dotnet run --project 管道对齐\Development\ApiDump -- <assembly.dll> [类型名正则] --members --all

# API 可用性探针：验证 Bentley.OpenPlant.Modeler.Api 这个混合模式程序集里
# 哪些成员真的能被 C# 消费（原生指针参数的成员不行）
dotnet build 管道对齐\Development\ApiProbe\ApiProbe.csproj -c Release
```

`Development\ApiDump\dump\` 里留了四份与本插件直接相关的签名清单（OpenPlant 业务对象 API、
SDK、接口、Building.Mechanical.Components），改代码前查签名比猜要快。其余 Bentley 平台程序集的
清单没有入库 —— 需要时用上面的命令现生成即可。

> ⚠️ **签名清单会骗人，必须当"线索"而不是"事实"用。**
> 元数据里标着 `public` 的成员，C# 未必能用：`BMECObject.InitTransform()` 在清单里是
> `method public void InitTransform()`，但 C# 编译器报"未包含该定义"。
> 任何要在代码里调用的成员，**先用 `Development/ApiProbe` 编译验证一遍**再去写业务代码。

---

## 8. 与开发指南的对照（2026-10-04 审计后）

结论：基础计算与交互已实现，但尚未完成指南 §38～39 的正式验收。不要将离线测试或历史少量成功日志当成全功能验收。

| 指南 | 当前状态 |
| --- | --- |
| §2～3、§5～7、§9～16、§26、§31～35 | 基准管独立选择，水平直管校验，Bottom / Center / Top 与保温计算，工具、窗口和命令已实现；PIPE 资格主要按 schema/类名分类，派生类覆盖仍需项目验证 |
| §8、§36 中心线优先 | 已修复：包围盒仅作诊断，取不到真实中心线时拒绝正式对齐 |
| §17 单位 | 毫米业务层、UOR 边界换算与 EC 长度标定已实现；英制 DGN 未实测，离线 T15 只验证属性比例，不是英制项目验收 |
| §18～20 移动与适配 | 分级调用、缓存取对象、EC 写回、几何 + EC 位移复核已实现；正式数据一致性仍需真实模型、保存重开和 ISO 验证 |
| §21～22 默认安全模式 | 已修复对端端口与构件身份混用；连到不移动对象或相连目标位移不同时跳过；未知连接拒绝 |
| §23～24 Move Group（后续扩展） | 已修复：按连通分量统一 ΔZ，管件/竖管只跟随；种子冲突、基准管在组内或不可写成员均拒绝。真实组移动尚未复测 |
| §25 预览 | 已改为 COM TransientElementContainer，不 AddToModel；显示、清理及英制主单位换算需 OPM 实测 |
| §27 执行检查 | 重读对象、批量预检查、移动后位置及连接对象集合复核已实现；尚未替代官方 Connectivity Check |
| §28～29 Undo / 恢复 | 必须成功建立撤销组和事务位置才执行；每级失败回退该级事务，整批失败回退批次；一次 Undo 的宿主行为仍需实测 |
| §30 日志 | 文件详细日志与界面摘要已实现，错误总原因可见；正式摘要仍有英文文案 |
| §37 性能 | 快照缓存和计划计算已实现；逐级复核仍逐元素读取 EC/连接，未做完整大批量性能测试 |
| §38～39 验收 | 38 条离线断言通过；T17～T20 及真实英制模型、真实 Move Group 尚未验收 |
| §4、§40～42 | Route Adjust 属后续版本，未实现；开发阶段和建议不能当作自动完成的验收项 |

完整发现、修复文件与实测步骤见 [评估报告](../管道对齐功能评估_2026-10-04.md)。

## 9. 本轮验证与复测

2026-10-04 现场追加修复：带弯头管道报「读取端口失败：集合已修改」是遍历 SDK 活 Ports 列表时对端查询刷新该列表所致。Ports 与 ConnectedComponents 现在先复制集合再遍历；普通 DgnElementSchema 实例不再进入 OpenPlant 探测，避免错误的 LENGTH 警告。本追加修复已编译，仍需宿主复测。截图中的 SINGLE 模式会拒绝单独挪动与弯头相连的管道；整体移动应选择 GROUP。

```powershell
dotnet build 管道对齐\PipeAlign_CS\PipeAlign.csproj -c Release --no-restore
dotnet run --project 管道对齐\Development\PipeAlignCheck\PipeAlignCheck.csproj -c Release --no-restore
dotnet build 管道对齐\Development\ApiProbe\ApiProbe.csproj -c Release --no-restore /p:ConnectivityOnly=true
```

主工程与连接 API 探针均为 0 错误、0 警告。离线断言不能执行 Bentley 事务、EC 写回或图形刷新。
历史 ApiProbe 默认包含不可消费的原生接口探针；本轮只编译独立的 ConnectivityOnly 路径。

产物：`bin\Release\net48\PipeAlign.dll`。本轮没有自动替换用户 AddIn 目录中的 DLL，也没有操作 DGN。
关闭 OPM 后按 §1.2 复制新版 DLL，再启动加载。连通管线选择「连同连通对象一起移动」，先选一根水平管作为整组起点；整组有多个起点时必须需要同一个 ΔZ。

必须实测：孤立管上下移动、连通管及弯头整组移动、边界拒绝、预览不保存到模型、取消与关闭清理、一次 Undo 撤销整组、保存重开、官方 Connectivity Check、ISO 以及英制项目。

## 10. License

仅用于项目内部，版权归作者所有。
