# 型钢构件及支吊架模型生成工具：OpenPlant Modeler 2024 C# 版

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

独立的 .NET Framework 4.8 / x64 AddIn。运行时只加载 C# DLL，不启动 Python。当前提供型钢截面放置、沿路径扫掠、构件特性查询、弯头耳轴、立管耳轴（F6/F7/F10）、罐壁人孔、实体管口、放置管夹（A2 标准型 2 螺栓管夹 / E1 不保温管导向架 / K1 不保温管限位架 / T4 高温隔热限位管托）、G2 混凝土锚板与只读的支吊架统计，并按“工作区 + 功能页”组织，后续可继续接入各种支吊架功能。

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

首页卡片由 `Data/Home/HomeFeatureCatalog.cs` 的清单渲染（不再手写 XAML），顺序由 `Services/Home/HomeFeatureRanker.cs` 计算。首页顶部自带标题栏（应用图标 + 标题 + 副标题 + **搜索框** + **排序下拉** + **重置排序**），下方依次是「最近使用」与四个分区（建模类 / 支撑架类 / 统计与扩展 / 规划中）：

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

- **评分**：点卡片右下角的星标按钮，在弹出的菜单里选 1～5 星或「清除评分」。**评分后不立即重排**，回到首页才按新顺序排列（否则刚点完的卡片会从手下滑走）。同一功能若同时出现在「最近使用」与所属分区，两处显示同步更新。
- **卡片尺寸固定**：卡片固定 320 × 124（规划中占位卡 320 × 84），标题 1 行、说明 2 行，超长文字用省略号裁剪；列表用自动换行布局，放不下就换行。因此功能说明写多长、窗口拉多宽，卡片尺寸都不变，也不会横向溢出。首页窗口宽度**按实际内容自动校准**（两列卡片 + 页边距 + 滚动条，实测得出），所以右侧不会留出多余空白；功能页宽 560（均按当前屏幕 DPI 换算成设备像素），进入/返回模块时版式不会跳。
- **使用频率**：进入功能页时自动统计；同一次会话内同一功能只记一次，命令行入口 `STEELPROBE PLACE` 同样计数。
- **重置**：标题栏右侧「重置排序」清空全部星标与使用统计。
- **存储**：`%LOCALAPPDATA%\SteelSectionProbe\home_preferences.json`，只存 `PageId → {Stars, TotalUseCount, LastUsedUtc, MonthlyUse}`，**不存顺序**；文件损坏或不可写时静默回落到出厂顺序，不影响首页显示。
- **契约**：清单里的 `PageId` 必须与功能页 `IWorkspacePage.PageId` 逐字一致（不一致时状态栏报“未注册的功能模块”）；`Category` 必须是 `HomeCategories` 里的已知键，`Icon` 必须能在 `HomePage.xaml` 找到对应几何。新增功能页只需在 `HomeFeatureCatalog` 加一项（含分区与图标键），首页无需改动。
- 纯计算检查：`dotnet run --project Development/HomeCheck/HomeCheck.csproj -c Release`。

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

代码位于 `Domain/Nozzle/`、`Data/Nozzle/`、`Services/Nozzle/`、`Tools/Nozzle/` 和 `UI/Nozzle/`。实体管口和罐壁人孔共用 `Services/SolidPrimitiveFactory.cs` 的基础 SmartSolid 操作。纯计算和尺寸表校验：`dotnet run --project Development/NozzleCheck/NozzleCheck.csproj -c Release`。需在 OPM 2024 中实测六种轴向、大小口径的相并与孔切除、连续点取及预览清理。## 放置管夹（A2 / E1 / K1 / T4）

首页只有一个“放置管夹”入口；进入后由页面最上方的下拉框切换四种管夹，参数区随类型切换。四种操作方式一致：点【开始点取】后在模型中悬停选择管道 / 直线 / 多段线，左键在点击处沿其轴线生成整组预览；改参数自动重建预览；点【确定生成】才写入 `PipeSupportComponents`。右键、结束点取、取消预览、返回首页与关闭工作区都会清理未确认预览。类型与各类型参数跨会话记住（`%LOCALAPPDATA%\SteelSectionProbe\pipe_clamp_last.json`）。

| 类型 | 适用范围 | 编号 |
| --- | --- | --- |
| A2 标准型 2 螺栓管夹 | DN15~750（表 1，24 档） | `DN管径` |
| E1 不保温管导向架 | DN15~900（表 1 子项 A~E） | `E1-子项-H`（不锈钢加 `-S`） |
| K1 不保温管限位架 | 1/2″~36″（子项 A~C） | `K1-子项[-管径]` |
| T4 高温隔热限位管托 | DN80~600（表 1 / 表 2） | `名称-管径-温度代码-H-L-材料代码-F` |

### A2 标准型 2 螺栓管夹

圆柱 ∪ 长方体后剪出管夹状，再开两个耳板螺栓孔并配 2 套简化紧固件（螺杆 + 六角头 + 带中心孔的六角螺母，不做布尔融合）。管夹内孔 A′ = A + 2×保温厚度，且孔心距 B 同步外移同样的保温厚度（否则孔会落进放大后的孔洞区域被剪掉、螺栓错位）。选中管道时按**公称直径**匹配表 1 并读其保温厚度；选中直线或匹配不上时改用面板管径与保温厚度。绕轴角度自动对齐（本地 Z 竖直向上），无需手工指定旋转角。

### K1 不保温管限位架

点选一根水平管道或普通直线（与水平面夹角超过 5° 会被拒绝）。两组限位块沿管轴一前一后，内侧间距 = 面板输入的已有钢构宽度 W。子项 A 是 H100×100×6×8 沿腹板高度中点剖开取半片的 T 形（翼缘 100×8 + 腹板 6×42），竖直放置、管道焊在其顶端截面、无底板；子项 B/C 是完整 H 型钢、水平且长度沿管轴，管道骑在两翼缘端面上，底板焊在朝已有钢构那一端的**截面**上。子项按 DN 自动选、可改。管道骑座高差 contact = √((OD/2)² − (b/2)²)，钢板顶面与翼缘端面的间距 = 2×(OD − √(OD² − (b/2)²))，其中 b = 型钢高度 − 2×翼缘厚。

### T4 高温隔热限位管托

点选一条管道轴线。上下两片承重板包在保温层外（对开 45°、两端留间隙 J），用耳板 + 4 颗带碟簧垫圈的螺栓连接；底座 = 底板 + 横向弧顶支撑（L > 600 时加中间肋板）+ 中央纵向腹板，弧顶减圆柱成形。H 由隔热层厚度 B 查表得到（面板只读显示）；底板宽度按保温层外径 D = OD + 2B 查表 2。耳板沿轴 2 组（L≤600）或 3 组（L>600），每组两处分口各 2 块。可选创建管道本体与保温层，默认都不建。

四种管夹的分层位置：表数据与元素读取在 `Data/PipeClamp/`（`PipeClampCatalog`、`A2ClampCatalog`、`K1LimitCatalog`、`T4ShoeCatalog`、`PipeClampReader`）；纯参数与结果在 `Domain/PipeClamp/`；尺寸推导与 Bentley 建模在 `Services/PipeClamp/`（A2/K1/T4 各一对 Calculator + Builder，加共用的 `PipeClampFrame`）；点取与预览所有权在 `Tools/PipeClamp/`；页面在 `UI/PipeClamp/`。E1 的数据、计算与建模仍在 `Data/E1Guide/`、`Domain/E1Guide/`、`Services/E1Guide/`，只把面板并入了本页面，不再有独立入口。四种管夹共用 `Tools/PipeClamp/PipeClampLocateTool.cs` 与 `PipeClampPreviewSession.cs`。

### E1 不保温管导向架

在上面的“放置管夹”页面把类型切到 E1 后，选择 DN15～DN900、A～E 子项（默认按 DN 自动选型）、构件A材料和是否为不锈钢管道。点取 OpenPlant 直管时读取其 EC 管径；点取普通直线或多段线时使用页面所选 DN。多段线按三维点取位置选最近的有效直线段，只使用该段的方向和标高；允许轴线坡度至 30°，在该段上投影得到放置中心。管轴取值顺序：中心线曲线 → 元素范围（包围盒）最长边；**包围盒兜底不限定水平，竖直管道同样适用**（与 Python 的 `axis_from_bbox` 一致），近似定位时页面会给出提示而不报错。各类型自己的走向限制由各自的 Calculator 负责（K1 ≤ 5°、E1 ≤ 30°）。悬停定位后左键一次生成两根镜像竖直构件的可撤销 `E1_RACK` Cell 预览；不锈钢选项另生成两块 06Cr18Ni9 薄板。构件底面位于管底标高，内侧面距管壁 3 mm。高度 H 在外径小于 88.9 mm 时为 50 mm，其余为外径半径加 50 mm 后四舍五入。编号为 `E1-子项-H`，不锈钢增加 `-S`，界面管径统一显示 DN。确认后写入 `PipeSupportComponents` 公共 ItemType：1 条 Assembly、2 件构件A和可选的 2 件薄板。支吊架统计页可以预览与导出材料表。源管道始终保留，不受删除选项影响。只有点取单根普通直线时，“确认后删除辅助线”才可勾选；默认不勾选，勾选后仅在确认时删除该辅助线。管道和多段线始终保留，不会删除整个多段线。

右键、结束点取、取消预览、返回首页和关闭窗口都会清理未确认预览。修改参数或重新点取会先写入替代预览再删除旧预览。A 为 50×10 板件；B、C、D、E 的型钢轮廓分别从本工程 `Resources/profiles.bin` 加载等边角钢 L50x50x6、平行腿槽钢 10、热轧 H 型钢 H100x100x6x8xr8 和 H150x150x7x10xr8，圆角保留真圆弧。E1 的 DN/外径与子项表在 `Data/E1Guide/E1GuideCatalog.cs`；修改这些值后重新编译。如需修改型钢规格，则修改 `Development/profile_catalog/` 并运行 `python -B Development/export_profiles.py`，然后重新编译；C# 运行时不读取或调用 Python 插件。

纯计算检查：`dotnet run --project Development/PipeClampCheck/PipeClampCheck.csproj -c Release`（覆盖 A2 表 1 与尺寸推导、K1 子项/骑座高差/底板盒/坐标架、T4 表 1 表 2 与保温高度表/布尔布局/孔位校核，以及四种管夹的清单属性契约），另有 `dotnet run --project Development/E1GuideCheck/E1GuideCheck.csproj -c Release` 覆盖 E1 的纯计算。Bentley 环境中的 EC 管径与保温厚度读取、多段线段点取、型钢扫掠、布尔运算、普通 Cell 预览删除以及 ItemType 汇总还需在 OPM 2024 用真实 DGN 实测。

## G2 混凝土锚板（膨胀螺栓）

首页点击“混凝土锚板”。详情页选择表 1 子项 A~D、安装面（竖直墙面 / 水平楼板顶面 / 水平楼板底面）与朝向；间距 S 默认取该子项的 MIN.S，切换子项时自动重置，并校验不得小于 MIN.S。页面同时显示锚板与锚栓规格、有效埋深、混凝土边缘要求 MIN.C / MIN.h 以及允许拉力与剪力。

在三维 DGN 中点击“开始点取”，左键点取混凝土表面上锚板背面的中心点，生成 `CONCRETE_ANCHOR_PLATE` 普通 Cell 预览；修改参数会先建立新预览再删除旧预览。“确定生成”保留单元并写入 `PipeSupportComponents` 公共 ItemType：1 条 Assembly、1 块锚板与 4 套膨胀锚栓。右键、结束点取、取消预览、返回首页和关闭工作区都会清理未确认预览。子项 / 间距 / 朝向 / 安装面会跨会话记住（存 `%LOCALAPPDATA%\SteelSectionProbe\g2_anchor_last.json`）。

几何与 `管道支吊架/G2-[混凝土锚板（膨胀螺栓）].py` 及 `模块/公共/混凝土锚板.py` 逐项对齐：局部原点为板背面中心（贴混凝土面），局部 +X 恒为混凝土外法向；锚板为正方形，边长 = S + 100（边距 50）、厚 T，四个 φG 螺栓孔位于 x=0 平面、间距 S×S 并居中。锚栓总长 L 保持不变，螺杆外端超出螺母外端面 5 mm（露出的丝头），因此有效埋深 = L − (板厚 T + 垫圈厚 + 螺母高 + 5)，表 1 四个子项均满足各自的 h_ef。每根锚栓由埋入端膨胀套管、螺杆、垫圈与六角螺母四段最简单的拉伸 / 圆柱构成，**不做布尔融合**（允许实体重合），与脚本一致。埋入端膨胀套管外径取 `1.7 × d`、长度取有效埋深的 0.55。安装面决定局部 +X：竖直墙面在水平面内绕 Z 旋转；楼板顶面 +X = 世界 +Z（锚板水平、螺栓朝下插入楼板）；楼板底面 +X = 世界 −Z（螺栓朝上）。朝向角在各自平面内绕外法向旋转锚板。

实现分布于 `Domain/G2Anchor/`、`Data/G2Anchor/`、`Services/G2Anchor/`、`Tools/G2Anchor/` 和 `UI/G2Anchor/`。局部坐标轴定义集中在 `G2AnchorCalculator.Axes`（纯计算），`G2AnchorFrame` 与纯计算检查工程共用同一份，避免两份朝向定义。纯计算检查：`dotnet run --project Development/G2AnchorCheck/G2AnchorCheck.csproj -c Release`，覆盖表 1 四子项尺寸与埋深自检、间距 S 与非法输入拒绝、三种安装面在多个朝向角下的三轴正交与右手系。Bentley 点取、普通 Cell 写入、预览删除与 ItemType 附加仍需在 OPM 2024 中实测。


## 点选参考文件里的元素

MicroStation 的参考文件（reference attachment）里的元素，其 ElementId 属于**参考文件自己那个文件的 ID 空间**，按 ID 在活动文件里查不到 —— 这正是早期版本点选参考元素会报"所选元素已不存在"的原因。

现在所有"点选元素"的功能都支持参考文件：定位回调把元素与**它所属的模型引用**一起上报（`Data/LocatedElement.cs`），读取器用那个模型去查元素、读几何与 EC。几何读取分两条路径：元素属于活动模型时仍走原 COM 路径（行为不变）；元素来自参考文件时改用 .NET 曲线查询（`CurvePathQuery.ElementToCurveVector` + `CurveVector.GetRange / GetStartEnd`），因为 COM 的 `ActiveModelReference` 只认活动模型。

还有一道与 ID 无关的关卡：MicroStation **默认不把参考元素交给元素集合工具**，所以即使读得到几何，点上去仍会报"元素位于只读参考文件之中"。这是工具层的策略，不是元素读取的问题，也**不取决于参考附件的类型或设置**（参考文件本身在 MicroStation 里永远不可编辑，没有"改成可写"这种选项）。修法是覆写 `DgnElementSetTool.GetReferenceLocateOptions()` 返回 `RefLocateOption.TreatAsElement`（把参考元素当普通元素来定位），并在 `OnPostLocate` 里加一层兜底放行。三个点选工具（放置管夹 / 构件特性查询 / 弯头耳轴）都已覆写。

适用功能：放置管夹（A2 / E1 / K1 / T4）、G2 混凝土锚板、弯头耳轴、构件特性查询。点取到参考元素时，界面会在元素信息与尺寸来源说明里标注"（参考文件）"。

**放置管夹有一条专门的"临时辅助线"流程**（`Services/PipeClamp/TempAxisLine.cs`）：点选参考文件里的管道时，插件先读出它的管轴与管道属性，再**在活动文件里按这段轴线生成一条普通直线**，然后用**已验证的按线路径**重新读一遍（并把参考元素读到的公称直径 / 保温 / 管道号并到这条线上），最后在确认或取消时**自动删除**这条临时线。这样"生成"这一段完全不接触参考文件 —— 不会碰到"参考元素写不进 / 删不掉 / 几何读不稳"这类问题，参考元素的影响面只剩一次轴线读取。临时线在切换到活动文件里的元素、重新点选、结束点取、切换管夹类型、离开页面时都会清理；异常退出（宿主崩溃）时最多残留一条普通直线，手动删除或撤消一步即可。界面会在预览行写明"已按参考管轴在活动文件中生成临时辅助线，确认或取消后自动删除"。

两个前提：该参考附件的 **Locate** 开关必须打开（否则连点都点不到），要用捕捉画辅助线时 **Snap** 也要打开。另外"确认后删除辅助线"只对**活动文件**里的直线生效 —— 参考文件里的直线不会提供该选项，也不会被执行删除。

单位换算要留意的差别：COM 的坐标是 master 单位（`× UorPerMaster / uorPerMm`），.NET 几何坐标是 UOR（`/ uorPerMm`），两者不能混用。
