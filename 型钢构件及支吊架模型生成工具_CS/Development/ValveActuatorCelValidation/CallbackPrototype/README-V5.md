# V5：以 GEARBOX_OPERATOR 为基准替换 CEL 外形

用户已确认 V4 官方流程能够放置，同时反馈手轮只有一个位置调整按钮。本版新增齿轮箱路线，供用户在 OPM 中比较调整行为；Agent 未启动或操作宿主。

## 本版内容

- 新测试类 `SSP_CEL_GEARBOX_OPERATOR` 继承原生 `GEARBOX_OPERATOR`；处理器 `CelGearboxComponent : GearBoxOperatorScript`，保留原生 Setup，重写 Create3DElements。
- 返回内嵌 CEL 克隆，并按本机 SDK 的 `GearBoxOperatorDraw` 保留方向标记：原点 `(0,0,0)`、方向 `(-1,0,0)`、朝向 `(0,0,1)`。不生成原生齿轮箱实体。
- 继续使用 `Topwork / TopworksPlacementTool` 和 `BMECApi.StartPlacement`。阀门点选、安装变换、确认、关联和取消均走官方工具。
- 保留 `SSP_CEL_HAND_WHEEL / CelHandwheelComponent`，旧手轮件不自动转成齿轮箱。未修改原生 HAND_WHEEL、GEARBOX_OPERATOR 或已有测试类。

DLL 版本 `5.0.0.0`，同名 `ValveActuatorCallbackCheck.dll`。编译零警告零错误；此结果不代表宿主按钮、关联或随动已验证。

## 更新方法

1. 正常退出 OPM。保留原 DLL 和当前两份 Schema 的备份；包中 `OriginalSchemas` 是准备时读取的当前源副本，包含先前的手轮测试定义。
2. 用包内 DLL/PDB 更新上次加载的位置：

   ```text
   E:\Code\Bentley_Python_plugin\型钢构件及支吊架模型生成工具_CS\bin\Release\net48\ValveActuatorCallbackCheck.dll
   ```

3. 将包中 `PreparedSchemas` 内以下两份 XML 替换至同一测试工作集的 Schemas 目录。`preparation-receipt.json` 是核验记录，不复制到工作集。

   ```text
   OpenPlant_3D.01.08.ecschema.xml
   OpenPlant_3D_Supplemental_Modeling.01.08.ecschema.xml

   C:\ProgramData\Bentley\OpenPlant 2024\Configuration\WorkSpaces\CINF_International_Projects_Workspace\WorkSets\CINF_F1263AA\Standards\OpenPlant\Schemas
   ```

   本次新增独立齿轮箱类，因此与 V4 不同，需要同时更新两份 Schema。副本只追加这个新类，已核验所有旧节点保持不变。如果你在包生成后又编辑过源 Schema，请先用准备脚本从最新源重新生成，避免覆盖后续修改：

   ```powershell
   .\Prepare-TestSchema.ps1 -SourceSchemaDirectory '你的当前Schemas目录' -OutputDirectory '一个尚不存在的输出目录' -BaseClassName GEARBOX_OPERATOR
   ```

   脚本只生成副本，不安装或启动宿主；若源中已存在同名新类则拒绝覆盖。

4. 重开同一工作集，使用测试 DGN 副本。加载更新后的 DLL：

   ```text
   mdl load "E:\Code\Bentley_Python_plugin\型钢构件及支吊架模型生成工具_CS\bin\Release\net48\ValveActuatorCallbackCheck.dll"
   ```

## 测试步骤与预期

1. 先在一个没有执行机构的原生阀门上测试。无需预选阀门或普通 CEL，直接运行：

   ```text
   ACTUATORCALLBACK PLACE
   ```

   或显式 `ACTUATORCALLBACK GEARBOX`。两者等价；`CREATE` 也是 PLACE 的兼容别名。

   **预期：**进入官方执行机构工具，点选阀门后出现用户 CEL 外形，按官方提示调整并确认。应使用齿轮箱的原生交互能力；按钮数量和各按钮对派生类的实际作用仍需本轮验证，不能仅凭基类或编译结果判定。普通原生 GEARBOX_OPERATOR 可在旁边另一只阀门作对照。

2. 选择刚放置的 CEL 执行机构，检查原生调整入口，依次尝试位置、方向调整（以原生工具实际提供的入口为准）。

   **预期：**当官方操作改变整个构件的安装位置或方向时，CEL 整体响应，保持阀门关联，外形不变回原生齿轮箱。原点仍是 CEL 新增圆柱的底部圆心；检查它是否与用户定义的阀门外表面交点重合。没有添加自动安装偏移。

   **边界：**这是固定整体 CEL，不是参数化齿轮箱拆件。仅改变 HANDLE_OFFSET、TOTAL_HEIGHT、箱体尺寸等原生尺寸字段，不保证 CEL 内部零件随之移动或缩放；若某个按钮只修改这些字段而不改变安装变换，需要进一步接入该参数。请记录该按钮名称及操作前后 PROBE 日志，不以“出现按钮”代替调整生效。

3. 官方操作结束后，分别只选择阀门、只选择执行机构，各运行一次：

   ```text
   ACTUATORCALLBACK PROBE
   ```

   **预期：**阀门 `ForwardOperatorCount=1`，子类为 `SSP_CEL_GEARBOX_OPERATOR`；执行机构 `ReverseParentCount=1`，指回同一阀门。处理器为 `ActuatorCallbackCheck.CelGearboxComponent`，`IsParametric=True`。PROBE 同时记录安装 Transform、九项齿轮箱参数及 ANGLE 等，便于比较调整前后。

4. 只移动/旋转父阀门，检查 CEL 随动；再检查重生成、Undo/Redo、保存关闭重开。

   **预期：**外形保持 CEL，无重复件，关联保留。右键取消新放置时不应留下半成品。本轮成功范围以你的实际反馈和关系日志为准。

5. 若需与已成功的手轮路线对照，在另一只空阀门上运行 `ACTUATORCALLBACK HANDWHEEL`。旧件仍使用手轮处理器，不会自动升级。

## 日志与固定资源

日志目录：`%LOCALAPPDATA%\SteelSectionProbe\logs\ActuatorCallbackCheck\`。

齿轮箱日志文件名包含 `gearbox_place` / `gearbox_callback`；应有 `Version=5`、`Class=SSP_CEL_GEARBOX_OPERATOR`、`PlacementTool=TopworksPlacementTool` 和 `CallbackResult=CEL geometry clone + native gearbox direction marker`。首次启动返回只表示工具请求已返回，不代表已完成放置或建立关系。

请保留调整前后 PROBE 和最新齿轮箱 place/callback 日志。若仍只有一个调整按钮，也请记录普通原生齿轮箱的对照结果。

固定 CEL：`气动执行-DN800`；资源 SHA256：`4DD17E6A4F44542380CB82DBCC60A32D1EA836DD99EA1987575F84458275FF6C`。仅验证 1000000 UOR/m 三维模型。原生尺寸字段（含共同继承的 LENGTH/DIAMETER）初始为 1、HANDLE_OFFSET/ANGLE 为 0，仅用于原生初始化，不代表执行机构的实际尺寸；几何完全取自 CEL。

每进程最多启动 16 次，正常退出 OPM 后释放验证期对象。包不含 Bentley SDK DLL，不更新正式主插件。回退时先退出 OPM，再恢复本次备份 DLL/Schema；已保存新齿轮箱测试件的 DGN 应保留 V5 环境，或在副本中撤销/移除测试件后再回退。V4 源码及 DLL 备份位于 `Runs/20261031_V4PlacementUserConfirmed`。
