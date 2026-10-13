# 查询、激活、作者页面 UI 检查

本工程编译真实四页 XAML、PrototypeChrome 和 PrototypeTheme。作者/激活页直接链接原页面逻辑，授权服务与宿主使用隔离夹具；查询页事件使用空夹具，不读取真实 DGN、授权文件、用户偏好或发送邮件。

```powershell
dotnet run --project Development/ToolPagesUiCheck/ToolPagesUiCheck.csproj -c Release -- "E:/Code/Bentley_Python_plugin/型钢构件及支吊架模型生成工具_CS"
```

52 项检查包含四页 400×880 外框、32+63 模块头、46 底栏、10.5 字体/14 行高/最多两行的长状态文字、按钮右边界、全部查询/统计列、四档 DPI、原激活页离开时清理输入、无授权版隐藏作者页授权卡片、未改模块恢复原布局。截图在 previews，数值均为展示夹具。

查询读取、统计汇总/JSON/三表 Excel 和授权验证另由 ComponentPropertiesCheck、SupportStatisticsCheck、LicenseCheck 真实源码回归。四页原 xaml.cs 保持改前82a7771内容；控件名、参数事件、业务按钮、数据列及绑定已对照。本检查不能替代 OPM 真实点取、导出、授权导入、邮件客户端及原生窗口交互测试。
