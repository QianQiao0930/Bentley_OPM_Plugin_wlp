# 型钢构件及支吊架模型生成工具：OpenPlant Modeler 2024 C# 版

## 上次输入

所有有参数输入的功能页都会跨会话记住上次输入。人孔、管夹、G2 锚板、N3/N4 和 N8 使用各自的 `LastChoice` 文件；型钢生成、构件特性查询、弯头耳轴、实体管口、立管耳轴、三角架、L 型架、门型架、T 型架和垫板使用按页面独立的 `*_last_input.json`。偏好存放在 `%LOCALAPPDATA%\SteelSectionProbe`，离开页面或关闭工具时写入，重新打开工具时恢复。统计页没有参数输入，因此无需保存。模型中的点选、预览与生成状态不属于上次输入。

## D7 L 型架

首页的“L 型架”入口对应 Python `D7-[L形_倒L形架].py`。点取两段相连的 L 形辅助折线，竖直段决定立杆 H，水平段决定横担 L；类型 1/2 为立杆在下，3/4 为立杆在上的吊架。子项 A～F 使用 `profiles.bin` 截面，E/F 仅适用于类型 1/3。面板输入 B 查表 1/2 荷载，始终显示当前 H/B 与该子项标准上限；超限不能更新预览。确认时一次写入固定的 `PipeSupportAssembly_L_PIPE_RACK`、`PipeSupportComponent_L_PIPE_RACK_Post` 和 `PipeSupportComponent_L_PIPE_RACK_Arm`，尺寸与编号只写实例属性。预览可更新或取消，返回首页时清理。纯计算检查在 `Development/LBracketCheck/`；Bentley 折线点取与扫掠需在 OPM 中实测。

## D5 / D6 / G12 / D19 三角架

首页入口为“三角架”，描述显示 `D5_D6_G12_D19`。先选择架型、A～D 子项和斜撑位置，再点取从生根端指向横担末端的水平辅助线；线长为 L2，面板输入 L1。D5 使用 H 型钢横担与角钢斜撑，可选两套 G2 端板及锚栓；D6 与 G12 使用单片槽钢，G12 增加四根膨胀锚栓；D19 使用背靠背双槽钢和端部连接板。实体型钢取本工程 `profiles.bin` 目录。确认前预览可取消，确认时写入 `PipeSupportComponents`。

清单保留 Python 的四种中文 `SupportType`、Assembly / Component 字段和构件数量。ItemType 名固定为 `PipeSupportAssembly_<组合代号>` 与 `PipeSupportComponent_<组合代号>_<角色>`；变化的编号、尺寸、规格写入实例值，不附加哈希。统计页仍按原前缀读取。纯计算检查：`dotnet run --project Development/TriangleBracketCheck/TriangleBracketCheck.csproj -c Release`。OPM 内的四种实体布尔、G12 锚栓朝向、D5 端板及预览清理仍需实测。

## N3 / N4 / N8 设备支架

首页分别提供 N3 单三角架、N4 双三角架和 N8 设备预焊件连接板入口。N3 点取设备表面至横担末端的水平辅助线；N4 点取设备中心至管中心的水平辅助线，并由设备外径、预焊件长度和线长计算 L1。两者均可选择 A～F 子型及斜撑在上或在下；N4 修改参数后需手动更新预览才能确认。N8 独立选择板型、方向及安装面后点取放置点。三个入口各自生成可取消的 Cell 预览，确认时写入 `PipeSupportComponents`；N4 可选的设备预焊件仅作 75% 透明参照，不计入清单。

规格与荷载表取自 `管道支吊架/模块/` 中的 Python N3、N4、N8 模块。纯计算检查位于 `Development/EquipmentSupportCheck/`。目前已通过 Release 编译和参数检查；OPM 2024 内的实际点取、实体布尔、预览清理及 ItemType 写入仍需实测。

N3/N4 斜撑与 Python 一样先延长两端，再分别按设备面及横担底面/顶面做实体差集剪切。三角架页面的操作栏固定在底部，窄面板也能看到“确定生成”。确认时先显示写入状态，并将三角架 ItemType 定义合并成一次检查与写入；状态栏会显示确认耗时。

N3/N4 与 N8 均**记住上次选择**（类型、子项、H、L2/L3/L4、设备外径、预焊件长度、各复选框、N8 的工况/安装面/朝向角），存于 `%LOCALAPPDATA%\SteelSectionProbe\bracket_last.json` 与 `n8_last.json`，重启 MicroStation 后仍然保留（N3 与 N4 各存一套，互不影响）。切换子项会把 H / L2 重置为该子项的最小值，这是既定行为，只在**进入页面时**才用记住的值覆盖。

N3/N4 参数页采用纵向字段和换行摘要，窄窗口可完整阅读。N4 的两根横担、两根构件 C 和六块筋板按连接顺序做实体并集；构件 C 顶面与横担顶面齐平。N3 筋板并入横担实体。若 Bentley 内核无法完成并集，预览会报错，避免留下相互穿插的独立构件。

N3 在规格区实时显示 `E = 横担长度 − H`（横担长度为辅助线长度减连接板厚度）。E 小于 150 mm 时以红字提示末端不符合图集要求，并禁止确认；等于 150 mm 可用。H、子项或辅助线变化后重新计算。

N3/N4 点取辅助线后自动生成首次预览；此后参数一经输入或选择就标记“更新预览 ●”并禁止确认。第一次点击更新按钮即重建预览，不需要先让输入框失去焦点。

## 立管耳轴（F6 / F7 / F10）

首页“立管耳轴”进入统一页面，顶部先选 F6 单耳轴、F7 双耳轴或 F10 小管径立管耳板，再设置该类型参数并点取管道或竖直辅助线。点取位置投影到轴线后确定放置标高；轴线与竖直方向夹角须在 5° 内。管道使用 EC 公称直径自动匹配，辅助线使用面板 DN。F6/F7 适用 DN50～DN1200，F10 适用 DN15～DN50。F6/F7 的端板 A/B/C、STD 壁厚及可选补强板按原 Python 表推导；F10 的长度 1/2/3、高度 A/B/C/D、固定 Y/N 分别控制两块耳板、底板及可选 M12 螺栓。

点取后先生成可撤销 Cell 预览，确认时才写入 `PipeSupportComponents`。切换类型、右键结束点取、取消预览、返回首页和关闭工作区均清理未确认元素。清单 `SupportType` 与 Python 保持一致：F6/F7 共用 `F6_F7-[立管的耳轴]`，F10 为 `F10-[小管径立管耳板]`。实现位于 `Domain/VerticalPipeSupport/`、`Data/VerticalPipeSupport/`、`Services/VerticalPipeSupport/`、`Tools/VerticalPipeSupport/` 和 `UI/VerticalPipeSupport/`。纯计算检查为 `Development/VerticalPipeSupportCheck/`；OPM 2024 中仍需对三个类型的布尔运算、参考管道点取、预览删除及 ItemType 写入进行实测。

独立的 .NET Framework 4.8 / x64 AddIn。运行时只加载 C# DLL，不启动 Python。当前提供型钢截面放置、沿路径扫掠、构件特性查询、弯头耳轴、立管耳轴（F6/F7/F10）、罐壁人孔、实体管口、放置管夹（A1 / A2 / A22 / E1 / K1 / T4）、G2 混凝土锚板与只读的支吊架统计，并按“工作区 + 功能页”组织，后续可继续接入各种支吊架功能。

VS Code 可打开仓库根目录的 [`型钢构件及支吊架模型生成工具.code-workspace`](../型钢构件及支吊架模型生成工具.code-workspace)。工程文件已更名为 `SteelSupportModeler.csproj`；为兼容已有 OPM 配置，输出 DLL、命名空间和 `STEELPROBE` 命令仍使用 `SteelSectionProbe`。

后续新增功能或由 AI Agent 接续开发前，请先阅读 [`AGENTS.md`](./AGENTS.md)。其中规定了目录职责、复用优先级、新功能接入步骤、Bentley 预览生命周期及交付验证要求。

## 功能

- 7 类型钢、1144 个规格：平行腿槽钢、普通热轧工字钢、热轧 H 型钢、斜腿槽钢、等边角钢、不等边角钢、HK 系列 H 型钢。
- 支持各类型钢插入基准、直线和真圆弧轮廓。
- 型钢页随规格和插入基准变化实时绘制二维截面轮廓预览。
- 在模型中连续放置二维闭合截面，支持动态预览、AccuSnap 和 AccuDraw。
- 在三维模型中选择开放路径，构造与起始切线垂直的截面并扫掠成 SmartSolid。
- 扫掠实体先作为预览写入模型；修改规格、基准或旋转角可重建，确认后附加 `PipeSupportComponents` 公共 ItemType。
- 可在确认扫掠后删除源路径。

## 工程结构

```text
型钢构件及支吊架模型生成工具_CS/
├─ App/                 AddIn 生命周期与功能页契约
├─ Registration/        Key-in 注册入口与 commands.xml
├─ UI/                  WPF 工作区、XAML 功能页、主题和预览控件
├─ Domain/              与 Bentley/UI 无关的型钢领域模型
├─ Data/                嵌入式型钢目录读取
├─ Services/            截面曲线、放置坐标系与扫掠几何
├─ Tools/               Bentley 点放置和路径定位交互工具
├─ Infrastructure/      公共 ItemType / 统计基础设施
├─ Resources/           运行时嵌入资源（profiles.bin）
├─ Development/         本地型钢规格源、轮廓计算和数据导出脚本
└─ Deployment/          DLL 更新脚本
```

新增支吊架功能时，建议以独立 Feature 目录承载其 UI、业务服务和 Bentley Tool，并实现 `IWorkspacePage` 接入 `MainWindow`。公共统计、主题、注册入口继续放在对应基础层，避免把新功能重新堆回一个窗体文件。

## UI 规范

工作区已迁移到 WPF/XAML，沿用仓库内支吊架面板的视觉语言：浅灰背景、白色卡片、微软雅黑、低对比度分区标题、固定底部实时状态栏和深色主操作按钮。首页以两列卡片列出全部功能入口，并按“星标 → 常用度”自动排序（见下节）；进入功能页后可返回首页选择其他模块。Bentley `Adapter` 只作为 `ElementHost` 的薄宿主，`WorkspaceView` 负责页面导航，`SteelSectionPage` 负责型钢页展示与事件协调，几何建模仍由 `Services/` 和 `Tools/` 完成。

## 型钢生成

7 类型钢（平行腿槽钢、普通热轧工字钢、热轧 H 型钢、斜腿槽钢、等边角钢、不等边角钢、HK 系列 H 型钢）共 1144 个规格，可放置二维闭合截面或沿开放路径扫掠成三维实体。

「03 当前截面参数」只显示 `Data/SteelSection/SteelSectionCatalog.cs` 登记的中文字段（高度 H、腹板厚度 tw、截面面积、理论重量…），名称与单位与 Python 原版 `型钢截面生成器/steel_sections/steel_registry.py` 的 `fields` 逐项一致；未登记的字段不会显示，界面上不会出现英文键。放置与扫掠的提示语、MicroStation 命令行名称与异常消息全部为中文。

```powershell
dotnet run --project Development/SteelSectionCheck/SteelSectionCheck.csproj -c Release
```

该检查读取嵌入的 `profiles.bin`，断言 7 个类型的字段顺序与 Python 注册表一致、字段在数据中齐备、中文名含汉字、单位合法。

## 首页功能排序与星标

首页卡片由 `Data/Home/HomeFeatureCatalog.cs` 的清单渲染（不再手写 XAML），顺序由 `Services/Home/HomeFeatureRanker.cs` 计算。首页顶部自带标题栏（应用图标 + 标题 + 副标题 + **搜索框** + **排序下拉** + **重置排序**），下方依次是「最近使用」与四个分区（建模类 / **HGT21629 支吊架** / 统计与扩展 / 规划中）：

> 2026-09-28 调整：「HGT21629 支吊架」收纳全部支吊架类功能（弯头耳轴、立管耳轴、放置管夹、混凝土锚板、N3/N4/N8）；建模类只保留通用建模（型钢、罐壁人孔、实体管口）。卡片尺寸固定 **240×124**（占位卡 240×84），整卡即入口按钮（Button 模板，悬停提亮 + 按压反馈）；首页宽度与功能页统一为 **560 DIP**（两列卡片 + 滚动条 + 页边距刚好放下），标题栏改成两行避免主标题被截断。卡片右下角的星标按钮与卡片是**并列关系**（不是卡片按钮的子节点），点星标只弹出 1～5 星的评分菜单，永远不会连带进入功能页；另外「最近使用」「常用优先」两种排序都先按星标档位排（≥3 星置顶、星级降序），再按时间/频率排，所以星标最高的功能不会被"用得少"挤下去。滚动条为定制细滑块（12 DIP 宽，圆角胶囊，悬停加深），由 `UI/Themes/Theme.xaml` 的 `ScrollViewer` 模板统一下发。

- **搜索**：输入关键词即时过滤卡片（匹配标题、说明或分区中文名），无匹配时显示提示；搜索期间隐藏「最近使用」。
- **排序下拉**：`默认排序`（星标 → 使用频率 → 出厂顺序）／`最近使用`（按最近进入时间降序）／`常用优先`（按衰减频率降序）。三种口径都先按分区分组，仅改变分区内顺序。
- **最近使用**：按 `LastUsedUtc` 取最近进入的至多 4 项，卡片左下角显示「刚刚 / N 分钟前 / N 小时前 / 昨天 / N 天前 / 日期」（`Services/Home/HomeRelativeTime.cs`，纯计算）。
- **分区**：每个功能的分区键在 `FeatureDescriptor.Category`，分区键/中文名/显示顺序的唯一来源是 `Data/Home/HomeCategories.cs`；`FeatureDescriptor.Icon` 决定卡片左侧图标（`UI/HomePage.xaml` 里的 `HomeIcon_<key>` 几何）。

| 关键字 | 方向 | 说明 |
| --- | --- | --- |
| 置顶区 | — | 星级 ≥ 3 才置顶；整个置顶区排在所有未置顶功能之前 |
| 星级 | 降序 | 5★ → 1★；1～2★ 不置顶，但仍在普通区里压过未评分 |
| 使用频率 | 降序 | 衰减计数 `Σ 该月次数 × 0.5^距今天数月`（半衰期 1 个月，保留 12 个月） |
| 出厂顺序 | 升序 | 从未使用、未评分时的兜底，等于改造前的首页顺序 |
| PageId | 字典序 | 全序兜底（`List.Sort` 不稳定，缺这级顺序会漂移） |

- **评分**：点卡片右下角的星标按钮，在弹出的菜单里选 1～5 星或「清除评分」。**评分后立即重排**（菜单一关就按新顺序重建，不必等回到首页）。同一功能若同时出现在「最近使用」与所属分区，两处显示同步更新。
- **卡片尺寸固定**：卡片固定 320 × 124（规划中占位卡 320 × 84），标题 1 行、说明 2 行，超长文字用省略号裁剪；列表用自动换行布局，放不下就换行。因此功能说明写多长、窗口拉多宽，卡片尺寸都不变，也不会横向溢出。首页窗口宽度**按实际内容自动校准**（两列卡片 + 页边距 + 滚动条，实测得出），所以右侧不会留出多余空白；功能页宽 560（均按当前屏幕 DPI 换算成设备像素），进入/返回模块时版式不会跳。
- **使用频率**：进入功能页时自动统计；同一次会话内同一功能只记一次，命令行入口 `STEELPROBE PLACE` 同样计数。
- **重置**：标题栏右侧「重置排序」清空全部星标与使用统计。
- **存储**：`%LOCALAPPDATA%\SteelSectionProbe\home_preferences.json`，只存 `PageId → {Stars, TotalUseCount, LastUsedUtc, MonthlyUse}`，**不存顺序**；文件损坏或不可写时静默回落到出厂顺序，不影响首页显示。
- **契约**：清单里的 `PageId` 必须与功能页 `IWorkspacePage.PageId` 逐字一致（不一致时状态栏报“未注册的功能模块”）；`Category` 必须是 `HomeCategories` 里的已知键，`Icon` 必须能在 `HomePage.xaml` 找到对应几何。新增功能页只需在 `HomeFeatureCatalog` 加一项（含分区与图标键），首页无需改动。
- 纯计算检查：`dotnet run --project Development/HomeCheck/HomeCheck.csproj -c Release`。

## 保冷立管导向架 L7

首页独立卡片进入。两种类型均先点取 DN15～DN150 立管或竖直辅助线，锁定安装标高，再在垂直于管轴的径向罗盘平面内旋转安装方向；竖直立管时罗盘显示在模型 XY 平面。类型 1 使用 A22 两螺栓管夹和构件 A，方向确定后继续拉伸 L；L 从管中心量至构件末端，默认及最小 300 mm，超过 1000 mm 时固定为 1000 mm。类型 2 使用 A24 四螺栓管夹，没有构件 A，方向左键确定后直接生成预览。确认后写入各自总成、承重夹板、管夹与紧固件的附加项；取消或离开页面会删除未确认预览。确认时在状态栏显示附加项写入耗时，详细分段计时保存在 `%LOCALAPPDATA%\SteelSectionProbe\statistics_trace.log`。

A22/A24 共用保冷间隙、螺栓与圆角算法；类型 1 构件 A 按计算管夹内径 A 选 ∠75×7（A≤100）、H100×100×6×8（100＜A≤450）或 H125×125×6.5×9（450＜A≤700）。承重夹板直接复用 T4 的 45° 对开圆环、开孔耳板及螺栓/螺母/垫圈建模，不生成 T4 底板和腹板；夹板沿管轴长度默认 300 mm，可在面板中调整。管夹位于夹板轴向正中。图纸没有给出防滑挡环的详细尺寸，暂不生成挡环。L8 尚未开放。

纯尺寸验证：`dotnet run --project Development/PipeClampCheck/PipeClampCheck.csproj -c Release`。

## 编译

```powershell
dotnet build SteelSupportModeler.csproj -c Release
```

项目默认引用：

```text
C:\Program Files\Bentley\OpenPlant 2024\IsometricsManager
```

如安装位置不同：

```powershell
dotnet build SteelSupportModeler.csproj -c Release /p:BentleyRoot="实际安装目录"
```

## 型钢规格数据维护

型钢规格的**可编辑源数据已放在本 C# 项目内**的 [`Development/profile_catalog/`](Development/profile_catalog/)；各类型钢使用下表中的文件。轮廓生成算法位于同目录对应的 `*_geometry.py`。这是一套仅供开发期生成数据的纯 Python 数学代码，无需原 `型钢截面生成器` 目录、OpenPlant Python 环境或原插件 UI。

| 型钢类型 | 编辑的规格文件 |
| --- | --- |
| 平行腿槽钢 | `steel_channel_data.py` |
| 普通热轧工字钢 | `steel_ibeam_data.py` |
| 热轧 H 型钢 | `steel_hbeam_data.py` |
| 斜腿槽钢 | `steel_tapered_channel_data.py` |
| 等边角钢 | `steel_equal_angle_data.py` |
| 不等边角钢 | `steel_unequal_angle_data.py` |
| HK 系列 H 型钢 | `steel_hk_data.py`（复用 H 型钢轮廓算法） |

修改已有规格时，在对应 `*_data.py` 中找到规格名，修改其尺寸值。新增同类型规格时，按该文件现有表格格式新增一行或一个条目，保持规格名唯一，并提供轮廓算法所需的全部尺寸字段。面积、重量及重心等字段若在该表中给出，也要同步核对；不要只改显示名称。若要新增一种型钢类型，还需新增数据与几何模块，并在 [`steel_registry.py`](Development/profile_catalog/steel_registry.py) 登记类型、名称与构造函数。修改截面形状或插入基准时，编辑对应 `*_geometry.py`。

在本项目目录重新生成资源并编译：

```powershell
python -B .\Development\export_profiles.py
dotnet build .\SteelSupportModeler.csproj -c Release
```

导出脚本会逐规格、逐插入基准检查轮廓是否闭合，并生成 [`Resources/profiles.bin`](Resources/profiles.bin)。该二进制文件通过 `SteelSupportModeler.csproj` 嵌入 DLL，运行时由 [`Data/RuntimeData.cs`](Data/RuntimeData.cs) 读取。**不要手工修改 `profiles.bin`；仅修改 `.py` 数据源也不会自动改变已编译的 DLL，必须重新导出并编译。**命令中的 Python 只用于开发期数据转换，C# 插件运行时不启动 Python，也不读取同级 Python 工程。

## OPM 中使用

将 DLL 输出目录加入 `MS_ADDINPATH`，然后输入：

```text
MDL LOAD SteelSectionProbe
STEELPROBE SHOW
```

也可以通过 `STEELPROBE PLACE` 打开工作区并立即进入截面放置。

若当前 DLL 被 OPM 占用，可先把新版本构建到备用目录：

```powershell
dotnet build SteelSupportModeler.csproj -c Release /p:OutputPath=bin\Release\net48_full\
```

退出全部 OPM 窗口后再执行：

```powershell
.\Deployment\install_new_version.ps1
```

## 验证范围

代码应先通过 OPM 2024 SDK 编译，再在 OPM 中实测以下流程：

1. 七类型钢切换、规格和插入基准联动。
2. 二维截面动态预览、连续放置与 Reset。
3. 开放路径过滤、扫掠预览、参数重建、确认和取消。
4. `PipeSupportComponents` ItemType 附加及源路径删除选项。

## 构件特性查询

从首页进入“构件特性查询”，点击“点取构件”后，将光标悬停在管道或其他构件上，左键单击即读取，可连续点取；右键 Reset 与点击“结束点取”都退出命令并在底部状态栏显示“已结束点取命令”。返回首页或关闭窗口也会退出点取。该功能只读取模型，不创建元素，也不写入 `PipeSupportComponents` ItemType。

结果页显示元素 ID、EC Schema / 类 / 实例 ID、常用 OpenPlant 管道属性、长度单位、外径反查 DN、保温后外径、中心线与管底标高、几何长度、起终点和走向。可在“自动判断 / 毫米 / 米”之间切换属性长度单位，并打开“显示全部 EC 属性”查看所选元素上各实例的属性。结果表的标签和数值均可选中复制；拖动“特性”列标题右侧边界可调整标签列宽，点击“复制查询结果”会将当前视图的全部行复制到剪贴板。曲线几何可用时使用开放曲线；Cell 等无开放曲线的元素使用包围盒近似，页面会标明来源。属性单位自动判断使用 EC `LENGTH` 与几何长度互校，无法标定时须核对原始值或手动指定。

实现分布在 `Domain/ComponentProperties/`、`Data/ComponentProperties/`、`Services/ComponentProperties/`、`Tools/ComponentProperties/` 和 `UI/ComponentProperties/`。EC 读取在定位回调结束后执行，结果是纯数据快照。无需另加 Key-in；现有 `STEELPROBE SHOW` 打开工作区后从首页进入。

纯计算检查：`dotnet run --project Development/ComponentPropertiesCheck/ComponentPropertiesCheck.csproj -c Release`。本功能已经通过 Release 编译。Bentley 点取、EC 实例读取和不同模型的单位行为仍需在 OPM 2024 中实测。
## 弯头耳轴

首页只有一个“弯头耳轴”入口。详情页依次选择“竖直弯头 / 水平弯头”和“竖直耳轴 / 水平耳轴”，对应四个原 Python 脚本：

| 组合 | 原脚本 | 编号 |
| --- | --- | --- |
| 竖直弯头 + 竖直耳轴 | `F2-[竖直弯头的竖直耳轴].py` | F2 |
| 水平弯头 + 竖直耳轴 | `F2-[水平弯头的竖直耳轴].py` | F2-HE |
| 竖直弯头 + 水平耳轴 | `F4-[竖直弯头的水平耳轴].py` | F4 |
| 水平弯头 + 水平耳轴 | `F5-[水平弯头的水平耳轴].py` | F5 |

在三维模型中选择弯头方向与耳轴方向，再设置底板或端板、材料、空心/实心及可用的 PTFE、底平、Outlet 伸出方向。编号中的主管和耳轴管径默认使用公制 DN（例如 `F2-DN100-DN50-...`）；“命名管径单位”可切换为英制 NPS，以保留原脚本的英寸编号。页面管径和清单规格始终显示 DN，长度仍以 mm 计。点击“点选弯头”，鼠标悬停定位 90° OpenPlant 弯头并左键选择；松开左键后沿耳轴方向移动鼠标，动态线框显示拉伸长度 H/L，再次左键固定长度。此时才生成耳轴、鞍口、通气孔与板件的可撤销 SmartSolid 预览。长度也可在参数框中调整；修改参数或点击“更新预览”会重建。“确认生成”保留组合 Cell 并写入 `PipeSupportComponents` 公共 ItemType；“取消预览”、返回首页及关闭窗口会清理本功能创建的预览。点选或拉伸阶段右键取消当前命令。所选弯头不会被修改。

90° HVAC 圆风管弯头也可点选：取实际外径选耳轴和底板档位，以 `RADIUS` 补足中心至端面长度；鞍口仍按实际外径建模。风管主管编号为 `D450` 这类外径文字，矩形风管弯头暂不支持。耳轴 ItemType 类型名固定为组合代号和构件角色，不附加哈希值。

纯计算检查：`dotnet run --project Development/ElbowTrunnionCheck/ElbowTrunnionCheck.csproj -c Release`。该检查覆盖四种轴线定位、视图投影取长、选型、编号和无效输入。Bentley 点取、实体布尔差集、预览删除与 ItemType 附加必须在 OPM 2024 中以实际 90° 弯头进行运行时验证。



## 支吊架统计

首页点击“支吊架统计”进入详情页，页面自动读取当前活动 DGN 文件的 `PipeSupportComponents` 公共 ItemType。直接显示支吊架总套数、整组与构件记录数、按类型套数及编号、逐组支吊架表和材料汇总表。三个明细表各有独立的底部横向滚动条，表格宽度跟随页面内容区，列内容可横向查看；蓝灰色 6 像素细滑块与页面主滚动条区分。底部可刷新，或导出 Excel（“汇总 / 支吊架表 / 材料汇总表”三张工作表）及 JSON 统一清单。另存为对话框默认建议 `活动DGN文件名_支吊架材料表_yyyyMMddHHmmss`，用户可直接改名。导出前会重新读取当前文件；本功能只读，不修改模型。清单本身采用**固定 ItemType 名 + 值写入元素上的 EC 实例**：同一功能（如型钢）无论放多少种规格，库里都只占固定的几个 ItemType，每条记录的规格、长度、数量差异写在元素自己的实例属性上。这样 MicroStation“项”面板里看到的是稳定的少量类型，而不是每个尺寸一个；历史文件中按旧规则生成的类型名仍可正常读取与汇总。

统计沿用原 `00-[支吊架统计].py` 与 `支吊架公共库.py` 的九个属性字段、Assembly / Component 分类及数量与总长汇总规则。C# 实现位于 `Domain/SupportStatistics/`、`Data/SupportStatistics/`、`Services/SupportStatistics/`、`UI/SupportStatistics/`。纯计算及导出格式检查：`dotnet run --project Development/SupportStatisticsCheck/SupportStatisticsCheck.csproj -c Release`。Bentley ItemType 跨模型读取与宿主内另存为对话框仍需在 OPM 2024 用真实 DGN 实测。

各建模功能写入 `PipeSupportComponents` 的属性与 `管道支吊架/模块/公共/支吊架公共库.py` 的契约完全一致：`SupportType` 存**中文类型名**（`E1-[不保温管导向架]`、`F2-[竖直弯头的竖直耳轴]`、`G2-[混凝土锚板（膨胀螺栓）]` 等），Assembly 记录的 `ComponentName` 固定为“支吊架”，构件记录的 `ComponentName` 才是构件名（构件A / 不锈钢薄板 / 锚板 / 膨胀锚栓 …）。ASCII 代号（`E1_RACK`、`F2_VERTICAL_ELBOW_TRUNNION`、`G2_ANCHOR_PLATE` …）**只用于 ItemType 命名**；中文类型名由各功能的目录数据给出（`E1GuideCatalog.SupportType`、`ElbowTrunnionCatalog.SupportType`、`G2AnchorCatalog.SupportType`）。这样 C# 与 Python 写入的记录才能按同一 `SupportType` 正确聚合套数，对应断言在 `Development/E1GuideCheck/`、`Development/ElbowTrunnionCheck/` 与 `Development/G2AnchorCheck/` 中。
## 罐壁人孔

首页进入“罐壁人孔”，选择 DN450 / DN500 / DN600、ASA 150 / 300 / 600 lbs、吊杆式或铰链式，并设置筒节长度、水平朝向、反向、螺栓及开盖机构。页面采用两列参数布局，尺寸以 mm 计，管径默认显示 DN。三种规格和吊杆直径表来自 `罐壁人孔/tank_wall_manhole.py`，C# 运行时不依赖 Python。

在三维 DGN 模型中点击“点取位置”，左键指定筒节在罐壁的中心，生成 `TANK_WALL_MANHOLE` 普通 Cell 预览。参数更改或“更新预览”会先建立新预览再删除旧预览；“确认生成”保留单元。右键、结束点取、取消预览、返回首页及关闭工作区都会清理未确认的预览。现阶段无需额外 Key-in，也不写入 `PipeSupportComponents`：该人孔属于罐体设备附件，原 Python 功能未提供支吊架清单字段。

实现分布于 `Domain/TankManhole/`、`Data/TankManhole/`、`Services/TankManhole/`、`Tools/TankManhole/` 和 `UI/TankManhole/`。筒节、法兰、带孔盲盖、紧固件、把手、铰链销、吊杆和盖板连接件均由 C# SmartSolid 构造。几何与 `罐壁人孔/tank_wall_manhole.py` 逐项对齐：吊杆回转支撑件的径向轮廓（双水平臂 16 厚、腹板 16 厚、背部外 R20 / 内 R10、开口端 30° 收窄到法兰厚度）其**外表面**在立柱轴线外 `D/2 + 20 + 16`；那 16 是原脚本 `BodyFromSweep` 把轮廓厚度加在扫掠路径终点之外产生的（脚本自己的 `_davit_support_placement` 长度公式只算到路径终点），本版按脚本的实际出形取值。轮廓与尺寸由 `TankManholeCalculator.DavitSupportAnchorY / DavitSupportOuterFaceY / DavitSupportChamferDistance / DavitSupportProfile` 纯计算给出（`DavitSupportProfile` 返回 8 段直线 + 4 段**真圆弧**，`DavitSupportOutline` 只是把圆弧展开成点列供校验用）。R20/R10 必须用真圆弧原语（`CurvePrimitive.CreateArc`）扫成真圆柱圆角面——用 8 段折线近似时圆角面上会出现成排的分面棱，每段法向相差 11.25°，在 OPM 里表现为一叠显眼的横线（Python 版用 `BlendEdges` 真圆角，所以没有这些线）。吊杆的圆到扁头过渡与原脚本同序：先试 `Create.BodyFromLoft(..., periodic:false, segment:true)`（段间线性、不做平滑，等价于原脚本的 `DgnRuledSweep`），失败才退回 24 段台阶近似（回退时轮廓反序，法向朝圆管一侧）。M20 调节吊环螺栓的圆环中心线半径 25（孔 Ø30、外径 Ø70）。**铰链销轴上下两端各有一只开口销**（销轴 Ø16、两端各伸出吊耳 20，半长 73.5；销轴两端各掏一个 Ø4.5 开口销孔，插 Ø4×28 开口销，两只镜像对称），位置由 `TankManholeCalculator.HingePinHalfLength / HingeCotterStations` 纯计算给出；吊杆立柱只在**下端**装一只开口销，因为立柱顶端与吊杆竖直段对接、没有自由端可锁。纯计算检查：`dotnet run --project Development/TankManholeCheck/TankManholeCheck.csproj -c Release`。已通过 Release 编译；Bentley 布尔差集、直纹放样、Cell 写入及预览删除尚未在 OPM 2024 中实测。
## 实体管口

首页进入“实体管口”，选择 CL150 法兰等级、钢管系列（`Ia_Sch10` 或 `Ia_large_dia_welded_wall12.5`）和 DN 规格。DN 下拉框只显示法兰与钢管均有数据且外径一致的组合。可填写壁厚覆盖值；留空使用管表壁厚。管口总长度包含法兰厚度 C，钢管名义长度为“总长度 − C”。放置方向支持 ±X、±Y、±Z，螺栓孔默认不绘制。

在三维 DGN 中点击“开始点取”，左键指定基点后生成一个 SmartSolid 预览；调整参数或继续左键点取会先建立新预览，再清理旧预览。“确认生成”保留当前实体，并可继续点取下一处（此时点取仍在进行中，直接点下一处即可，无需再点“开始点取”）；右键、结束点取、返回首页或关闭工具会取消未确认预览。`NozzlePlacementTool.Begin()` 是幂等的：已经在点取中时只重新提示一次，不做“结束再安装”——后者会先假发一次 `Ended` 清掉页面状态，新实例还可能被上一个实例的延迟 `OnCleanup` 带掉，表现为“再点一次开始点取后第一次点击被当成结束，要点两次才进得去”。尺寸来自原 `实体管口/flange_data.json`，作为 `Resources/nozzle_flange_data.json` 嵌入 DLL，运行时无需 Python 或外部 JSON。当前 CL150 表未提供密封面凸台尺寸，因此不生成凸台；若表内补充 `raised_face_od` 和 `raised_face_height`，建模服务可按数据生成。该功能是可视化设备管口，沿用原脚本约定，不写入支吊架材料表或 OPM 管道 EC 组件。

代码位于 `Domain/Nozzle/`、`Data/Nozzle/`、`Services/Nozzle/`、`Tools/Nozzle/` 和 `UI/Nozzle/`。实体管口和罐壁人孔共用 `Services/SolidPrimitiveFactory.cs` 的基础 SmartSolid 操作。纯计算和尺寸表校验：`dotnet run --project Development/NozzleCheck/NozzleCheck.csproj -c Release`。需在 OPM 2024 中实测六种轴向、大小口径的相并与孔切除、连续点取及预览清理。

## 放置管夹（A1 / A2 / A22 / A24 / E1 / K1 / T4 / L2）

首页只有一个“放置管夹”入口；进入后由页面最上方的下拉框切换八种管夹，参数区随类型切换。01 管夹类型与 03 点取预览固定显示，只有 02 参数区滚动。A1 先点取管道或辅助线确定位置，再移动光标在管道径向平面内调整开口方向，左键锁定并生成预览；其余类型左键点取后直接生成预览。改参数可更新预览；点【确定生成】才写入 `PipeSupportComponents`。右键、结束点取、取消预览、返回首页与关闭工作区都会清理未确认预览。类型与各类型参数跨会话记住（`%LOCALAPPDATA%\SteelSectionProbe\pipe_clamp_last.json`）。

| 类型 | 适用范围 | 编号 |
| --- | --- | --- |
| A1 U 型管卡 | DN15~900（表 1，27 档） | `A1-DN管径-M螺栓-角度°` |
| A2 标准型 2 螺栓管夹 | DN15~750（表 1，24 档） | `DN管径` |
| A22 保冷管用 2 螺栓管夹 | DN15~900（表 2；A 按表 1 的 13 档选型） | `A22-DN管径-保冷厚度` |
| A24 保冷管用 4 螺栓管夹 | DN15~900（表 2；F 按表 1 的 13 档选型） | `A24-DN管径-保冷厚度` |
| E1 不保温管导向架 | DN15~900（表 1 子项 A~E） | `E1-子项-H`（不锈钢加 `-S`） |
| K1 不保温管限位架 | 1/2″~36″（子项 A~C） | `K1-子项[-管径]` |
| T4 高温隔热限位管托 | DN15~600（表 1 / 表 2；DN50 及以下为详图 B 底座） | `名称-管径-温度代码-H-L-材料代码-F` |
| L2 最小长度保冷管托 | DN15~600（表 1 / 表 2；DN50 及以下用简式底座） | `L2-DN管径-保冷厚度[-F代码]` |

### A1 U 型管卡

弯弧圆心落在管轴上，半径 C/2；两条直腿长度 D，弯弧为真半圆。四颗带中心孔六角螺母按 Python 版尺寸布置，通板没有实体也不计入清单。管道按 EC 公称直径匹配表 1；辅助线使用面板 DN 和点击点作为管中心。第二次左键锁定开口角度后生成可撤销预览；确认时写入固定 ItemType `PipeSupportAssembly_A1`、`PipeSupportComponent_A1_U_BOLT`、`PipeSupportComponent_A1_NUT`，角度、尺寸只写入记录字段。

### A2 标准型 2 螺栓管夹

圆柱 ∪ 长方体后剪出管夹状，再开两个耳板螺栓孔并配 2 套简化紧固件（螺杆 + 六角头 + 带中心孔的六角螺母，不做布尔融合）。管夹内孔 A′ = A + 2×保温厚度，且孔心距 B 同步外移同样的保温厚度（否则孔会落进放大后的孔洞区域被剪掉、螺栓错位）。选中管道时按**公称直径**匹配表 1 并读其保温厚度；选中直线或匹配不上时改用面板管径与保温厚度。绕轴角度自动对齐（本地 Z 竖直向上），无需手工指定旋转角。

### A22 保冷管用 2 螺栓管夹

按 DN 查表 2 得承重板厚度（DN15~100 为 6、125~150 为 8、200~400 为 10、450~900 为 12 mm）；`A = 管道外径 + 2×(承重板厚度 + 保冷厚度) + 10`，再按 A 查表 1 得 C、E、T、W、螺栓与允许荷载。`B = A/2 + E`，孔径 `G = 螺栓直径 + 3`；E 对应 A2 的 D。几何是上下两片对合的圆弧承重板，各带左右法兰耳板，开两处贯穿孔，配两套螺杆、六角头、螺母和四只垫圈。承重环与法兰的过渡圆角按 `T≤15 时 R_MIN=T；T>15 时 R_MIN=2.5T`，使用与承重环外圆和法兰平面相切的圆弧剖面拉伸建模；大圆角靠近螺栓时整平垫圈座面。管道优先读取 EC 公称直径、外径与保冷厚度；缺失时使用面板 DN、表外径和面板厚度。按 `A22-DN管径-保冷厚度` 编号；超出 A=1400 mm 的表 1 上限时拒绝建模。

### A24 保冷管用 4 螺栓管夹

沿用 A22 的表 2、A/B/G 计算和相切过渡圆角；按 A24 表 1 查 F：A≤400 为 100、401~450 为 120、451~700 为 145、701~900 为 170、901~1050 为 195、1051~1400 为 225 mm。内侧两孔仍在 ±B，外侧两孔在 ±(B+F)；法兰每侧延长 F，总长比 A22 多 2F。每组有四套螺杆、螺母与八只垫圈，清单独立记为 A24。A24 表 1 未提供允许荷载，规格中不沿用 A22 的荷载数据。

### L2 最小长度保冷管托

按 L2 表 1 选最小长度 L、轴向螺栓组距 F、端距 E、T1/T2/T3、螺栓及荷载；DN15~150 为 L=150、F=80、E=35 mm，DN200~600 为 L=300、F=150、E=75 mm。表 2 按保冷厚度查 H：≤25→100、26~75→150、76~125→200、126~175→250、176~225→300、226~275→350 mm。四套螺栓。编号为 `L2-DN管径-保冷厚度[-F代码]`，其中末段 F 是图注 5 的编号字段，与表 1 中的孔组距 F 区分。

实体直接复用 T4 的圆筒承重板、45° 对开、耳板开孔、紧固件和底座布尔建模；小管径只用底板与中央纵向腹板，DN80 及以上增加横向支撑。L2 图中梯宽 C 指向 LGEN2 注 8，所附资料未给出该尺寸；当前沿用 T4 按保冷层外径查底板宽度的规则，耳板尺寸与对开间隙也沿用同 DN 的 T4 参数。L2 表 1 给出的上、下弧形块密度与允许轴向位移写入规格说明，未改变几何。允许荷载使用 L2 自己的表值。

### K1 不保温管限位架

点选一根水平管道或普通直线（与水平面夹角超过 5° 会被拒绝）。两组限位块沿管轴一前一后，内侧间距 = 面板输入的已有钢构宽度 W。子项 A 是 H100×100×6×8 沿腹板高度中点剖开取半片的 T 形（翼缘 100×8 + 腹板 6×42），竖直放置、管道焊在其顶端截面、无底板；子项 B/C 是完整 H 型钢、水平且长度沿管轴，管道骑在两翼缘端面上，底板焊在朝已有钢构那一端的**截面**上。子项按 DN 自动选、可改。管道骑座高差 contact = √((OD/2)² − (b/2)²)，钢板顶面与翼缘端面的间距 = 2×(OD − √(OD² − (b/2)²))，其中 b = 型钢高度 − 2×翼缘厚。

### T4 高温隔热限位管托

点选一条管道轴线。上下两片承重板包在保温层外（对开 45°、两端留间隙 J），用耳板与螺栓连接。DN15/20/25/40/50 按详图 B 建模：矩形底板 + 中央纵向腹板，无横向弧顶支撑，耳板固定两组、尺寸 40×40×12。DN80~600 保留底板 + 横向弧顶支撑（L > 600 时加中间肋板）+ 中央纵向腹板，弧顶减圆柱成形。H 由隔热层厚度 B 查表得到（面板只读显示）；底板宽度按保温层外径 D = OD + 2B 查表 2。DN80、DN100 的 M12、T1/T2/T3 与三向荷载已核对图示表 1；小管径图中未给出的 C、k、J 等尺寸暂沿用 DN80 数据。可选创建管道本体与保温层，默认都不建。

八种管夹的分层位置：表数据与元素读取在 `Data/PipeClamp/`；纯参数与结果在 `Domain/PipeClamp/`；尺寸推导与 Bentley 建模在 `Services/PipeClamp/`；点取与预览所有权在 `Tools/PipeClamp/`；页面在 `UI/PipeClamp/`。A1 使用专门的 `A1ClampOrientationTool` 完成第二阶段旋转。E1 的数据、计算与建模仍在 `Data/E1Guide/`、`Domain/E1Guide/`、`Services/E1Guide/`，只把面板并入了本页面。管夹共用 `PipeClampLocateTool` 与 `PipeClampPreviewSession`。

### E1 不保温管导向架

在上面的“放置管夹”页面把类型切到 E1 后，选择 DN15～DN900、A～E 子项（默认按 DN 自动选型）、构件A材料和是否为不锈钢管道。点取 OpenPlant 直管时读取其 EC 管径；点取普通直线或多段线时使用页面所选 DN。多段线按三维点取位置选最近的有效直线段，只使用该段的方向和标高；允许轴线坡度至 30°，在该段上投影得到放置中心。管轴取值顺序：中心线曲线 → 元素范围（包围盒）最长边；**包围盒兜底不限定水平，竖直管道同样适用**（与 Python 的 `axis_from_bbox` 一致），近似定位时页面会给出提示而不报错。各类型自己的走向限制由各自的 Calculator 负责（K1 ≤ 5°、E1 ≤ 30°）。悬停定位后左键一次生成两根镜像竖直构件的可撤销 `E1_RACK` Cell 预览；不锈钢选项另生成两块 06Cr18Ni9 薄板。构件底面位于管底标高，内侧面距管壁 3 mm。高度 H 在外径小于 88.9 mm 时为 50 mm，其余为外径半径加 50 mm 后四舍五入。编号为 `E1-子项-H`，不锈钢增加 `-S`，界面管径统一显示 DN。确认后写入 `PipeSupportComponents` 公共 ItemType：1 条 Assembly、2 件构件A和可选的 2 件薄板。支吊架统计页可以预览与导出材料表。源管道始终保留，不受删除选项影响。只有点取单根普通直线时，“确认后删除辅助线”才可勾选；默认不勾选，勾选后仅在确认时删除该辅助线。管道和多段线始终保留，不会删除整个多段线。

右键、结束点取、取消预览、返回首页和关闭窗口都会清理未确认预览。修改参数或重新点取会先写入替代预览再删除旧预览。A 为 50×10 板件；B、C、D、E 的型钢轮廓分别从本工程 `Resources/profiles.bin` 加载等边角钢 L50x50x6、平行腿槽钢 10、热轧 H 型钢 H100x100x6x8xr8 和 H150x150x7x10xr8，圆角保留真圆弧。E1 的 DN/外径与子项表在 `Data/E1Guide/E1GuideCatalog.cs`；修改这些值后重新编译。如需修改型钢规格，则修改 `Development/profile_catalog/` 并运行 `python -B Development/export_profiles.py`，然后重新编译；C# 运行时不读取或调用 Python 插件。

纯计算检查：`dotnet run --project Development/PipeClampCheck/PipeClampCheck.csproj -c Release`（覆盖 A2、A22、A24 与 L2 的表数据及尺寸推导、K1 子项/骑座高差/底板盒/坐标架、T4 表 1 表 2 与保温高度表/布尔布局/孔位校核，以及八种管夹的清单属性契约），另有 `dotnet run --project Development/E1GuideCheck/E1GuideCheck.csproj -c Release` 覆盖 E1 的纯计算。Bentley 环境中的 EC 管径与保温厚度读取、多段线段点取、型钢扫掠、布尔运算、普通 Cell 预览删除以及 ItemType 汇总还需在 OPM 2024 用真实 DGN 实测。

## G2 混凝土锚板（膨胀螺栓）

首页点击“混凝土锚板”。详情页选择表 1 子项 A~D、安装面（竖直墙面 / 水平楼板顶面 / 水平楼板底面）与朝向；间距 S 默认取该子项的 MIN.S，切换子项时自动重置，并校验不得小于 MIN.S。页面同时显示锚板与锚栓规格、有效埋深、混凝土边缘要求 MIN.C / MIN.h 以及允许拉力与剪力。

在三维 DGN 中点击“开始点取”，左键点取混凝土表面上锚板背面的中心点，生成 `CONCRETE_ANCHOR_PLATE` 普通 Cell 预览；修改参数会先建立新预览再删除旧预览。“确定生成”保留单元并写入 `PipeSupportComponents` 公共 ItemType：1 条 Assembly、1 块锚板与 4 套膨胀锚栓。右键、结束点取、取消预览、返回首页和关闭工作区都会清理未确认预览。子项 / 间距 / 朝向 / 安装面会跨会话记住（存 `%LOCALAPPDATA%\SteelSectionProbe\g2_anchor_last.json`）。

几何与 `管道支吊架/G2-[混凝土锚板（膨胀螺栓）].py` 及 `模块/公共/混凝土锚板.py` 逐项对齐：局部原点为板背面中心（贴混凝土面），局部 +X 恒为混凝土外法向；锚板为正方形，边长 = S + 100（边距 50）、厚 T，四个 φG 螺栓孔位于 x=0 平面、间距 S×S 并居中。锚栓总长 L 保持不变，螺杆外端超出螺母外端面 5 mm（露出的丝头），因此有效埋深 = L − (板厚 T + 垫圈厚 + 螺母高 + 5)，表 1 四个子项均满足各自的 h_ef。每根锚栓由埋入端膨胀套管、螺杆、垫圈与六角螺母四段最简单的拉伸 / 圆柱构成，**不做布尔融合**（允许实体重合），与脚本一致。埋入端膨胀套管外径取 `1.7 × d`、长度取有效埋深的 0.55。安装面决定局部 +X：竖直墙面在水平面内绕 Z 旋转；楼板顶面 +X = 世界 +Z（锚板水平、螺栓朝下插入楼板）；楼板底面 +X = 世界 −Z（螺栓朝上）。朝向角在各自平面内绕外法向旋转锚板。

实现分布于 `Domain/G2Anchor/`、`Data/G2Anchor/`、`Services/G2Anchor/`、`Tools/G2Anchor/` 和 `UI/G2Anchor/`。局部坐标轴定义集中在 `G2AnchorCalculator.Axes`（纯计算），`G2AnchorFrame` 与纯计算检查工程共用同一份，避免两份朝向定义。纯计算检查：`dotnet run --project Development/G2AnchorCheck/G2AnchorCheck.csproj -c Release`，覆盖表 1 四子项尺寸与埋深自检、间距 S 与非法输入拒绝、三种安装面在多个朝向角下的三轴正交与右手系。Bentley 点取、普通 Cell 写入、预览删除与 ItemType 附加仍需在 OPM 2024 中实测。


## 点选参考文件里的元素

MicroStation 的参考文件（reference attachment）里的元素，其 ElementId 属于**参考文件自己那个文件的 ID 空间**，按 ID 在活动文件里查不到 —— 这正是早期版本点选参考元素会报"所选元素已不存在"的原因。

现在所有"点选元素"的功能都支持参考文件：定位回调把元素与**它所属的模型引用**一起上报（`Data/LocatedElement.cs`），读取器用那个模型去查元素、读几何与 EC。几何读取分两条路径：元素属于活动模型时仍走原 COM 路径（行为不变）；元素来自参考文件时改用 .NET 曲线查询（`CurvePathQuery.ElementToCurveVector` + `CurveVector.GetRange / GetStartEnd`），因为 COM 的 `ActiveModelReference` 只认活动模型。

还有一道与 ID 无关的关卡：MicroStation **默认不把参考元素交给元素集合工具**，所以即使读得到几何，点上去仍会报"元素位于只读参考文件之中"。这是工具层的策略，不是元素读取的问题，也**不取决于参考附件的类型或设置**（参考文件本身在 MicroStation 里永远不可编辑，没有"改成可写"这种选项）。修法是覆写 `DgnElementSetTool.GetReferenceLocateOptions()` 返回 `RefLocateOption.TreatAsElement`（把参考元素当普通元素来定位），并在 `OnPostLocate` 里加一层兜底放行。三个点选工具（放置管夹 / 构件特性查询 / 弯头耳轴）都已覆写。

适用功能：放置管夹（A1 / A2 / A22 / E1 / K1 / T4）、G2 混凝土锚板、弯头耳轴、构件特性查询。点取到参考元素时，界面会在元素信息与尺寸来源说明里标注"（参考文件）"。

**放置管夹有一条专门的"临时辅助线"流程**（`Services/PipeClamp/TempAxisLine.cs`）：点选参考文件里的管道时，插件先读出它的管轴与管道属性，再**在活动文件里按这段轴线生成一条普通直线**，然后用**已验证的按线路径**重新读一遍（并把参考元素读到的公称直径 / 保温 / 管道号并到这条线上），最后在确认或取消时**自动删除**这条临时线。这样"生成"这一段完全不接触参考文件 —— 不会碰到"参考元素写不进 / 删不掉 / 几何读不稳"这类问题，参考元素的影响面只剩一次轴线读取。临时线在切换到活动文件里的元素、重新点选、结束点取、切换管夹类型、离开页面时都会清理；异常退出（宿主崩溃）时最多残留一条普通直线，手动删除或撤消一步即可。界面会在预览行写明"已按参考管轴在活动文件中生成临时辅助线，确认或取消后自动删除"。

两个前提：该参考附件的 **Locate** 开关必须打开（否则连点都点不到），要用捕捉画辅助线时 **Snap** 也要打开。另外"确认后删除辅助线"只对**活动文件**里的直线生效 —— 参考文件里的直线不会提供该选项，也不会被执行删除。

单位换算要留意的差别：COM 的坐标是 master 单位（`× UorPerMaster / uorPerMm`），.NET 几何坐标是 UOR（`/ uorPerMm`），两者不能混用。
# 门型架（D8 / D13 / G5 / G6 / D16）

首页“门型架”统一进入五种架型。D8 / D13 支持正门与倒门；G5 / G6 带地面锚板、锚栓、螺母及灌浆基础。点取竖直辅助线后先生成可取消预览，确认时按固定角色 ItemType 名一次写入清单；编号、规格及尺寸放在实例属性中，不参与 ItemType 命名。

纯计算检查：`dotnet run --project Development/PortalFrameCheck/PortalFrameCheck.csproj -c Release`。

## T 型架（D12 / G4 / D15）

首页“T 型架”统一进入三种架型。D12/G4 点取竖直辅助线；D15 点取水平辅助线。页面选择子项与类型，生成可取消预览。型钢来自内嵌 `profiles.bin`；G4 复用门型架地脚几何。确认时一次写入 `PipeSupportComponents` 清单。Assembly 与 Post / Arm / MemberA / MemberB / AnchorPlate / AnchorBolt / AnchorNut / Grout 的 ItemType 名按组合代号和角色固定，不附加哈希或尺寸。纯计算检查：`dotnet run --project Development/TFrameCheck/TFrameCheck.csproj -c Release`。

参数卡片显示当前子项、类型的标准上限：D12/G4 为 H 与 L，D15 为 L1、L2 及辅助线长（L1 上限 + 构件 B 腹板厚）。输入 L2/L 后立即显示当前值；点取辅助线后显示实际 L1/H。超限时标红，预览错误同时给出当前值与上限。校验保留 1 mm 测量容差。

## 垫板（Y2 弧形垫板 / 弯头垫板）

首页“垫板”统一进入两种型式，页面顶部切换。Y2 点取水平管道、HVAC 圆形直风管或直线，垫板在点击投影处沿管轴居中、贴于管底；普通管道按 DN 查管外径和 6/8/10 mm 板厚。HVAC 圆形直风管直接取 EC 的 `OUTSIDE_DIAMETER` / `MAIN_DIAMETER` / `RUN_DIAMETER` 实际外径，外径不超过 2000 mm 用 6 mm 板，超过用 10 mm 板，编号如 `Y2-D450-300-C1-120`。弯头垫板点取 90° 管道或 HVAC 圆风管弯头，沿弯头背弧扫掠 75°（可调），截面默认包角 120°；风管弯头取实际外径与 `RADIUS`。两者采用真圆弧截面、可选 Ø6 通气孔。确认时一次写入公共清单；ItemType 名按 `Y2_ARC_PAD` / `ELBOW_PAD` 与 `PAD` 角色固定，编号和规格为实例值。纯计算检查：`dotnet run --project Development/PadPlateCheck/PadPlateCheck.csproj -c Release`。扫掠与 EC 点取仍需在 OPM 2024 中用实际模型验证。


### L8 保冷立管导向架

保冷立管导向架页先选 L7/L8，再选类型，之后点取立管或竖直辅助线、定方向并放置。L7 类型 1/2 保持现有结构；L8 类型 1 复用 L7 类型 1 的 A22、承重夹板及构件 A 几何，仅采用 L8 编号。L8 类型 2 使用相同的 A22/承重夹板，在构件末端附加已有 N8 连接板、螺栓、螺母和垫圈；已有设备预焊件由设备模型提供。

按提供的 L8 表 1，类型 2 的构件 A 按管夹内径 A 分段：≤100 mm 为 ∠75×7，100～450 mm 为 [12.6，450～700 mm 为 [14a；前两段采用 N8 类型 1，第三段采用 N8 类型 2。L8 类型 1 按用户要求保留 L7 类型 1 的型钢选型。N8 板面垂直构件轴线，板厚从构件实长中扣除，使构件端面贴合连接板。

L8 编号：`L8-类型-DN管径-保冷厚度-L-材料代码-L1`。L 为沿管轴夹板长度（至少 300 mm），L1 为管心至端部距离（300～1000 mm）；材料代码 L/C1/S 的管材温区及防滑挡环材料按提供的表 3 展示。允许荷载按 DN15～150 表 2 存储；L=300/450/600 mm 时允许轴向位移为 30/100/180 mm，其他长度不外推位移。材料代码与荷载写入组合规格；不根据材料代码自动改变模型材质。

计算、管夹、承重夹板、方向/长度工具与预览会话继续共用 `ColdRiserGuide` 原有实现；N8 使用 `N8Catalog` / `N8Builder`，型钢使用 `profiles.bin` / `SteelMemberFactory`。确认时一次写入固定 `L8_TYPE1` / `L8_TYPE2` Assembly 和构件角色 ItemType，取消或切换系列/类型删除未确认预览。纯计算验证：`dotnet run --project Development/PipeClampCheck/PipeClampCheck.csproj -c Release`。最终实体、设备连接处及交互需在 OPM 内检查。


## 普通钢结构围栏（C#）

首页“建模类”→“普通钢结构围栏”。迁移来源为仓库 `普通钢结构围栏/steel_handrail.py`，C# 运行时不启动 Python。选择立柱连接形式、踢脚板左右侧、是否反转路径及端部闭合方式后，点取活动模型中的开放直线、折线或纯直线复杂链。参数变更延迟 150 ms 自动更新预览；可更新、确认或取消，辅助线始终保留。右键、结束操作、返回首页和关闭窗口清理未确认预览；重建失败保留上一版有效预览，并禁用确认，待参数修正后重新生成。

- 类型 1：圆管向 70×16.1 mm 椭圆压扁端直纹放样，过渡长度 38.5 mm；146×75×10 mm 侧板。继承原版暂定尺寸及半轴减壁厚内腔近似，不代表压扁加工后的精确等壁厚。
- 类型 2：R76 下弯与侧板，中心至连接板距离默认 **120 mm**（以原脚本常量为准），须大于 83 mm。
- 类型 3：145×75×10 mm 水平底板，坡段底板仍水平；立柱由板顶开始。
- 类型 4：保留原版预留模式，只生成围栏本体，无底部安装节点。

固定尺寸：立柱 φ48.3×3.2，顶部扶手 φ42.4×3.2 / 中心高 1017 mm，中间横杆 φ33.7×3.2 / 中心高 560 mm，连接球 φ76；踢脚板 130×6 mm、净高 10 mm、与立柱外壁净距 10 mm。围栏相对辅助线向所选侧的反方向偏移 34.2 mm，沿用原版定位。柱距 ≤2000 mm，优先 50 mm 工程模数，余量首尾优先；水平转角采用真圆弧 R140，纯变坡点强制设置立柱。端部回弯四选一，不闭合 / 始端 / 末端 / 两端，每端由 160 mm 直段、R140 弯头、177 mm 竖段、另一弯头回接横杆。颜色精确为 RGB(255,204,0)。

同一折点同时转向和带坡度、竖直段、闭合、自交、180° 折返及不足以容纳圆角的短路径明确拒绝；暂不提供参考模型辅助线放置，也不生成螺栓、钢梁和焊缝实体。踢脚板沿完整偏移路径一次连续扫掠，并锁定竖直方向。

确认后使用公共 `PipeSupportComponents` 库，固定 `PipeSupportAssembly_STEEL_HANDRAIL` 和各角色 `PipeSupportComponent_STEEL_HANDRAIL_*`，尺寸不进入类型名。顶部/中间横杆按每道围栏总中心线长记一项；踢脚板按**实际偏移路径长度**记载（修正原 Python 按未偏移栏杆长度记载的近似）；球数为柱数×2，类型 1 压扁端和类型 2 下弯段沿用原版水平代表下料长，坡段为近似。“导出 JSON 清单”扫描当前 DGN 文件各模型中已确认的 **C# 围栏**，按规格汇总。原 Python 写入的 `SteelHandrailComponents` 库暂不自动迁移或合并；现有“支吊架统计”页也可读取新围栏并导出 Excel/JSON。

分层代码：`Domain/SteelHandrail`、`Data/SteelHandrail`、`Services/SteelHandrail`、`Tools/SteelHandrail`、`UI/SteelHandrail`。板件、钢管及扫掠复用 `SolidPrimitiveFactory`，连接球使用解析球实体。验证：`dotnet run --project Development/SteelHandrailCheck/SteelHandrailCheck.csproj -c Release`，28 组原 Python 基准 × 4 种节点形式，以及排柱边界、闭合清单、非法路径检查；Python 仅在开发期生成 `reference.json`。Bentley 放样/布尔/扫掠及点取取消流程仍需在 OPM 内实测。


### 弯头耳轴主管规格补齐

四种弯头耳轴组合共用管径目录识别主管，支持 DN15、20、25、32、40、50、65、80、100、125、150、200、250、300、350、400、450、500、550、600、650、700、750、800、850、900、950、1000、1050、1100、1200。补齐原独立白名单遗漏的 DN65、DN80、DN125；其余任意数值不自动视为标准 DN。DN65/DN80 按现有表选 DN50 耳轴（外径 60.3 mm，默认壁厚 3.91 mm）；DN125 选 DN80 耳轴（外径 88.9 mm，默认壁厚 5.49 mm）。竖直耳轴 A 型方形底板均为 200×200×10 mm。风管的直接档位和就近外径匹配同步使用完整目录。验证覆盖新增三种主管的四种方向组合、公制/英制编号和完整目录选型。

## D16 水平门形 / 井形架

在现有门型架页面选择 D16，再选类型 1 或 2、子项 A～E、接点焊接型式 A～D。点选水平直线，起点为生根端，方向由直线决定，线长为 L1。L2 为两构件 A 内侧净距；构件 A 与 B 的截面几何中心处于同一水平面。类型 1 禁用 L3/L4，外侧 B 位于 L1，A 再延伸 50 mm；类型 2 外侧 B 位于 L1+L3，内侧 B 位于 L1−L4，A 在外侧 B 后延伸 50 mm。L4=0 不生成内侧 B，L4=L3 时编号省略 L4。焊接型式现阶段仅选择、保存及写入编号，不生成焊缝或筋板。

子项 A/B 使用 ∠75×7 / ∠100×10，L2 最大 1000 mm；C 使用 [14a；D 为 H150×150×7×10 与 [10；E 为 H200×200×8×12 与 [14a，C～E 的 L2 最大 1200 mm。L1 最大 1000 mm，按附图四档读取允许荷载，空栏不推算。所有输入单位为 mm，模型转换使用活动模型 UorPerMeter。构件扫掠和清单复用公共服务；确认前可更新或取消预览。

D16 截面方向：两侧 A 镜像，角钢水平肢在上、竖直肢在内侧且背靠背；槽钢腹板背靠背、开口向外。角钢 B 水平肢在上、竖肢朝框架外侧（内侧 B 朝根部）。H 型钢 A 的 B 实长为 L2 + A 翼缘宽 − A 腹板厚，两端延伸至腹板内侧面，清单使用实际长度。

D16 尺寸定位修正：类型 1 的 L1 到 B 竖肢/腹板外侧平面，B 中心站位 L1−B宽/2，A 总长 L1+50。类型 2 两根 B 背靠背，外侧中心为 L1+L3+B宽/2，内侧中心为 L1−L4−B宽/2，A 总长 L1+L3+B宽+50；两类 A 均比 B 最外边缘伸出 50 mm。B 宽度读取截面目录 B 参数。此处替代此前以 B 中心定位的说明。

## D20 门型架

D20 合并于 portal-frame。子项 A～D 的 H 型钢立杆、双槽钢横担及腹板间净距 S 复用 G6 规格与背靠背几何，不生成地脚。竖直辅助线 H 为立杆底面到横担顶面，立杆实长 H+50。按附图 L 为两立杆中心间距，横担实长 L−立杆截面高度。H 上限分别 1000/2000/3000/3000 mm；允许垂直荷载按 L≤500/1000/1500/2000 表查，空栏不推算。编号 D20-子项-H-L；ItemType 固定 D20_PORTAL_FRAME 及 Post/Arm 角色，实例尺寸不进入类型名。PortalFrameCheck 覆盖尺寸、编号、荷载表和上限。

D16 可勾选起始端附加 G2 混凝土锚板，每根 A 一套，共两块板、八根膨胀锚栓。子项 A～D 与外移量沿用 D5 端焊三角架；孔距取 G2 最小孔距与大于 A 截面最大尺寸的下一档 25 mm 模数中的较大值。A 起点为外移量+板厚，实长扣除该值，B 定位与 A 外端保持不变。锚板方向随辅助线方位转动；预览统一管理，确认时固定 G2Plate/G2Bolt 角色写入清单。参数随页面持久化；拒绝锚板重叠及过大外移。
