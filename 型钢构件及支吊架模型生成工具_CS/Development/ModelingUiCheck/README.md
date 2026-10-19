# 十二个建模模块的原型界面检查

2026-10-17：墙面爬梯五个数值填写框改为等宽双列，护笼勾选保持整行。现有406项布局/停靠尺寸/DPI/状态检查通过，并检查wall-ladder-400-880.png确认同行输入对齐；WallLadderCheck 12372项回归通过。未增加业务字段或修改事件。

2026-10-14：正式工作区改用Bentley原生停靠。检查工程调用真实NativePanelLayout隐藏重复窗口标题，保留63模块头/固定操作；新增400×560、400×600、520×720、400×1080与四档DPI检查，见[DockingCheck](../DockingCheck/README.md)。下方原400×880尺寸仍为视觉回归基准。


链接真实十二页XAML、局部ModelingTheme、PrototypeChrome、原ProfilePreviewControl与ProfileModels。原九页事件使用隔离空夹具；新增水箱爬梯、墙面爬梯、磁翻板液位计链接真实页面逻辑及纯Calculator/PreviewSession，用隔离模型API和内存偏好替身验证状态。不运行Bentley原生几何、不写实际模型、授权或用户偏好。

```powershell
dotnet run --project Development/ModelingUiCheck/ModelingUiCheck.csproj -c Release -- "E:/Code/Bentley_Python_plugin/型钢构件及支吊架模型生成工具_CS"
```

166项检查覆盖400×880外框、32+63标题、46共用底栏、确认入口初始可见、参数滚动与固定操作区、按钮边界、消防统计页签/五列、四档DPI及原兼容布局；还覆盖两种爬梯与磁翻板的参数失效、更新失败/成功、确认/取消、延迟点取取消、退出及重复关闭，以及墙面爬梯线高读取/非法线拒绝/护笼开关和磁翻板L1越界。previews保存十二页及参数滚动至底部截图。

contracts.json 保存改前114e0d9的原具名控件、默认值、状态与事件处理函数。已对照所有原选项、表列与绑定，并核对九页原 xaml.cs 内容不变。实际业务检查另运行 SteelHandrailCheck、SpiralStairCheck、PipeAlignmentCheck/UndoCheck、TankManholeCheck、NozzleCheck、SquareManholeCheck、FireCabinetCheck 和 HoseCabinetCheck。

本检查不代表 OPM 实际点取、预览、取消、确认、模型实体、EC 写入或原生窗口切换已测试；这些仍需宿主试放确认。


当前所有页面的统一规格见 [UI规范-v4](../../Docs/UI规范-v4.md)。文内旧宽度和布局恢复描述为测试夹具/历史阶段，不能据此把新页面改回560宽。
