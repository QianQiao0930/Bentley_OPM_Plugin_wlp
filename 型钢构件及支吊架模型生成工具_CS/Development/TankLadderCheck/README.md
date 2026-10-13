# 水箱爬梯离线检查

```powershell
python Development/export_tank_ladder_reference.py
dotnet run --project Development/TankLadderCheck/TankLadderCheck.csproj -c Release
```

生成器只提取原 `水箱爬梯/ladder_lib.py` 已审阅的布局函数，用记录替身代替MSPy模型操作。12组Python参考覆盖高度90～5000、数量边界、不同顶部净距和加强撑间距；运行时C#不读取或启动Python。

1208项检查覆盖梯腿起点、圆角两端及R150中间点、梯腿底端、镜像、角钢/踏步/支撑坐标及数量、独立参数快照、共享真实角钢目录、非法/非有限值与数量上限。链接实际TankLadderPreviewSession并使用API替身检查确认保留、参数失效、替换/写入失败、删除失败与所有权重试。

ModelingUiCheck链接实际TankLadderPage.xaml.cs及纯Calculator/PreviewSession，用隔离的模型API与内存偏好替身检查参数变化、更新失败/成功、确认/取消、延迟点取取消、退出及重复关闭。全部十页共121项WPF布局/状态检查通过。

这些检查不验证Bentley原生扫掠/相并、模型显示、AccuSnap或真实Undo。OPM中需检查旋转和不同模型单位、两种相并选项、确认/右键/离开页面及回退清理。
