# 支吊架 v4 UI 检查

2026-10-29：用户要求开始点取直接放弃旧选择。管夹/保冷立管/门型架的已激活按钮分支新增对幂等Begin的调用，契约仅更新对应三页业务源码摘要；同时补齐拉取基线a1ed137已有的TFrame状态栏文案源码摘要。原控件、事件、绑定和选择项保持。597项真实XAML布局/DPI检查及validate_contracts.py通过；点取首击和延迟清理由ProbeLocateCheck与SupportBindingCheck的真实工具替身检查验证，不能以本展示夹具替代宿主验收。

2026-10-15：A1/A2新增材料代码输入，默认C1，沿用34高ModelInput。597项检查增加两参数卡的字段默认/宽度边界，以及四种停靠尺寸和四档DPI；实际渲染已查看。契约仅增A1MaterialCodeText/A2MaterialCodeText和授权页面业务SHA，原控件/事件不放宽。这里仍使用空业务回调；编号、清单、ALIAS及偏好序列化由PipeClampCheck/PipeClampIsoCheck验证，宿主联动需实测。

2026-10-14：用户授权正式管夹原生ISO集成，仅更新PipeClampPage业务源码摘要，所有原控件/默认选项/绑定/事件契约保持；原生写入逻辑集中在会话与NativePipeSupport，不放入页面。当前551项布局/固定操作/分型/DPI检查通过，实际确认流程另由PipeClampIsoCheck验证。

2026-10-14：正式工作区改用Bentley原生停靠。检查工程调用真实NativePanelLayout隐藏重复窗口标题，保留63模块头/固定操作；新增400×560、400×600、520×720、400×1080与四档DPI检查，见[DockingCheck](../DockingCheck/README.md)。下方原400×880尺寸仍为视觉回归基准。


真实16份物理XAML覆盖17个入口：N3/N4共用BracketPage，Q1/Q2是一个已改入口。本轮新增15份物理页面的v4改造，Q1/Q2保留并一起验证。链接共享标题、主题、展示转换器；业务回调使用空夹具，不读写DGN、用户偏好或授权。

```powershell
dotnet run --project Development/SupportUiCheck/SupportUiCheck.csproj -c Release -- "E:/Code/Bentley_Python_plugin/型钢构件及支吊架模型生成工具_CS"
```

202项检查覆盖400×880、32+63头部、46底栏、确认初始可见、参数滚动不移动操作区、按钮右边界、管夹八个参数面板、立管两组参数、Q2类型4角度入口、N3/N4动态代号、四档DPI与兼容布局。previews保存所有入口与重点分型，数值和读数仅为展示夹具。

contracts.json保存4a79280改前控件/默认值/事件及业务源码校验。validate_contracts.py对照具名控件、选择项、绑定、原事件及原xaml.cs；领域/目录/服务/工具等另作Git内容对照。业务回归使用原PipeClampCheck（含L7/L8）、Q1SupportCheck、ElbowTrunnionCheck、G2AnchorCheck、VerticalPipeSupportCheck、E1GuideCheck、N1/N2、EquipmentSupportCheck（N3/N4/N8）、D2、Triangle、L、Portal、T、Pad等检查工程。

当前所有页的正式规格见 [UI规范-v4](../../Docs/UI规范-v4.md)。旧宽度说明只作为历史，不是当前新增页规则。本检查不等同OPM原生实体、点取、角度、滑动、取消、确认、EC写入或Undo实测。

2026-10-13：新增 U3 参数面板及长材料/子项文案预览；其他模块原 UI-only 契约快照保留；PipeClamp 仅源码摘要随用户授权的 U3 功能更新，原控件、事件、选择及绑定契约继续验证。

2026-10-13：按用户要求开放 N3 预焊件占位，新增独立开关与 D 输入。BracketPage 契约只更新授权变更的源码摘要并补充新字段，原 N4 字段与事件继续验证。当前209项布局检查含N3默认关闭、D随勾选启用、N3/N4参数分区和展开后的固定确认区；n3-preweld-enabled.png为展示夹具。EquipmentSupportCheck的92项检查覆盖扣长、编号、E边界、反向及配置兼容，宿主实体尚未实测。

2026-10-13：根据用户N3原图，将N3的H显示为两块连接板中心距，N4原标注保留。当前211项布局检查包含两个页面的H文案；EquipmentSupportCheck通过145项，新增N3上下两型的板中心、所有A～F最小H的20mm净距及45°斜撑检查，N4原定位继续回归。

2026-10-13：N4的H也统一为两块连接板中心距，替代上一条N4保留原标注的状态。BracketPage的默认H文案及业务源码摘要同步更新，211项UI检查通过；当前EquipmentSupportCheck通过2394项，包含N3/N4中心距、防碰撞及截面剪切回归。
