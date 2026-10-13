# 支吊架 v4 UI 检查

真实16份物理XAML覆盖17个入口：N3/N4共用BracketPage，Q1/Q2是一个已改入口。本轮新增15份物理页面的v4改造，Q1/Q2保留并一起验证。链接共享标题、主题、展示转换器；业务回调使用空夹具，不读写DGN、用户偏好或授权。

```powershell
dotnet run --project Development/SupportUiCheck/SupportUiCheck.csproj -c Release -- "E:/Code/Bentley_Python_plugin/型钢构件及支吊架模型生成工具_CS"
```

202项检查覆盖400×880、32+63头部、46底栏、确认初始可见、参数滚动不移动操作区、按钮右边界、管夹八个参数面板、立管两组参数、Q2类型4角度入口、N3/N4动态代号、四档DPI与兼容布局。previews保存所有入口与重点分型，数值和读数仅为展示夹具。

contracts.json保存4a79280改前控件/默认值/事件及业务源码校验。validate_contracts.py对照具名控件、选择项、绑定、原事件及原xaml.cs；领域/目录/服务/工具等另作Git内容对照。业务回归使用原PipeClampCheck（含L7/L8）、Q1SupportCheck、ElbowTrunnionCheck、G2AnchorCheck、VerticalPipeSupportCheck、E1GuideCheck、N1/N2、EquipmentSupportCheck（N3/N4/N8）、D2、Triangle、L、Portal、T、Pad等检查工程。

当前所有页的正式规格见 [UI规范-v4](../../Docs/UI规范-v4.md)。旧宽度说明只作为历史，不是当前新增页规则。本检查不等同OPM原生实体、点取、角度、滑动、取消、确认、EC写入或Undo实测。
