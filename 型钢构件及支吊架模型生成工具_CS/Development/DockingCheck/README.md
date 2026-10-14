# Bentley 原生停靠检查

运行：`dotnet run --project Development/DockingCheck/DockingCheck.csproj -c Release`。

链接真实 MainWindow、WorkspaceView、SteelSectionAddIn、IWorkspacePage 和 NativePanelLayout。Bentley Adapter/WindowManager 与业务页为隔离替身；使用真实 WinForms/WPF 宿主及工作区导航代码。

58 项检查覆盖：稳定面板标识、默认右停靠、左右/标签/自动隐藏能力、重复打开只注册一次、页面切换不改宿主尺寸、自动隐藏不触发取消、底部关闭及原生关闭清理、关闭后重开复用、清理失败阻止关闭、隐藏期间授权到期拦截、宿主销毁清理全部页面、插件卸载清除面板注册、失败拒绝卸载且保留授权到期检查及重复释放。

LayoutChecks.cs 由五个 UI 检查工程共享，检查真实页面在400×560、400×600、520×720、400×1080及1/1.25/1.5/2倍DPI下的底栏与确认操作；最小高度下参数区缩短并保持滚动。各检查工程调用真实NativePanelLayout，以覆盖进入工作区时隐藏自绘窗口标题栏的行为。

本次结果：DockingCheck 58项、HomeUiCheck 83项、ModelingUiCheck 406项、SupportUiCheck 551项、ToolPagesUiCheck 188项、QSupportUiCheck 57项及HomeCheck全部通过；支吊架控件/事件/业务源码契约守卫通过。授权/无授权Release均零警告零错误，常规和备用DLL/PDB保持一致。

OPM中仍须验证：拖到左/右及其他面板标签组、浮动/图钉自动隐藏、不同显示器DPI、点取期间自动收起不取消、原生X/底栏关闭取消未确认预览、重新打开与卸载重载。稳定ID交给Bentley管理布局；跨次启动的停靠区域及标签恢复必须在宿主实际工作区中确认，不自行加载/覆盖整个Bentley布局文件。
