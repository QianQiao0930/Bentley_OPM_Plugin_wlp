# PipeAlign：AI 与开发者协作规范

## 当前用户授权（2026-10-04）

UI依据../ui-share：480×960逻辑像素竖版，样式在UI/PipeAlignDialog.Layout.cs集中定义，原业务事件留在PipeAlignDialog.cs。管道明细为OwnerDraw ListBox卡片，原ListView只存行数据；移除必须读取卡片选择，不得回到隐藏ListView选择。不要显示禁用Z位移框或引入额外成功确认。UiLayoutCheck为离线布局桩，不验证SDK停靠及EC行为。

用户已明确要求实现锁 Z 轴的水平管随动、竖直直管单端伸缩，固定另一端；该授权覆盖下文 V1 不做 Route Adjust 的旧范围限制。只实现 Z 向受限调整，不自动生成管段，不处理斜管或复杂分支歧义。
用户要求正常操作无重复确认：点击【应用】即授权执行，正常成功用状态栏反馈，只有错误才弹窗。下文“应用并确认”不再要求额外确认对话框。
用户现场确认 Undo 失效：禁止继续把调用 SaveAndCleanUpUndo 当成撤销已验证，需使用明确的 DGN 事务边界，并在交付中说明宿主复测状态。

本文件适用于 `管道对齐/PipeAlign_CS/` 及其全部子目录，包括 `管道对齐/Development/` 下的开发期工具。

它既是人类开发文档，也是后续编码 Agent 的执行规范。任何改动前请先读本文件与
[`README.md`](README.md)，再检查真实代码；**不要只根据文件名或旧对话猜测当前实现**。

需求来源是 [`../管道对齐插件开发指南.md`](../管道对齐插件开发指南.md)（下称"指南"）。
与指南冲突时以指南为准，并同步更新 README 的对照表。

---

## 1. 项目目标与边界

PipeAlign 是 OpenPlant Modeler 2024 的独立 C# AddIn：按一根**基准管**的标高，
把一批**目标管**的管底 / 管中心 / 管顶对齐过去。

**V1 刻意不做的事**（指南 §3.2、§4、§23）：

* 不处理斜管、弯头、三通、异径管、阀门、法兰、支吊架、仪表、设备管口**作为被直接选中的目标**；
  它们可以作为 Move Group 的成员被一起平移，但不能单独拿来对齐；
* 不做"自动改竖向管段与弯头来重新布管"（指南 §4 的 Pipe Route Adjust）；
* 不通过"简单图形平移"模拟重新布管。

把这几条实现出来的冲动要压住：它们会让管线路由与轴测图静默失真。
Move Group 已实现（见 §5.1），但它的边界处理是**拒绝**而不是"尽力而为"。

---

## 2. 技术约束

* 目标框架 `.NET Framework 4.8`；平台 `x64`；**C# 语言版本 7.3**（不要用 C# 8+ 语法：
  没有文件级命名空间、没有 `record`、没有 `init`、没有 switch 表达式、没有可空引用类型）；
* `AllowUnsafeBlocks=true`，但因为 `Bentley.OpenPlant.Modeler.Api.dll` 是混合模式程序集，
  **大部分原生指针参数的成员 C# 根本消费不了** —— 新增调用前先编译验证，别照抄签名清单；
* 默认 Bentley 根目录 `D:\Program Files\Bentley\OpenPlant 2024\OpenPlantModeler`，
  用 `/p:BentleyRoot=` 覆盖；
* 源文件 UTF-8；**界面文案、异常消息、`NotificationManager.OutputPrompt` 一律中文**
  （异常消息会直接显示给用户）；`UOR` / `EC` / `DGN` / `OpenPlant` / `PIPE` / `ItemType`
  这类技术名词保留原文；
* 程序集名与 `MdlTaskID` 都是 `PipeAlign`，`MDL LOAD PipeAlign` 是兼容契约，不要改；
* `commands.xml` 的嵌入逻辑名固定为 `CommandTable.xml`。

---

## 3. 分层与依赖方向

```text
UI / Tools ──> Services ──> Domain
           └─> Data ──────> Domain
           └─> OpenPlant ─> Domain
Infrastructure：日志 / 报告，被 UI 与 Registration 使用
Registration ──> App / UI
```

强制规则：

* `Domain/` **不得**引用任何 Bentley 类型。它是纯数据 + 纯计算，
  因此必须能被 `../Development/PipeAlignCheck` 直接 `<Compile Include>` 链接。
  `Domain/PipeAlignOptions.cs` 的解析、`Domain/PipeTopology.cs` 的分类、
  `Domain/AlignmentPlan.cs` 的统计都属于这一层；
* `Services/` 里**不引用 Bentley**、因此必须能被自检工程链接的有：
  `ElevationCalculator`、`PipeValidationService`、`PipeAlignPlanner`、`LengthUnitCalibrator`、
  `UnitService`、`PipeGroupExpander`（它靠注入的 `Func<string, PipeInfo>` 读成员）；
  `PipeMoveService` 会碰 Bentley（撤销组、事务），**不得**被自检工程链接。
  **新增纯计算类时，记得在 `Development/PipeAlignCheck/PipeAlignCheck.csproj` 里补一行
  `<Compile Include>` 并加上断言** —— `Domain\*.cs` 是通配的，`Services\` 是一个文件一行；
* `Data/` 负责"元素 ↔ 纯数据"的转换，不得弹窗、不得做几何建模；
* `OpenPlant/` 是版本适配层，所有 `BMECObject` / `BMECApi` / `SchemaUtilities` 的调用
  只能出现在这里；换 OPM 版本时只改这一层；
* `Tools/` 只管交互状态机与预览生命周期；`UI/` 不得实现几何或校验算法；
* `Registration/` 只做命令入口。

**如果一个新类同时负责读 EC、显示控件、点选元素和移动几何，说明分层失败，必须拆开。**

---

## 4. 四条不能破的铁律（都是踩了崩溃 / 踩了坑才定下的）

1. **EC 实例绝不带出遍历。** `DgnECManager.FindInstances` 返回的实例只在这次遍历过程中有效；
   物化后留用、或返回给别的函数稍后再访问，会让 OPM **访问违例、进程直接消失**（catch 不到，
   日志都来不及写）。所以"查询 → 遍历 → 取值"必须写在同一个函数里，产物只能是纯数据。
   现有落点：`Data/PipeElementReader.ReadEc`、`OpenPlant/OpenPlant2024ObjectProbe`。
2. **不拿可能不存在的属性名去问 Bentley。** 先枚举实例上实际存在的属性，只读存在的那些。
   同理：读对端对象的**类名**是安全的，读它的其它 EC 属性就不一定。
3. **EC 读取不在点取工具的回调里做。** 实测在 `OnDataButton` 内部访问 EC 实例会让 OPM 崩溃，
   而同样的调用在普通脚本上下文里正常。`Tools/PipePickTool.cs` 只把元素 ID 交给回调，
   由 `UI/PipeAlignDialog.QueuePick` 入队、`ProcessPendingPicks` 在 `BeginInvoke` 之后读取。
   **不要为了"少一个类"把读取搬回工具回调。**

4. **元素身份必须带着模型引用一起传。** `ElementId` 只在**它自己那个文件的 ID 空间**里有效：
   参考文件里的管道与活动模型里的某个元素完全可能同号。所以 `PipeInfo.Source` 存的是
   `LocatedElement`（模型引用 + 元素 ID），`PipeAlignSession.TryReload` 与
   `PipeDebugReport.SourceOf` 都**必须**把它带回去；丢掉模型引用就会读成另一个构件，
   甚至把参考元素误判成可改（真实的安全漏洞，不是观感问题）。
   同理，**判等 / 去重一律用 `Domain/PipeIdentity.Key(pipe)`，不要自己写 `ElementId` 比较** ——
   只按 ElementId 去重会把跨文件的同号元素当成"重复选中"静默丢掉。

另外两条与点取工具相关的既有经验（与仓库另一个 C# 工程一致）：

* 点取工具的 `Begin()` 必须**幂等**：已在点取中时只重新提示，**不要"先 `End()` 再装新实例"**
  —— 那会先假发一次"已结束"（界面据此清空状态），新实例还可能被上一个实例的延迟清理带掉；
* 只读定位要用 `GetReferenceLocateOptions() => RefLocateOption.TreatAsElement` +
  `OnPostLocate` 兜底，否则参考文件里的管道点不中，用户只会看到"元素位于只读参考文件之中"。

---

## 5. 最重要的一条设计约束：不许用没被证实的单位改模型

指南 §18 要求优先用 OpenPlant 对象接口移动，但**单位没有官方保证**。
猜错单位的后果不是失败，而是把管道挪到几百米之外。

因此：

* 移动能力与单位只在**读取阶段**、用**该元素自己的几何**探测一次
  （`OpenPlant2024ObjectProbe.ProbeMoveCapability`），结论写进 `PipeInfo.MoveProbe`；
* 探测要**两步都过**才算证实：
  (1) **长度比** `|GetNthPoint(1)−GetNthPoint(0)| ÷ 几何长度` 必须等于已知候选之一
  （"每毫米多少 UOR" 或 1.0 = 毫米），否则拒绝；
  (2) **端点坐标比对**：把两个 API 端点换算成毫米后与**独立几何通道**读出的管轴端点
  逐分量比较（两种端点顺序都试），最大分量误差必须小于 1 mm。
  `Transform3d.Translation` 另按同一单位与管轴端点核对；
* **探测不通过就拒绝移动**，并在结果里说明原因。新增任何"直接写模型"的快捷路径前先想清楚：
  你凭什么确定单位？如果答案是"文档上说是 UOR"，那就是没被证实；
* ⚠️ **换算方向必须写清，不能靠变量名暗示。** 这里真的错过一次：`ApiUnitsPerMillimeter`
  的含义是"每毫米多少 API 单位"，所以 **mm → API 是乘、API → mm 是除**。
  当时的核对代码在"应该除"的地方乘了，于是所有 Z≠0 的管都被误判成"接口不可用"，
  而 Z=0 的管因为 `0×1000=0` 蒙对，看着又像正常。写这类换算时请：
  (1) 在方法名或注释里写明方向（现有 `ToApiUnits` / `PointErrorMm` 就是这么命名的）；
  (2) 用**独立来源**的坐标去断言（几何通道读出的端点），而不是只比一个标量比值 ——
  单看"长度比 = 1000"两个方向都能自洽；
  (3) 加一条 Z≠0 的用例，别让原点上的巧合掩盖错误；
* 每次移动之后必须用**独立几何通道**复核（`Data/PipeGeometryVerifier`），
  复核不过就回退并降级到下一级；三级都不过 → 失败 → **立即停止后续修改**（指南 §29）。
  复核现在读**两路**，缺一不可：元素几何（用户看到的）与 EC 变换矩阵
  （`TRANSFORMATION_MATRIX.M11`，数据模型里的）。只有这样才能把"没写进去"和
  "写了但图形没重建"分开 —— 这两种情况要改的地方完全不同，第一轮实测时因为分不清，
  白白多猜了一轮。**改 `PipeMoveVerification` 时不要退回只看几何**；
* ⚠️ **对象必须通过 OpenPlant API 取，不能 `new`。** 实测：`new BMECObject(instance)` 拿到的是
  没挂到文档上的副本，`SetLinearPoints` / `Transform3d` 全都不报错、读数却纹丝不动。
  正确做法是先 `BMECApi.Instance.ObjectCache.FindByInstanceId(instanceId)`，
  没有再用 `BMECApi.CreateBMECObjectForInstance(instance)` 创建并 `ObjectCache.Add`。
  见 `OpenPlant2024PipeAdapter.AcquireComponent`。**这条与"从缓存取到的对象不能 Dispose"
  是配套的** —— 释放它们会把 API 手里的活对象销毁掉；
* ⚠️ **`Refresh()` / `Resync()` 是"从数据模型读回来"，不是"写出去"。** 第三轮实测抓了个正着：
  修改后对象读数是 `39700.000`（`SetLinearPoints` 精确接受了 `−334328.935`），
  调完 `Refresh/Resync` 又变回 `374028.935` —— **改动被自己抹掉了**。
  所以 `Refresh` 只能放在写回**之后**用来刷新内存副本；放在写回之前等于自杀。
  当时这么写还顺带让 `BMECObjectWriter.Serialize()` 变得**根本没被测到**
  （轮到它时改动已经没了，它返回 `true` 但无事可做）——
  **排查这类问题时，顺序错了会让证据也失效**；
* ⚠️ **OpenPlant 对象接口只改内存副本。** 实测 `SetLinearPoints` / `Transform3d`
  都能正确接受改动（单位也对），但数据模型里始终是旧值，
  `BMECObjectWriter.Serialize()` 与连接更新都没能把它推出去。
  因此有了 **Level 2b：直接写 EC 变换矩阵 + `IDgnECInstance.WriteChanges()`**
  （`OpenPlant2024PipeAdapter.TryPersistEcTransform`）。它与 Level 2 一样是"OpenPlant 对象路径"，
  不是指南 §19 禁止的"只改图形"。
  * **Level 2b 必须与 Level 2 分成两级，绝不能合成一条链**：若 Level 2 其实写成功了，
    后面的直写会把位移**叠加两次**。分成两级、中间隔着复核与回退，结构上就不可能叠加；
  * 直写有三重门禁（缺一不做）：该元素已证实 API 坐标单位 → EC 的 Z 读数与"几何 Z × 单位"
    吻合（**用实测数据证明同坐标系，不靠"文档上说是 UOR"**）→ EC 当前值仍等于移动前基线
    （防止重复叠加）。任一门禁不过就拒绝，而不是硬写；
  * 属性名也**不能现编**：只有读取阶段确实枚举到了 `TRANSFORMATION_MATRIX.M11`
    （`PipeInfo.EcTranslationZRaw.HasValue`）才允许去访问它 —— 拿一个可能不存在的属性名
    去问 Bentley 会让 OPM 直接崩掉；
* Level 3（DGN 图形变换）默认关闭。它是"让数据与图形不一致"的做法，指南 §19 明确禁止
  当作正式实现。要打开它必须由用户在配置里显式承担风险，并在结果里提示。

---

## 5.1 移动范围：Safe Mode 与 Move Group

* `MoveScope.SelectedOnly`（默认）：只移动用户选中的管道；连到非移动对象就跳过（指南 §22）。
* `MoveScope.ConnectedGroup`（指南 §23）：沿连接关系展开整组，组内**同一个 ΔZ**。
  实现在 `Services/PipeGroupExpander.cs`（纯计算 + 注入的 `Func<string, PipeInfo>` 读取委托，
  因此能被离线断言）。
  * 成员策略在 `Domain/MoveGroupPolicy.cs`，类别判定复用
    `PipeConnectionClassifier` —— **不要另起一份"类名 → 类别"的关键字表**；
  * 遇到边界（管口 / 支吊架 / 仪表 / 未知类）→ **拒绝整组**，逐条列出边界。
    **绝对不要改成"能移多少移多少"的裁剪**：那会正好在边界处留下断口，比不移动更糟（指南 §24）；
  * 连通性未知、成员读不出来、超过 `MoveGroupMaxMembers` → 同样拒绝整组。**不猜移动范围**；
  * 组内成员在计划里标 `AlignmentPlanItem.AddedByGroup`，界面上行首加「＋」，
    否则用户会困惑于"行数怎么变多了"；
  * **不要把 Safe Mode 的拓扑过滤删掉**：在 GROUP 模式下它退化成一次交叉校验 ——
    组里若仍有"连到非移动对象"的成员，说明展开漏了东西，此时跳过比硬移安全。

---

## 6. 预览、确认、撤销

* 预览只画**临时直线**，不改动管道对象本身（指南 §25）；
* 重建预览时**先把新的一组全部写完，成功了再删旧的一组**；中途失败要把已建的部分删掉、
  保留旧预览（`Tools/PipeAlignPreviewSession.Rebuild`）；
* `重置`、`关闭窗口`、`应用完成后`、`参数变更` 都必须清理预览；
* 参数（模式 / 表面 / 容差 / 目标集合）一变，`_session.Plan` 必须置空，
  不能拿旧计划去执行；
* 一次 `应用` = 一次 Undo（指南 §28）：整批包在
  `PipeUndoScope` 的明确事务边界与 `BMECApi.StartUndoGroup / EndUndoGroup` 里；
  禁止调用 `SaveAndCleanUpUndo`，异常时 `CancelToPosition` 并检查返回状态；宿主撤销行为必须实测。
* 模型修改只在用户点击【应用】后执行；按当前用户授权不再二次确认，正常成功不弹窗。

---

## 7. 运行参数

* 所有容差与开关都在 `Domain/PipeAlignOptions.cs`，**不得写死在业务代码里**（指南 §11）；
* 配置是 `键=值` 文本（不是 JSON）—— 目的是让纯计算层不引入序列化依赖，
  也让现场能直接用记事本改；
* 新增配置项时**必须同时**：加属性 + 默认值 + `Apply` 分支 + `Serialize()` 输出 + README 表格，
  并保证非法值只忽略该行（返回默认值 + warnings），**绝不抛异常**；
* `Domain/PipeAlignOptions.Parse` 是纯函数，新增项要顺手在 `Development/PipeAlignCheck` 里加断言。

---

## 8. 单位约定

* 业务计算与领域模型**一律毫米**；UOR 换算只发生在 Bentley 边界，
  且只经由 `IUnitService`（指南 §17）；
* 读 `ModelInfo` 的地方**只有** `Data/DgnUnitServiceFactory`；
* EC 长度属性是裸 double，**不得假设是毫米**：用
  `Services/LengthUnitCalibrator`（"属性 `LENGTH` ↔ 几何长度"标定，比例 1.0 或 1000.0），
  标定不成立时退回"数值 < 1 视为米"的兜底并**明确提示用户**；
* 字段名要带上单位（`OutsideDiameterMm`、`DeltaZmm`、`HorizontalToleranceMm`）。

---

## 9. 新增功能的推荐步骤

1. 读本文件、`README.md`、指南的相关章节；
2. `git status` 看有没有用户尚未提交的改动，不要覆盖；
3. 先用 `Development/ApiDump` 查清 Bentley 的真实签名，用 `Development/ApiProbe` 验证
   C# 能不能消费该成员 —— **不要用"故意编译报错"的探针去猜签名**；
4. 先写 `Domain/` 的纯模型与 `Services/` 的纯计算，并在 `Development/PipeAlignCheck` 里加断言；
5. 再写 `Data/` / `OpenPlant/` 的边界适配；
6. 最后接 `Tools/` 与 `UI/`，并用 `Registration/Keyins.cs` + `commands.xml` 暴露入口；
7. `dotnet build -c Release` 必须 0 错误；
   新增警告要解释或消除；
8. 更新 `README.md`（功能、目录职责、与指南的对照表、验证状态）；
9. 交付时明确列出：改了哪些文件、验证到什么程度、**哪些只能在 OPM 里实测**。

---

## 10. 完成定义

一项改动只有同时满足下列条件才算完成：

* 放在正确的层，没有把 Bentley 调用泄进 `Domain/`；
* 没有破坏 §4 的四条铁律与 §5 的单位自证约束；
* 纯计算部分有离线断言，且 `Development/PipeAlignCheck` 仍然通过；
* 预览 / 确认 / 取消 / 清理的路径完整；
* 单位与容差约定清楚，容差走配置；
* `dotnet build -c Release` 通过；
* README 已更新，并说明了"已离线验证"与"仍待在 OPM 实测"分别是哪些。

做不到其中一项时，必须把它作为明确的待办或风险写进交付说明，**不得默认为"以后再说"**。

---

## 11. 禁止的实现方式

* 把 Bentley 类型引进 `Domain/`，让自检工程链接不了；
* 在工具回调里读 EC；
* 用没被该元素几何证实的单位 / 接口去写模型；
* 把 `Element.ApplyTransform` 当成默认移动手段；
* 在没有复核的情况下把"接口调用返回成功"当作"移动成功"；
* 移动失败后继续处理后面的管道（会留下改了一半的模型）；
* 在预览阶段就移动真实对象；
* 用全局静态变量共享大量可变状态（会话状态放 `App/PipeAlignSession.cs`）；
* 吞掉异常且不给用户任何状态提示；
* 改动 `型钢构件及支吊架模型生成工具_CS/` 或仓库里的 Python 插件 ——
  本工程与它们没有代码依赖，只借鉴做法。

---

## 12. 已知边界与后续工作

1. **移动已实测生效**（第四轮）：路径是 Level 2b（EC 变换直写 + `WriteChanges`），
   见 §5。仍需在 OPM 里继续核对的是：
   * **一次 Undo 是否撤消整批**（指南 §28）；
   * 对齐后重新打开模型、Connectivity Check 与轴测图是否正常（指南 §39 的 T18～T20）；
   * Move Group 在真实连通管线上的展开结果（§5.1）—— 尤其要确认"连接关系读得准"。
     读取器现在同时用 `Port.IsConnected` / `Port.ConnectedTo` 与
     `BMECObject.ConnectedComponents` 两个来源，**来源与条数写进日志**
     （`连接关系：…；对象来源 …；端口 N 个（已连 M）；ConnectedComponents K 个`）。
     现场曾出现过"明显连着邻管却报无连接"——若再遇到，把那一行发来，
     说明两个来源都没给数据，下一步要换用 OpenPlant 的关系查询 API
     （`BMECApi.GetRelatedJointsForComponent` / `GetJointConstituentComponents`）。
     在那之前 **`STRICT` 模式下的"无连接"结论不可全信**，而这会同时影响
     Safe Mode 的保护与 Move Group 的范围；
2. 写回链（`OpenPlant2024PipeAdapter.WriteOut`）是"一遍走完"，没有按步判定"哪一步才生效"。
   每步之后都已经读一次对象端点并记进尝试记录，接上判定即可指出生效点。
   **顺序绝对不要调整**：`Serialize` 必须在 `Refresh` 之前，理由见 §5；
3. 没有"记住上次用的模式 / 表面模式"（本仓库其它功能有这种做法）。要加就写进
   `%LOCALAPPDATA%\PipeAlign\`，并且读写失败一律静默回落；
4. `Deployment/install_to_addinpath.ps1` 只做"复制 + SHA256 校验 + 打印加载步骤"，
   **刻意不碰机器级设置**（MS_ADDINPATH / 注册表 / OPM 配置）。不要把它扩成会改环境变量的脚本。
   ⚠️ 该文件必须保持 **UTF-8 with BOM**：Windows PowerShell 5.1 会把无 BOM 的 `.ps1` 按 ANSI 读，
   脚本里的中文会乱码并直接导致语法错误。改完请确认 BOM 还在（首三字节 `EF BB BF`）；
5. `Tools/PipePickTool` 依赖 `DgnElementSetTool` 原生的框选能力，未单独处理 Fence；
6. **Pipe Route Adjust 未实现**（指南 §4：自动改竖向管段与弯头来重新布管）。
   Move Group 已实现（§5.1），Run Align 不需要单独做 —— 它就是 Move Group 的用法之一。

改动第 1、2 条涉及的代码时，**必须在交付说明里写清"没有实测、依据是什么"**。
