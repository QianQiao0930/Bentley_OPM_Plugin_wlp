# 首页 v4 离线验证

2026-10-14：正式工作区改用Bentley原生停靠。检查工程调用真实NativePanelLayout隐藏重复窗口标题，保留63模块头/固定操作；新增400×560、400×600、520×720、400×1080与四档DPI检查，见[DockingCheck](../DockingCheck/README.md)。下方原400×880尺寸仍为视觉回归基准。


该检查工程链接真实 HomePage XAML、展示代码、现有功能清单、排序器和HomePreferences存储代码。Bentley宿主与授权状态使用隔离夹具。仅本检查工程定义HOME_UI_CHECK，把偏好文件放在可执行文件同目录isolated-home_preferences.json；不修改用户的home_preferences.json。

运行：

```powershell
dotnet run --project Development/HomeUiCheck/HomeUiCheck.csproj -c Release -- "E:/Code/Bentley_Python_plugin/型钢构件及支吊架模型生成工具_CS"
```

当前83项检查覆盖400×880外框、159头部、47统计带、131工具栏、46底栏、两种卡片密度、分类与编号搜索、真实32模块、查询分类三个入口与直线坐标搜索/导航、原1～5星菜单、星标不误进模块、模块导航事件、授权状态/无授权隐藏、排行显示、1/1.25/1.5/2倍DPI渲染，以及模块页兼容外边距/底栏恢复。新增四项界面选择真实写盘/清缓存重载、旧偏好兼容、未知模块记录保留、损坏/非法配置回落、全局最近列表唯一性、跨三类时间交叉排序、置顶开关、筛选/重置与导航检查。渲染图输出previews，含home-recent-compact/detail-400-880.png，作为UI对照材料，不是生产依赖。

本机prototype_capture.cjs用独立无界面Edge渲染仓库资料中的v4原型。原型图片中的示例模块、计数和魏字logo不能替代真实功能清单、真实偏好和既有SVG品牌图标。

OPM窗口首次打开、跨页面原生外框恢复、标题拖动和最小化仍需宿主检查；纯WPF渲染不等同宿主实测。


当前所有页面的统一规格见 [UI规范-v4](../../Docs/UI规范-v4.md)。文内旧宽度和布局恢复描述为测试夹具/历史阶段，不能据此把新页面改回560宽。
