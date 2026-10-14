# N3/N4/N8 设备支架回归

```powershell
dotnet run --project Development/EquipmentSupportCheck/EquipmentSupportCheck.csproj -c Release
```

6426 项检查覆盖真实参数/板中心距/板边净距、截面目录、斜撑两端剪切延长量及布置方向。

`ChannelOrientationChecks` 链接真实 `BracketBuilder` 与 `profiles.bin`，通过 `BuilderApiFakes` 记录扫掠参数；覆盖 N3/N4、A～F、类型1/2、辅助线反向、预焊占位开关、0/30/90/180度辅助线的384组组合。检查N4子项A/B横担和斜撑的槽钢腹板朝内、开口向外，真实截面圆角保留；同时核对N3与H型钢原方向、两侧中心间距、纵向长度、斜撑轴线和剪切流程、构件C方向及搭接长度。

替身记录调用，不执行Bentley原生布尔、扫掠或写入。OPM中仍需试放N4的A/B、上下两型及反向状态，核对开口、端面剪切、连接筋板、更新/取消/确认与Undo。旧模型不会自动变更，需重新生成；未确认预览使用“更新预览”重建。
