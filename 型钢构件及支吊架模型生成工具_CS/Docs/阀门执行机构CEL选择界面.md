# 阀门执行机构：先选择 CEL，再点选阀门

重开后点击旧件出现 `SteelSectionProbe` 找不到并崩溃时，先按[程序集加载错误处理](执行机构重开后程序集加载错误.md)显式加载主插件验证，再安装自动加载 cfg。首次放置时手动加载一次不会保证下次启动仍加载；需把处理器作为已保存组件的运行依赖部署。

2026-10-31 后续修正版V6.1：用户截图的“只有一个调节柄”源于原生调节器按实际类名处理，派生类读取LENGTH/DIAMETER，先前1mm占位使三柄重叠。新增件现按CEL范围设置并回读控制距离；CEL及原点不变。V6已安装环境只更新主插件DLL/PDB，不再改Schema；旧件不自动更新，请新放验证。[详细原因与步骤](../Development/ValveActuatorCelValidation/Runs/20261031_GripOverlap/原因及V6.1测试.md)。下文V6首次安装步骤保留。

2026-10-31，CEL 选择界面验证版（V6）。当前已完成主插件界面与代码、离线检查及编译；未由 Agent 启动 OPM。官方放置、调整按钮、二进制属性的实际 DGN 持久化、重生成、随动及重开效果由用户验证。

## 原来的 CEL 从哪里来

V3～V5 验证 DLL 使用编译时内嵌的 `Resources/actuator.cel`，原始来源：

```text
C:\ProgramData\Bentley\OpenPlant 2024\Configuration\Organization\Cell\阀门执行机构.cel
```

固定单元为 `气动执行-DN800`，SHA256 为 `4DD17E6A4F44542380CB82DBCC60A32D1EA836DD99EA1987575F84458275FF6C`。运行时从 `ValveActuatorCallbackCheck.dll` 提取到本地校验缓存，不会每次重新读取上述原文件；修改原文件不会自动更新旧验证件。

新界面读取用户选择的 CEL 文件。一个 CEL 库可以包含多个模型，文件与库内单元均由用户选择，没有把原模型名写死到新处理器中。

## 一次更新

1. 正常退出 OPM，备份当前主插件 `SteelSectionProbe.dll / .pdb` 和两份工作集 Schema。旧 `ValveActuatorCallbackCheck.dll` 保留，已有 V3～V5 件仍使用它。
2. 将本包的 `SteelSectionProbe.dll / .pdb` 更新至此前主插件加载目录。常用目录是：

   ```text
   E:\Code\Bentley_Python_plugin\型钢构件及支吊架模型生成工具_CS\bin\Release\net48
   ```

   本次是更新主插件，并非用这个文件替换 `ValveActuatorCallbackCheck.dll`。主插件产品版本仍为 1.0.0；本轮构建身份以包内 manifest 的 MVID/SHA256 为准。原授权规则保持。

3. 将包中 `PreparedSchemas` 的两个 XML 替换到同一测试工作集：

   ```text
   OpenPlant_3D.01.08.ecschema.xml
   OpenPlant_3D_Supplemental_Modeling.01.08.ecschema.xml

   C:\ProgramData\Bentley\OpenPlant 2024\Configuration\WorkSpaces\CINF_International_Projects_Workspace\WorkSets\CINF_F1263AA\Standards\OpenPlant\Schemas
   ```

   `preparation-receipt.json` 只作核验，不复制到工作集。副本新增独立的 `SSP_CEL_VALVE_ACTUATOR`，继承 `GEARBOX_OPERATOR`，几何处理器为主插件内的 `SteelSectionProbe.CelValveActuatorComponent`。所有原有节点及旧测试定义保持，未覆盖原生齿轮箱/手轮处理器。

   包内 `OriginalSchemas` 是生成副本时的源文件。若源 Schema 后来又改过，先基于最新源重新生成，避免覆盖后续编辑：

   ```powershell
   .\Prepare-TestSchema.ps1 -SourceSchemaDirectory '你的当前Schemas目录' -OutputDirectory '一个尚不存在的输出目录' -BaseClassName GEARBOX_OPERATOR -SelectableCel
   ```

   脚本只生成副本，源中已存在同名新类则拒绝覆盖。

4. 重开 OPM、同一工作集与测试 DGN 副本，加载更新后的主插件。可通过主插件首页“建模类→阀门执行机构”进入，或执行：

   ```text
   mdl load "E:\Code\Bentley_Python_plugin\型钢构件及支吊架模型生成工具_CS\bin\Release\net48\SteelSectionProbe.dll"
   STEELPROBE ACTUATOR
   ```

   `ACTUATORCALLBACK PLACE` 仍是旧固定 CEL 验证入口，不会打开新界面。

## 使用方法和预期效果

1. 点击“选择 CEL”，选择文件；从“库内三维单元”下拉框选择执行机构。界面显示真实离线几何预览，可以切换等轴测/俯视。预览不写模型；图片显示失败时仍可尝试开始，由原生几何读取独立校验。
2. 点击“开始放置”，再到视图中点选没有执行机构的原生阀门，按官方提示调整并确认。无需预选阀门或普通 CEL。放置期间文件和单元选择锁定，点“结束”或按官方流程右键结束后可再次选择。
3. 预期外形来自本次选择，官方 Topworks 工具负责安装、关系与确认。位置使用 CEL 自带原点；用户原型号仍以新增圆柱底部圆心为约定基点。未增加自动补偿，须校核该点与阀门外表面交点是否吻合。
4. 换选另一个单元，在另一只空阀门上放置。预期两件保持各自外形；后来改变界面选择或源 CEL 文件，不应使已放置件变成新的选择。
5. 结束放置，分别只选择阀门、只选择执行机构，运行只读校核：

   ```text
   STEELPROBE ACTUATORCHECK
   ```

   预期阀门 `ForwardOperatorCount=1`，子类为 `SSP_CEL_VALVE_ACTUATOR`；执行机构 `ReverseParentCount=1` 并指向同一阀门。执行机构应有 `PersistedCelDataVerified=true`、所选单元名、对应资源哈希及字节数，处理器为 `CelValveActuatorComponent`、`IsParametric=True`。同时记录 Transform、齿轮箱尺寸/角度字段，便于比较按钮操作前后。新命令也能查看旧验证件的关联，但仅校核新类的 CEL 数据。
6. 验证整体位置/方向调整、父阀门移动/旋转、重生成、Undo/Redo、保存关闭重开。可在保留备份后临时移走原 CEL 文件，再重开并重生成：预期仍读取实例保存的内容，而不是另一个当前选项。最后恢复原文件。退出重开后再次运行校核，检查数据哈希、单元名和关联仍一致。

原生齿轮箱调整按钮的数量和实际作用仍需实测。本版是固定整体 CEL，原生尺寸参数不会自动缩放或分别移动 CEL 内部零件；若某个按钮只修改 HANDLE_OFFSET 等尺寸而不修改整体安装变换，需要进一步映射。不要仅凭按钮出现就判定调整生效。

## 数据与当前边界

点击开始时读取一个完整的磁盘文件快照，校核该快照中所选单元，写入每个执行机构独立的 EC 属性：版本、单元名、源路径、SHA256、CEL 二进制数据与请求标记。几何回调从实例中的二进制内容恢复校验缓存，缓存键包含资源哈希与单元名，并区分活动 DGN/模型。源路径只用于追溯，不作为重生成的依赖；新主插件不内嵌固定阀门 CEL。

整个库文件会保存在每个执行机构实例中，方便重开恢复；多模型大库会增加 DGN 体积。当前限制文件非空且不大于 16 MiB；支持三维 Graphic 单元、源主单位 mm、1000 UOR/mm、GlobalOrigin 为零；活动三维模型为 1000000 UOR/m。其他单位/分辨率先明确拒绝，避免比例错误。界面可列出三维点单元，但其开始按钮会禁用。

仍使用官方 `BMECApi.StartPlacement`；插件不手工设置 RelatedInstance、不调用 Create/Serialize、不新增阀门关系或删除普通 CEL。离开/关闭页面会结束本页拥有的原生工具，不结束其他请求的工具。验证期每进程最多启动 16 次、缓存 32 个模型/资源组合；正常退出 OPM 后释放。使用过原生资源后拒绝单独卸载 DLL，请退出 OPM 后更新。

日志：`%LOCALAPPDATA%\SteelSectionProbe\logs\ValveActuator\`。请保留本轮 `place`、`callback`、调整前后及重开后的 `inspect` 日志；命令启动返回不等于安装或关联成功。纯离线检查中的 EC、CAD 与放置接口使用替身，不能证明宿主的二进制保存和交互已通过。

源码分层：`Domain/ValveActuator` 快照与校验，`Data/ValveActuator` 读取，`OpenPlant/ValveActuator` 属性/几何/官方工具边界，`UI/ValveActuator` 现有停靠工作区页面。首页总计 36 个可用功能、1 个占位（建模 15、支吊架 18、查询 3）。新页面复用 ModelingTheme、PrototypeChrome 与 CelLibraryPreviewControl。

本轮离线验证：38 项快照/属性协议/真实 XAML 交互及四档 DPI 布局检查；首页纯计算、83 项首页 WPF 检查、68 项停靠生命周期检查通过。授权/无授权主工程均零警告零错误。备份位于仓库 `迁移备份/阀门执行机构选CEL界面_20261031`。回退前退出 OPM，并处理测试 DGN 内的新类实例或保留本轮环境用于读取；不能移除仍被已保存测试件使用的类和处理器。
