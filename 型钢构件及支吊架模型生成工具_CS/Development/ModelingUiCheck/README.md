# 九个建模模块的原型界面检查

链接真实九页 XAML、局部 ModelingTheme、PrototypeChrome、原 ProfilePreviewControl 与 ProfileModels。事件回调使用隔离空夹具，选型和统计数值仅用于渲染，不运行 Bentley 工具、不写模型、授权或用户偏好。

```powershell
dotnet run --project Development/ModelingUiCheck/ModelingUiCheck.csproj -c Release -- "E:/Code/Bentley_Python_plugin/型钢构件及支吊架模型生成工具_CS"
```

100 项检查覆盖 400×880 外框、32+63 标题、46 共用底栏、确认入口初始可见、参数滚动不带走操作按钮、按钮不超右边界、两个消防统计页签与全部五列、四档 DPI、对齐页原隐藏 SingleScope 和未改支吊架恢复原布局。previews 保存九页、参数滚动至底部和消防统计页签截图，均使用展示夹具。

contracts.json 保存改前114e0d9的原具名控件、默认值、状态与事件处理函数。已对照所有原选项、表列与绑定，并核对九页原 xaml.cs 内容不变。实际业务检查另运行 SteelHandrailCheck、SpiralStairCheck、PipeAlignmentCheck/UndoCheck、TankManholeCheck、NozzleCheck、SquareManholeCheck、FireCabinetCheck 和 HoseCabinetCheck。

本检查不代表 OPM 实际点取、预览、取消、确认、模型实体、EC 写入或原生窗口切换已测试；这些仍需宿主试放确认。


当前所有页面的统一规格见 [UI规范-v4](../../Docs/UI规范-v4.md)。文内旧宽度和布局恢复描述为测试夹具/历史阶段，不能据此把新页面改回560宽。
