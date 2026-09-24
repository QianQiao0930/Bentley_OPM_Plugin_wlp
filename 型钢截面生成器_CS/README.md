# 型钢截面生成器：OpenPlant Modeler 2024 C# 版

独立 .NET Framework 4.8 / x64 AddIn。Python 项目保持原样。本插件运行时只加载 C# DLL，不启动 Python。

## 已实现

- 7 类型钢，1144 个规格：平行腿槽钢、普通热轧工字钢、热轧 H 型钢、斜腿槽钢、等边角钢、不等边角钢、HK 系列 H 型钢。
- 与 Python 版相同的各类型钢插入基准、直线和真圆弧轮廓。`profiles.bin` 由 `export_profiles.py` 在开发时从原 Python 数据和纯几何模块生成，嵌入 DLL。
- 模型中连续点取放置二维闭合截面，动态预览，AccuSnap 与 AccuDraw 精确点取。COM 点位从主单位换算到 DGN UOR。
- 在三维模型中选开放路径（直线、折线、复合链、圆弧、样条），在路径起点构造垂直于切线的截面并扫掠成 SmartSolid。路径接近竖直时使用世界 Y 轴作为朝向参考。
- 扫掠实体先作为预览写入模型；更改类型、规格、基准或旋转角会重建。点击“确定扫掠”保留实体并附加 `PipeSupportComponents` 公共 ItemType；点击“取消预览”删除。可在确认时删除原路径。
- 参数列表显示当前规格数据。

## 编译

```powershell
dotnet build SteelSectionProbe.csproj -c Release
```

项目默认引用 `C:\Program Files\Bentley\OpenPlant 2024\OpenPlantModeler` 的 SDK 程序集。如安装位置不同，指定 `/p:BentleyRoot="安装目录"`。输出位于 `bin\Release\net48`。

修改 Python 版数据或几何后，在包含 `steel_sections` 的原项目旁运行 `python export_profiles.py`，再重新编译。此步骤仅用于开发，不是插件运行依赖。

## OPM 中使用

将 DLL 输出目录加入 `MS_ADDINPATH`。**目前旧 DLL 被运行中的 OPM 占用**，新版已另存于 `bin\Release\net48_full\SteelSectionProbe.dll`。退出所有 OPM 窗口后，在本目录执行：

```powershell
.\install_new_version.ps1
```

该脚本把新版复制到原来的 `bin\Release\net48` 位置并核对 SHA256。然后重启 OPM，输入：

```text
MDL LOAD SteelSectionProbe
STEELPROBE SHOW
```

在窗口中选类型、规格、插入基准。点“在视图中放置截面”后移动鼠标查看预览，以 AccuSnap 或 AccuDraw 指定位置并单击。可继续放置，右键 Reset 结束。

扫掠时先点“选取路径并扫掠”，再点选一条开放路径。检查预览、调整参数后点“确定扫掠”。若不保留，点“取消预览”。也可用 `STEELPROBE PLACE` 打开窗口并立即开始二维截面点取。

## 验证状态

已对 OPM 2024 SDK 程序集编译（0 警告、0 错误），并验证嵌入数据可读出 7 个类型与 1144 个规格。完整七类型钢放置、路径扫掠和 ItemType 附加仍需在 OPM 界面实测。
