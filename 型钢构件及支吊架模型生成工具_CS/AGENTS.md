# 型钢构件及支吊架模型生成工具：AI 与开发者协作规范

本文件适用于 `型钢构件及支吊架模型生成工具_CS/` 目录及其全部子目录。

它既是人类开发文档，也是后续编码 Agent 的执行规范。任何新增功能、重构或修复都应先阅读本文，再检查真实代码；不要只根据文件名或旧对话猜测当前实现。

## 1. 项目目标

本项目是 OpenPlant Modeler 2024 的 C# AddIn，目标是提供统一的：

- 国标型钢截面放置；
- 沿路径扫掠生成型钢实体；
- 各类管道支吊架及组合构件生成；
- 公共 ItemType、统计和清单数据写入；
- 可持续扩展的功能首页与独立功能页。

架构上的首要目标不是“用最少文件实现功能”，而是：

1. 尽量复用已有型钢数据和几何能力；
2. UI、交互工具、业务建模、领域数据和基础设施相互分离；
3. 新功能能够独立阅读、独立测试、独立维护；
4. 临时预览必须可安全取消，不得在模型中留下垃圾元素；
5. 不破坏已有 Key-in、资源名称和统计契约。

## 2. 当前技术约束

- 目标框架：`.NET Framework 4.8`；
- 平台：`x64`；
- C# 版本：`7.3`；
- 宿主：OpenPlant Modeler 2024 / Bentley MicroStation API；
- UI：WPF/XAML；顶层 Bentley 宿主仍继承 `Adapter`，通过 `ElementHost` 承载 `WorkspaceView`；
- 默认 SDK 根目录：`C:\Program Files\Bentley\OpenPlant 2024\IsometricsManager`；
- 命名空间目前统一为 `SteelSectionProbe`；
- 工程文件名为 `SteelSupportModeler.csproj`，但运行时程序集名仍为 `SteelSectionProbe`，以兼容现有 OPM 加载配置；
- 用户界面文案使用中文，内部类型与方法名优先使用清晰英文；
- 源文件使用 UTF-8，禁止引入乱码字符串。

不要使用高于 C# 7.3 的语法，例如文件级命名空间、记录类型、init-only 属性或新的模式匹配语法。

## 3. 当前目录职责

```text
型钢构件及支吊架模型生成工具_CS/
├─ App/                 AddIn 生命周期、跨功能页契约
├─ Registration/        Key-in 处理器与 commands.xml
├─ UI/                  工作区、首页、功能页和通用视觉控件
├─ Domain/              纯领域模型，不负责读文件或操作 Bentley 模型
├─ Data/                数据读取、目录查询和数据源适配
├─ Services/            可复用几何、建模和业务服务
├─ Tools/               Bentley 点取、定位、动态绘制等交互状态机
├─ Infrastructure/      ItemType、统计、日志、导出等外部基础设施
├─ Resources/           嵌入 DLL 的运行时资源
├─ Development/         开发期数据生成、转换和验证脚本
├─ Deployment/          编译产物安装与部署脚本
├─ bin/、obj/            编译输出，不是业务源码
├─ SteelSupportModeler.csproj
└─ README.md
```

### 3.1 依赖方向

推荐依赖方向如下：

```text
UI ───────┐
Tools ────┼──> Services ──> Domain
          ├──> Data ──────> Domain
          └──> Infrastructure

Registration ──> App / UI
```

强制规则：

- `Domain/` 不得引用 WPF/WinForms、Bentley API、文件系统或嵌入资源；
- `Data/` 不得创建模型元素，也不得弹窗；
- `Services/` 不得直接控制主窗口页面跳转；
- `Tools/` 负责 Bentley 交互状态，不应保存大量标准表数据；
- `UI/` 不得实现复杂几何算法；
- `Registration/` 只负责命令入口，不承载业务建模；
- `Infrastructure/` 不得反向依赖具体功能页。

如果一个新类同时负责读取数据、显示控件、点选元素和创建几何，说明分层失败，必须拆分。

## 4. 现有能力清单与复用优先级

开发新功能前，必须按以下顺序检查可复用能力。

### 4.1 型钢目录数据

相关文件：

- `Domain/ProfileModels.cs`
- `Data/RuntimeData.cs`
- `Resources/profiles.bin`
- `Development/export_profiles.py`
- `Development/profile_catalog/`（本工程内可编辑的型钢规格与纯轮廓生成代码）

当前领域对象：

- `FamilyData`：型钢族；
- `ProfileData`：具体规格及尺寸参数；
- `ModeData`：插入基准及闭合轮廓；
- `SegmentData`：直线或圆弧轮廓段。

新增支吊架若使用槽钢、角钢、工字钢或 H 型钢，必须优先从 `RuntimeData.Families` 查询现有规格，禁止：

- 在新功能中再次硬编码同一套型钢尺寸；
- 复制一份 `profiles.bin`；
- 为每种支吊架建立互不一致的型钢规格表；
- 直接从 UI 控件文本反向解析几何尺寸。

只有现有目录确实不存在所需数据时，才允许扩展数据管线。扩展时应修改本工程 `Development/profile_catalog/` 中对应的 `*_data.py`；轮廓或插入基准变化时修改 `*_geometry.py`。然后运行 `python -B Development/export_profiles.py` 重新生成 `Resources/profiles.bin` 并编译，不要手工编辑二进制文件，也不要再修改或读取同级 Python 插件作为本工程的数据源。

### 4.2 型钢截面和扫掠几何

相关文件：

- `Services/GenericProfile.cs`
- `Tools/ProfilePlacement.cs`
- `Tools/SweepPlacement.cs`

`GenericProfile` 当前提供：

- `Curves(...)`：创建原生 `CurveVector`；
- `Native(...)`：创建 DGN 截面元素；
- `Preview(...)`：创建 COM 动态预览轮廓；
- `SweepProfile(...)`：在路径起点构造垂直于切线的截面。

复用原则：

1. 新功能只是生成型钢杆件时，应复用 `ModeData` 和 `GenericProfile`；
2. 新功能需要多个型钢构件拼装时，应创建组合构件 Builder，不要复制截面算法；
3. 新功能需要不同交互流程时，应新建 Tool，但 Tool 仍调用公共建模服务；
4. 不要让新的支吊架功能直接调用 `SteelSectionPage`；
5. 不要为了复用而直接调用带有当前 UI 状态的 `SweepPlacement`。

`SweepPlacement` 目前同时包含交互状态和扫掠创建逻辑。若新功能也需要程序化创建型钢杆件，正确做法是：

1. 将无 UI 状态的“根据规格、坐标系和路径创建扫掠体”提取到 `Services/SteelMemberFactory.cs`；
2. 让现有 `SweepPlacement` 改为调用该服务；
3. 新支吊架 Builder 同样调用该服务；
4. 保留预览所有权和确认/取消逻辑在各自 Tool 或会话对象中。

禁止从 `SweepPlacement` 复制一份扫掠实现到新功能。

### 4.3 统计与 ItemType

相关文件：

- `Infrastructure/Statistics.cs`

现有实现写入 `PipeSupportComponents` 公共 ItemType 库。新增构件必须先检查该契约是否能够表达：

- Assembly / Component；
- 支吊架类型；
- 规格；
- 设计长度；
- 数量、单位；
- 管线或编号信息。

如果字段足够，扩展公共统计服务，不要为每个功能创建新的 ItemType 库。如果确实需要新字段，应保证：

- 对旧 DGN 文件兼容；
- 缺少字段时可增量创建；
- 已存在的数据不会被覆盖；
- ItemType 名称稳定；
- README 和本文同步记录契约变化。

## 5. 新功能应如何组织

### 5.1 推荐的跨层目录

当某个功能超过一个简单页面或包含独立建模逻辑时，在对应层下建立相同的功能子目录。例如新增“门型架”：

```text
Domain/PortalFrame/
    PortalFrameParameters.cs
    PortalFrameResult.cs

Data/PortalFrame/
    PortalFrameCatalog.cs

Services/PortalFrame/
    PortalFrameCalculator.cs
    PortalFrameBuilder.cs

Tools/PortalFrame/
    PortalFramePlacementTool.cs
    PortalFramePreviewSession.cs

UI/PortalFrame/
    PortalFramePage.xaml
    PortalFramePage.xaml.cs
    PortalFramePreviewControl.cs
```

这种组织方式保留了项目的分层结构，也能让人类快速搜索同一功能的所有组成部分。

只有真正跨多个功能复用的类，才放在层目录根部。例如：

- `Services/SteelMemberFactory.cs`
- `UI/Themes/Theme.xaml`
- `UI/WorkspaceView.xaml`
- `Infrastructure/Statistics.cs`

不要建立 `Common/Utils.cs` 一类无限膨胀的杂物文件。

### 5.2 文件命名

使用能够表达职责的名称：

- `...Parameters`：输入参数；
- `...Catalog` / `...Repository`：数据查询；
- `...Calculator`：纯数值计算；
- `...Builder` / `...Factory`：创建模型几何；
- `...Tool`：Bentley 交互命令；
- `...PreviewSession`：临时模型元素生命周期；
- `...Page`：工作区功能页；
- `...PreviewControl`：仅负责 UI 绘制的控件。

避免使用 `Helper`、`Manager`、`NewClass`、`Utils2` 等无法表达边界的名字。

## 6. 新功能接入工作流

后续开发者或 Agent 应按以下顺序实施。

### 步骤 1：盘点现有能力

先使用代码搜索确认：

- 所需型钢规格是否已在 `RuntimeData` 中；
- 所需轮廓、扫掠或坐标系是否已有服务；
- 是否已有相似 Tool；
- 是否可以复用 `PipeSupportComponents` 统计契约；
- 仓库 Python 版支吊架中是否已有经过验证的计算逻辑或标准表；型钢规格以本工程 `Development/profile_catalog/` 为唯一可编辑源。

允许参考 Python 版算法和数据，但 C# 版运行时不得依赖启动 Python。

### 步骤 2：定义纯领域输入和结果

在 `Domain/<Feature>/` 中定义参数和结果对象。单位必须写入字段名或 XML 注释，例如：

- `LengthMm`；
- `RotationDegrees`；
- `Quantity`。

领域对象不要持有：

- WPF/WinForms 控件；
- `Element`、`ElementHandle`；
- COM `Application`；
- 当前页面的静态引用。

### 步骤 3：接入数据

标准表、规格映射和默认参数放入 `Data/<Feature>/`。较大的静态数据放入 `Resources/`，并提供 `Development/` 下的生成脚本。

数据读取应做到：

- 加载一次、缓存复用；
- 缺少资源时提供明确异常；
- 校验数量、版本和必要字段；
- 不在 UI 事件里反复解析大型资源。

### 步骤 4：实现计算和几何

优先把计算拆成两部分：

1. `Calculator`：纯数学、尺寸推导、选型和校验；
2. `Builder`：把计算结果转换为 Bentley 几何。

纯计算应尽量不引用 Bentley API，以便编写普通单元测试。只有最终坐标、曲线、实体和模型写入需要进入 Bentley 边界。

如果必须创建新的建模逻辑：

- 通用型钢或通用板件逻辑放在 `Services/` 根部；
- 某一支吊架专用逻辑放在 `Services/<Feature>/`；
- 不得放进 `UI/`、`Registration/` 或 `Data/`；
- 不得把大段建模代码写在按钮点击事件中。

### 步骤 5：实现 Bentley Tool

交互点取、Locate、Dynamics、Reset 和 Cleanup 放在 `Tools/<Feature>/`。

Tool 的职责是：

- 获取用户输入；
- 管理交互状态；
- 调用 Calculator / Builder；
- 管理临时预览；
- 把状态消息交给页面或主窗口。

Tool 不应承担标准数据定义和复杂尺寸计算。

### 步骤 6：实现功能页

每个可从首页进入的模块实现 `IWorkspacePage`：

```csharp
internal sealed class ExamplePage : UserControl, IWorkspacePage
{
    public string PageId { get { return "example"; } }
    public string PageTitle { get { return "示例功能"; } }
    public string PageSubtitle { get { return "一句话说明"; } }
    public FrameworkElement View { get { return this; } }

    public void OnActivated() { }
    public void OnDeactivated() { /* 结束 Tool，清理未确认预览 */ }
    public void OnWorkspaceClosing() { /* 释放全部资源 */ }
}
```

接入页面时需要同时修改：

1. `UI/MainWindow.cs`：实例化并 `RegisterPage(...)`；
2. `UI/HomePage.cs`：增加功能入口卡片，使用唯一稳定的 `PageId`；
3. 必要时在 `Registration/Keyins.cs` 和 `Registration/commands.xml` 增加直接入口。

普通功能不需要额外 Key-in。只有需要脚本化调用或直接进入的核心流程才增加命令。

### 步骤 7：接入统计和确认流程

只有用户确认后，临时预览才成为正式模型元素并写入最终统计信息。不要在鼠标悬停时反复创建 ItemType。

### 步骤 8：补充文档和验证

更新：

- `README.md` 的功能和使用说明；
- 本文件中发生变化的架构或契约；
- 对应数据生成说明；
- 可运行的单元测试或验证脚本。

## 7. 预览、确认和取消的强制规则

所有会写入模型的交互功能必须明确区分：

```text
候选输入 -> 临时预览 -> 用户确认 -> 正式元素
                       -> 用户取消 -> 删除临时元素
```

强制要求：

- 每个功能只能拥有自己创建的预览元素；
- 重建时应先成功创建新预览，再删除旧预览，避免失败后什么都不剩；
- `Reset`、返回首页、关闭页面和关闭主窗口都必须清理未确认预览；
- 确认后必须解除预览所有权，防止 Cleanup 误删正式元素；
- 删除源路径、辅助线等破坏性操作只能发生在明确确认之后；
- `OnDeactivated()` 必须结束当前 Tool；
- `OnWorkspaceClosing()` 必须可重复调用而不报错；
- 不得依赖垃圾回收器删除 DGN 元素。

## 8. 坐标、单位和几何约定

### 8.1 单位

- 业务尺寸和标准表统一使用毫米；
- 重量使用 `kg/m`；
- 面积按现有目录字段约定使用 `cm²`；
- 角度在领域层使用度，并在进入三角函数前转换为弧度；
- DGN UOR 转换只在 Bentley 建模边界进行。

不要在 UI、Calculator 和 Builder 中分别重复一套单位换算。

### 8.2 坐标系

- 明确记录局部 X/Y/Z 的含义；
- 路径扫掠必须处理接近竖直的起始切线；
- 叉积结果必须校验长度，禁止静默产生 NaN；
- 圆弧应继续使用真圆弧，不要用大量短线替代正式模型几何；
- UI 中的二维轮廓预览可以采样圆弧，但不得把采样结果用于最终 DGN 建模。

### 8.3 模型写入

- 创建元素前确认活动模型存在；
- 仅三维功能必须检查 `Is3d`；
- `AddElement` / `AddToModel` 失败时提供可理解的错误；
- 不要持有已经删除或失效的 COM 元素引用；
- 从 COM ID 查找原生元素时检查空值和有效性。

## 9. UI 规范

现有视觉基础位于：

- `UI/Themes/Theme.xaml`
- `UI/WorkspaceView.xaml`
- `UI/HomePage.xaml`
- `UI/SteelSectionPage.xaml`

新增页面应复用这些控件和颜色，不要为单个页面另建一套主题。

统一要求：

- 首页只展示功能入口，不堆放业务参数；
- 功能参数只在对应详情页显示；
- 使用 XAML `Grid`、卡片和编号分区组织表单，禁止依赖绝对坐标拼页面；
- 状态统一写入 `MainWindow.SetStatus(...)` 的底部固定状态栏；
- 主操作复用 `Theme.xaml` 中的 `PrimaryButtonStyle` / `SecondaryButtonStyle`；
- 内容过高时使用 WPF `ScrollViewer`，并复用统一窄滚动条样式；
- 提供清晰的确认、取消和返回首页行为；
- 参数变化时更新页内预览，但不要在每次鼠标移动时执行昂贵实体建模；
- 不在单个页面重新定义与 `Theme.xaml` 冲突的字体、颜色和按钮模板，特殊几何预览绘制除外；
- 最小窗口尺寸下不得遮挡确认/取消按钮。

## 10. Registration 与兼容性

现有稳定命令：

```text
STEELPROBE SHOW
STEELPROBE PLACE
```

除非用户明确要求，不要重命名或删除它们。

命令新增流程：

1. 在 `Registration/Keyins.cs` 添加公开静态处理器；
2. 在 `Registration/commands.xml` 添加 Keyword 和 KeyinHandler；
3. 保持 `CommandTable.xml` 嵌入逻辑名称不变；
4. 编译后在 OPM 中实测命令加载；
5. 在 README 中记录。

资源逻辑名称 `SteelSectionProbe.profiles.bin` 也是兼容契约，不应随意改变。

## 11. 构建、验证和部署

### 11.1 编译

在本目录执行：

```powershell
dotnet build SteelSupportModeler.csproj -c Release
```

基本交付要求是 0 错误。新增警告必须解释并尽量清除。

### 11.2 最低验证清单

每次功能修改至少检查：

- 首页能够进入目标功能并返回；
- `STEELPROBE SHOW` 正常；
- `STEELPROBE PLACE` 仍能直达型钢页；
- 类型、规格和插入基准联动；
- 页内轮廓预览更新；
- Bentley Dynamics 预览更新；
- 确认后元素保留；
- 取消、Reset、返回首页和关闭窗口不会留下预览；
- ItemType 写入正确；
- 三维限制和非法路径错误明确；
- 高 DPI 和最小窗口尺寸下控件不重叠；
- 窄滚动条可通过滚轮和拖动使用。

纯计算模块应另有单元测试，至少覆盖正常值、边界值和非法输入。

### 11.3 DLL

正常输出：

```text
bin/Release/net48/SteelSectionProbe.dll
```

备用部署件：

```text
bin/Release/net48_full/SteelSectionProbe.dll
```

编译后的 DLL 不是源码真相。不要只替换 DLL 而不提交对应源码和文档。若更新备用 DLL，必须确认它与本次源码编译产物的 SHA256 一致。

## 12. 禁止的实现方式

后续开发不得：

- 把新功能继续堆进 `SteelSectionPage.xaml.cs`；
- 在按钮事件里直接写数百行建模代码；
- 为支吊架复制一份型钢规格和轮廓算法；
- 让 C# 运行时启动 Python 才能完成建模；
- 把业务数据写进 `HomePage.cs`；
- 从其他功能页读取控件值作为业务输入；
- 使用全局静态变量共享大量可变参数；
- 在预览尚未确认时写入最终统计；
- 忽略 Cleanup、Reset 或页面离开事件；
- 为绕过错误吞掉所有异常且不给用户状态提示；
- 修改无关 Python 插件或仓库其他模块；
- 用生成 DLL 代替源码验证。

## 13. 当前已知边界与后续重构建议

当前代码已经完成基础分层，但仍有以下边界需要后续开发注意：

1. `GenericProfile` 同时包含原生 DGN 和 COM 轮廓创建；若继续扩大，应拆成纯轮廓服务与 Bentley 适配器；
2. `SweepPlacement` 仍同时管理预览状态和底层扫掠创建；第一个需要程序化创建型钢杆件的支吊架功能应优先提取 `SteelMemberFactory`；
3. `Statistics` 当前偏向型钢记录；扩展支吊架前应先定义稳定的 Assembly / Component 写入 API；
4. `WorkspaceView` 和 `HomePage` 的功能注册目前是显式代码；功能数量较多后可引入轻量 `FeatureDescriptor`，但不要过早使用复杂依赖注入框架；
5. Bentley 运行时交互尚无法由普通 `dotnet test` 完整覆盖，因此编译通过不等于 OPM 实测通过。

重构这些边界时，必须先让现有型钢页改用新服务，再让新功能复用；不要保留新旧两套并行实现。

## 14. Agent 开发步骤

任何 Agent 接手任务时应执行：

1. 阅读本文件、`README.md` 和目标功能源码；
2. 检查 `git status`，保留用户已有改动；
3. 使用搜索确认是否已有可复用数据、几何或 Tool；
4. 写明将修改的层和复用点；
5. 先实现纯模型和服务，再接 Tool 和 UI；
6. 保证预览生命周期完整；
7. 编译并检查差异；
8. 若能进入 OPM，执行运行时验证；不能时明确说明未实测部分；
9. 更新文档和必要的部署 DLL；
10. 交付时列出修改文件、验证结果和剩余风险。

## 15. 完成定义

一项新功能只有同时满足以下条件才算完成：

- 放在正确目录和层级；
- 复用了已有型钢数据及几何能力，或说明为何不能复用；
- 没有把业务逻辑塞入 UI；
- 预览、确认、取消和 Cleanup 完整；
- 数据和单位约定清楚；
- 已接入首页和功能页生命周期；
- 已接入公共统计或明确说明不需要；
- `dotnet build -c Release` 通过；
- 已更新 README / 本规范；
- 已说明 OPM 实测结果或未实测原因。

如果无法满足其中一项，应把它作为明确的待办或风险写入交付说明，不得默认为“以后再说”。

## 16. 构件特性查询

`component-properties` 是只读工作区页面：首页入口位于 `UI/HomePage.xaml`，功能页位于 `UI/ComponentProperties/`，点取 Tool 位于 `Tools/ComponentProperties/`，EC 读取与几何快照位于 `Data/ComponentProperties/`，单位与管径推算位于 `Services/ComponentProperties/`。不创建 DGN 元素，也不写入 ItemType。点取使用 `DgnElementSetTool`：AccuSnap 悬停定位，单次左键 `DoLocate` 后只传元素 ID；右键 Reset 与页面按钮统一触发退出状态。EC 实例读取延后到 UI Dispatcher，并在 `FindInstances` 遍历内转为纯数据；不得把 `IDgnECInstance` 带出遍历。页面离开和关闭窗口必须终止点取。保留现有 `STEELPROBE SHOW` / `STEELPROBE PLACE` 命令。
## 17. 弯头耳轴四组合

首页唯一入口 `elbow-trunnion` 注册在 `UI/HomePage.xaml` 与 `UI/WorkspaceView.xaml.cs`。详情页在 `UI/ElbowTrunnion/`；弯头 EC 读取与 Python 表 1/Sch40 数据在 `Data/ElbowTrunnion/`；纯方向、长度和 F2/F4/F5 编号计算在 `Services/ElbowTrunnion/ElbowTrunnionCalculator.cs`；Bentley SmartSolid 鞍口、通孔、板件在 `Services/ElbowTrunnion/ElbowTrunnionBuilder.cs`；点取与预览所有权在 `Tools/ElbowTrunnion/`。四个组合分别对应原 `F2-[竖直弯头的竖直耳轴].py`、`F2-[水平弯头的竖直耳轴].py`、`F4-[竖直弯头的水平耳轴].py`、`F5-[水平弯头的水平耳轴].py`。

本功能不复用型钢目录或 `GenericProfile`：四个耳轴由钢管或圆钢、鞍口、通气孔和板件构成，原脚本的管径与壁厚来自独立的 Sch40/耳轴选型表，不是型钢轮廓。确认后使用同一个 `PipeSupportComponents` ItemType 库，在组合 Cell 上写 Assembly 与各 Component；原有属性名不变。弯头源元素保持不变。预览新元素成功写入后才删除旧预览；取消、切换方向、离开页面与关闭工作区均尝试清理预览，删除失败保留元素所有权并提示。方向区与参数区均使用双列布局。管径在页面与清单规格中统一显示 DN；组合编号默认使用公制 DN，用户可在“命名管径单位”中改用英制 NPS。F2/F4/F5 四组合共用这一编号选项，命名切换不改变建模尺寸，长度仍以 mm 计。点选弯头的首击只确定源构件；`ElbowTrunnionDragTool` 随后通过视图投影读取鼠标拉伸 H/L，动态帧只绘制临时线框；松开首击并移动鼠标后的下一次左键才固定长度。固定后创建可撤销 SmartSolid 预览，页面确认时才写入最终清单属性。拉伸阶段 Reset、离开页面或关闭窗口均结束工具；参数框可在固定长度后调整预览。


## 18. 支吊架统计

`support-statistics` 是只读页面，首页入口在 `UI/HomePage.xaml`，页面与导出按钮在 `UI/SupportStatistics/`。统计快照在 `Domain/SupportStatistics/`；`Data/SupportStatistics/SupportStatisticsReader.cs` 遍历当前 DGN 文件的模型与图形元素，读取 `PipeSupportComponents` 的 `PipeSupportAssembly_*`、`PipeSupportComponent_*` 实例并立即复制属性值；`Services/SupportStatistics/` 负责纯汇总及 Excel / JSON 文件写出。继续使用现有九个 ItemType 字段和公共库，不新增统计库，也不写入模型。Excel 保留原 Python 的“汇总 / 支吊架表 / 材料汇总表”三张表；导出前刷新数据。三个表格的横向滚动条使用页面局部样式与受限宽度，不扩大工作区；另存为建议名由活动 DGN 文件名、`_支吊架材料表_` 和 `yyyyMMddHHmmss` 时间戳组成，用户仍可修改。变更汇总口径或字段时，须同步 `Statistics.cs` 契约、README 和纯计算检查。
## 19. 罐壁人孔

首页唯一入口 `tank-manhole`，详情页在 `UI/TankManhole/`，规格表和纯计算分别在 `Data/TankManhole/`、`Services/TankManhole/TankManholeCalculator.cs`，Bentley SmartSolid 在 `Services/TankManhole/`，点取与预览所有权在 `Tools/TankManhole/`。原始来源为仓库同级 `罐壁人孔/tank_wall_manhole.py`。公称尺寸使用 DN450 / DN500 / DN600，业务几何尺寸用 mm，只有 Frame 将尺寸转换成活动 DGN 的 UOR。两种开盖形式共用基础筒节、法兰、盲盖、螺栓和把手；吊杆与铰链各由独立 Builder 路径添加。组合单元名保持 `TANK_WALL_MANHOLE`。本功能是罐体设备附件，原脚本没有支吊架 Assembly / Component 清单契约，不写入 `PipeSupportComponents`。

点取左键后才构造可撤销模型预览；参数变化重新构造时先写入新预览，再删除旧预览。右键 Reset、页面按钮、返回首页和关闭工作区均清理预览。C# 侧几何必须与 `罐壁人孔/tank_wall_manhole.py` 逐项对齐：吊杆回转支撑件的径向轮廓（双水平臂 16 厚、腹板 16 厚、背部外 R20 / 内 R10、开口端 30° 收窄到法兰厚度）其**外表面**在立柱轴线外 `D/2 + 20 + 16`——那 16 是原脚本 `BodyFromSweep` 把轮廓厚度加在扫掠路径终点之外产生的，改动支撑件时不要按脚本的长度公式（只算到路径终点）取 20；轮廓与尺寸放在 `TankManholeCalculator` 的 `DavitSupportAnchorY / DavitSupportOuterFaceY / DavitSupportChamferDistance / DavitSupportProfile`（纯计算，可在 `Development/TankManholeCheck/` 断言；`DavitSupportProfile` = 8 直线 + 4 真圆弧，`DavitSupportOutline` 把圆弧展开成 40 点仅供校验）。**圆角必须用真圆弧原语**（`CurvePrimitive.CreateArc` + `SolidPrimitiveFactory.Prism(profile, origin, extrusion)`）扫成真圆柱面；用 8 段折线近似会在圆角上留下成排分面棱（每段法向差 11.25°，OPM 里是一叠横线，而原脚本的 `BlendEdges` 是真圆角、没有这些线）。`SolidPrimitiveFactory.PolygonPrism` 只能给折线用，别拿它画圆角。吊杆的圆到扁头过渡同样按原脚本优先级：先 `Create.BodyFromLoft(profiles, guides, modelRef, periodic:false, segment:true)`（段间线性无平滑，等价原脚本的 `DgnRuledSweep`），失败才退回 24 段台阶近似（回退时轮廓反序，法向朝圆管一侧）；`BodyFromLoft` 的两个布尔量含义见 MSPy 存根 `Examples/Microstation/Intellisense/MSPyMstnPlatform.pyi`。M20 调节吊环螺栓圆环中心线半径 25（孔 Ø30）。30° 端部倒角用布尔差集；需在 OPM 核对。OPM 运行时必须检查所有 DN / 压力组合的扫掠和布尔差集、直纹放样、普通 Cell 形成、预览取消以及吊杆连接位置。纯计算检查位于 `Development/TankManholeCheck/`。
## 20. 实体管口

`solid-nozzle` 首页入口位于 `UI/HomePage.xaml`，详情页在 `UI/Nozzle/`，纯参数和结果在 `Domain/Nozzle/`，嵌入尺寸表读取在 `Data/Nozzle/`，计算与 Bentley 建模在 `Services/Nozzle/`，点取和预览所有权在 `Tools/Nozzle/`。原始数据 `实体管口/flange_data.json` 原样复制为 `Resources/nozzle_flange_data.json` 并嵌入 DLL。新增法兰尺寸时修改原始数据并重新复制或建立数据生成脚本，不在页面硬编码尺寸。与罐壁人孔共用 `Services/SolidPrimitiveFactory.cs` 的圆柱、扫掠和布尔操作。

管口总长度包含法兰厚度，业务输入均为 mm，Bentley 构件边界统一换算 UOR。仅允许当前等级和钢管系列同时存在且外径一致的 DN。螺栓孔默认不绘制；密封面凸台只有数据表提供外径和高度时才绘制。模型是一个 SmartSolid；确认前为工具拥有的预览元素，重新点取或修改参数先创建替代预览，Reset、页面离开和关闭时删除未确认元素。原 Python 工具为可视化管口，不创建 OPM 管道组件或支吊架材料条目，因此本功能不写入 `PipeSupportComponents`。纯数据检查位于 `Development/NozzleCheck/`，OPM 运行时需验证布尔相并/差集和预览删除。## 21. E1 不保温管导向架

`e1-guide` 首页入口在 `UI/HomePage.xaml`，详情页在 `UI/E1Guide/`。表 1 的 DN/外径与 A～E 选型数据在 `Data/E1Guide/E1GuideCatalog.cs`，纯布局计算在 `Services/E1Guide/E1GuideCalculator.cs`，Bentley 型钢和板件建模在 `Services/E1Guide/E1GuideBuilder.cs`，点取及预览所有权在 `Tools/E1Guide/`。与普通型钢路径扫掠共用 `Services/SteelMemberFactory.cs`；B～E 的轮廓从本工程的 `RuntimeData.Families` 读取，不依赖同级 Python 插件。该功能仅接受三维模型和坡度不超过 30° 的直线轴段。普通直线和多段线使用页面 DN，OpenPlant 管道优先读取 EC 管径。LineString 和仅含直线的 ComplexString 按三维点取位置选最近有效线段；其余线段不参与计算。放置点在选中线段三维投影并截断至端点。管轴取值顺序为：中心线曲线 → 元素范围（包围盒）**最长边**，与 Python `axis_from_bbox` 一致；**兜底不得限定水平** —— 竖直管道同样要靠它定位，加"必须水平"会把竖直管一律拒掉（与 Python 行为不符）。包围盒近似只给提示（`E1GuideSelection.AxisNote` → 页面预览行）不报错。各类型自己的走向限制放在各自 Calculator 里（K1 ≤ 5°、E1 ≤ 30°）。OPM 中需对斜向管道和多段线实测。

确认前预览是本功能持有的 `E1_RACK` Cell；重新点取先创建替代预览再清理旧元素，Reset、返回首页与关闭工作区均清理未确认元素。确认时才在公共 `PipeSupportComponents` 库写入 Assembly、构件A ×2 与可选薄板 ×2；源管道和多段线始终保留。“删除辅助线”仅在单根普通直线点取后可选，默认不勾选；确认时还需核对源元素仍为直线才执行删除。数据、长度和距离均使用 mm，命名仅使用 DN 档对应的 E1 子项与高度。纯计算检查位于 `Development/E1GuideCheck/`。


## 22. 混凝土锚板（G2）

`g2-anchor-plate` 首页入口位于 `UI/HomePage.xaml`，详情页在 `UI/G2Anchor/`。表 1 子项 A~D、安装面与建模常量在 `Data/G2Anchor/G2AnchorCatalog.cs`，纯参数与解析结果在 `Domain/G2Anchor/G2AnchorModels.cs`，校验与尺寸解析在 `Services/G2Anchor/G2AnchorCalculator.cs`，局部坐标在 `G2AnchorFrame`，Bentley 建模在 `G2AnchorBuilder`，点取与预览所有权在 `Tools/G2Anchor/`。原始来源为仓库同级 `管道支吊架/G2-[混凝土锚板（膨胀螺栓）].py` 与 `管道支吊架/模块/公共/混凝土锚板.py`。

局部坐标系原点为板背面中心（贴混凝土面的那一点），**局部 +X 恒为混凝土外法向**（锚栓露出的那一侧），混凝土在 −X 侧。三种安装面只改变三个局部轴的世界方向：`wall` 在水平面内绕 Z 旋转；`floor` 取 +X = 世界 +Z（锚板水平、螺栓朝下插入楼板）；`ceiling` 取 +X = 世界 −Z（螺栓朝上）。轴方向定义集中在 `G2AnchorCalculator.Axes`（纯计算），`G2AnchorFrame` 与 `Development/G2AnchorCheck/` 必须共用这一份，**不要在 Frame 里另写一套**。

锚板为正方形，边长 = S + 100（边距 50）、厚 T、四角 4 个 φG 孔。锚栓总长 L 保持不变，螺杆外端超出螺母外端面 5 mm（露出的丝头），故有效埋深 = L − (板厚 T + 垫圈厚 + 螺母高 + 5)，须不小于表 1 的 h_ef；不满足时抛中文错误（数据自检）。埋入端膨胀套管外径取 `1.7 × d`、长度取有效埋深的 0.55。每根锚栓由埋入端膨胀套管、螺杆、垫圈与六角螺母四段简单拉伸 / 圆柱构成，**不做布尔融合**（允许实体重合）——这是原脚本的既有行为，不要为了“更干净”改成相并。

预览为 `CONCRETE_ANCHOR_PLATE` 普通 Cell，由 `G2AnchorPreviewSession` 持有：重建时先写入新版、成功后再删除旧版，删除失败则回滚新版。**确认时才写 `PipeSupportComponents`**（1 条 Assembly + 锚板 ×1 + 膨胀锚栓 ×4），预览阶段只出几何。`Statistics.AttachG2Anchor` 的属性值必须与 `模块/公共/支吊架公共库.py` 的契约一致：`SupportType` 存**中文类型名**（`G2-[混凝土锚板（膨胀螺栓）]`），Assembly 记录的 `ComponentName` 固定为“支吊架”，构件记录用构件名（锚板 / 膨胀锚栓）。右键、结束点取、取消预览、离开页面与关闭工作区均清理未确认预览；子项 / 间距 / 朝向 / 安装面跨会话记住（`%LOCALAPPDATA%\SteelSectionProbe\g2_anchor_last.json`）。

纯计算检查位于 `Development/G2AnchorCheck/`：`dotnet run --project Development/G2AnchorCheck/G2AnchorCheck.csproj -c Release`。OPM 运行时需实测点取、普通 Cell 写入与删除、ItemType 附加，以及三种安装面下的锚板朝向与锚栓伸入方向。

## 23. 清单属性契约（所有写入 PipeSupportComponents 的功能共用）

`Infrastructure/Statistics.cs` 的每个 `AttachXxx` 都必须与 `管道支吊架/模块/公共/支吊架公共库.py` 的九字段契约一致——这是 Python 与 C# 两侧写入的记录能被同一套统计聚合的前提：

| 字段 | Assembly 记录 | Component 记录 |
| --- | --- | --- |
| `RecordKind` | `Assembly` | `Component` |
| `SupportType` | **中文类型名**（`E1-[不保温管导向架]` / `G2-[混凝土锚板（膨胀螺栓）]` / `F2-[竖直弯头的竖直耳轴]` …） | 与左列相同 |
| `AssemblyTag` | 支吊架编号 | 同一编号 |
| `ComponentName` | 固定为 `支吊架` | 构件名（构件A / 不锈钢薄板 / 锚板 / 膨胀锚栓 …） |
| `Specification` | 整组规格 | 构件规格 |
| `DesignLengthMm` / `Quantity` / `Unit` / `PipeNumber` | 0 / 1 / 套 / 管道号 | 设计长度 / 数量 / 件·块·套 / 管道号 |

**ASCII 代号只用于 ItemType 命名**（`PipeSupportAssembly_<代号>_<哈希>`），绝不写进属性值：写进去会让统计页的“按类型套数”显示英文代号，并与 Python 写入的同类记录分裂成两组。中文类型名一律由 `Data/<功能>/` 的常量或映射方法提供（`E1GuideCatalog.SupportType`、`ElbowTrunnionCatalog.SupportType`、`G2AnchorCatalog.SupportType`），不要在 `Statistics.cs` 里另写一份字面量。新增功能时必须同时在该功能的 `Development/<功能>Check/` 里断言这张映射，防止两边再次漂移。

## 24. 放置管夹（A2 / E1 / K1 / T4 合并入口）

首页只有 `pipe-clamp` 一个入口（`UI/PipeClamp/PipeClampPage.xaml`），页面顶部下拉切换四种管夹，参数区按类型切换可见性。**不要为管夹类功能再新增首页入口** —— 新管夹作为下拉里的一个 `PipeClampKind` 加进来即可（同步 `PipeClampCatalog`、`PipeClampLastChoice` 的记忆字段、`Development/PipeClampCheck` 的断言与 README 的类型表）。

四种管夹共用 `Tools/PipeClamp/PipeClampLocateTool.cs`（点选管道 / 直线 / 多段线，只上报元素 ID 与点击点）与 `PipeClampPreviewSession.cs`（预览生命周期 + 按种类分派清单写入）。`Data/PipeClamp/PipeClampReader.cs` 复用 `E1GuideReader` 的轴线与管道判定，再补公称直径、外径与保温厚度（EC 属性 `INSULATION_THICKNESS`；值落在 (0,1) 时按米计、乘 1000 转毫米）。

- **A2**（`A2ClampCatalog` / `A2ClampCalculator` / `A2ClampBuilder`）：表 1 只按**公称直径数值**匹配（与脚本 `_match_table_dn` 一致，不拿外径比）；保温时内孔 A′ = A + 2B，且孔心距 B 必须同步外移 B，否则孔会落进放大后的孔洞区域被剪掉、螺栓随之错位。绕轴角度由 `PipeClampFrame.Axes` 自动给出（局部 Z 竖直向上），不给用户旋转角入口。
- **K1**（`K1LimitCatalog` / `K1LimitCalculator` / `K1LimitBuilder`）：只接受与水平面夹角 ≤ 5° 的管轴。子项 A 的半片 T 形截面在本地自建（8 点、无圆弧）；子项 B/C 的 H 型钢取 `geometric_center` 轮廓。**H 型钢轮廓的 2D x 是翼缘宽 B、y 是截面高 H**（见 `型钢截面生成器/steel_sections/steel_hbeam_geometry.py` 的顶点定义），换轴时别弄反，否则“腹板水平、两翼缘竖直”会变成另一种姿态。
- **T4**（`T4ShoeCatalog` / `T4ShoeCalculator` / `T4ShoeBuilder`）：H 只能由隔热层厚度 B 查表得到，面板只读显示，**不要给用户直输 H 的入口**。布尔顺序固定为：外圆柱 − 内圆柱 − 45° 矩形贯穿体 → 每块耳板开孔后并入 → 底板 + 弧顶支撑（减圆柱成形、必要时再减对开间隙）并入。切口方向一律用 `T4ShoeCalculator.CutFrame` 的 (c, s) 做 (x, a, b) 映射，不要自己推坐标。
- **E1**：面板并入本页，数据 / 计算 / 建模仍在 `Data/E1Guide/`、`Domain/E1Guide/`、`Services/E1Guide/`。“确认后删除辅助线”只对单根普通直线有效，删除前要核对源元素仍是直线，且管道与多段线始终保留。

型钢轮廓的三连查找统一走 `Data/ProfileLookup.cs`（纯查表，接受 `FamilyData[]`，因此纯计算检查工程也能链接），不要在功能里另写一套。新增管夹时若需要新增型钢规格，仍走 `Development/profile_catalog/` + `export_profiles.py` 的既有流程。

## 25. 点选元素的功能必须传递元素所属的模型（参考文件支持）

参考文件（reference）里的元素，其 ElementId 属于**它自己那个文件的 ID 空间**，按 ID 去活动模型里查是查不到的。因此所有"点选元素"的工具都必须上报 `LocatedElement`，读取器必须接受并透传 `DgnModelRef`：

- **工具**：在定位回调内 `LocatedElement.From(element)` 取 `element.DgnModelRef` 与 `ElementId`（不要把 Bentley 的 `Element` 对象带出回调），点击点放进 `ClickX/Y/Z`；
- **读取器**：签名统一为 `Read(DgnModelRef modelRef, ulong id, …)`，并保留 `Read(id, …)` 作为"活动模型"的快捷转发；内部用 `ComponentPropertyReader.ResolveModel(modelRef)` 拿到正确的模型；
- **几何**：**活动模型走原 COM 路径，参考元素走 .NET 曲线查询**（`CurvePathQuery.ElementToCurveVector` + `CurveVector.GetRange / GetStartEnd`）。COM 的 `ActiveModelReference` 只认活动模型，**绝不能用它读参考元素** —— 这是"点不到参考文件里的管道"的根因；
- **单位**：COM 坐标是 master 单位（`× UorPerMaster / uorPerMm`），.NET 几何坐标是 UOR（`/ uorPerMm`），两者换算不同，不要混用；
- **定位策略**：MicroStation **默认不把参考元素交给 `DgnElementSetTool`**，点上去会报"元素位于只读参考文件之中" —— 这道关卡与 ElementId 无关、也与参考附件的类型/设置无关（参考文件在 MicroStation 里永远不可编辑）。凡是只需要**读取**的定位工具，都必须覆写 `protected override RefLocateOption GetReferenceLocateOptions()` 并返回 `RefLocateOption.TreatAsElement`（枚举是标志位：`Normal=0 / SelfAttachment=1 / Editable=2 / TreatAsElement=4`），再加一层 `OnPostLocate` 兜底（基类拒绝且元素来自参考文件时返回 true）。**`SetRefLocateOption` 在 C# 侧不存在**，别照 Python/C++ 的写法找。

补充：`Element` 没有 `ElementRange` / `ModelRef` 属性，但**有 `DgnModelRef` 与 `DgnModel`**；`HitPath` 也没有 `GetHeadElementRef`。需要查 Bentley API 真实签名时，用 `_apidump` 那类"只读元数据"的办法（`PEReader` + `MetadataReader`，可打印完整签名）—— 注意 **`DgnElementSetTool` 在 `Bentley.DgnDisplayNet.dll` 里，不在 `Bentley.DgnPlatformNET.dll`**，按类型名找 DLL 时先 `grep -a` 一下。**不要用 PowerShell 的 `Reflection.Assembly.LoadFrom`**（被安全策略拦截），也不要用"故意编译报错"的探针去猜不存在的成员：编译器的函数体分析会被声明级错误压制，可能给出"看起来没报错"的假象。

破坏性操作（删除辅助线等）必须排除参考元素：参考元素的 ID 在活动模型里删不掉，应提前禁用选项并说明原因。
