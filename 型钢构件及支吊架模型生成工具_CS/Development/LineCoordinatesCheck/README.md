# 直线坐标修改离线回归

```powershell
dotnet run --project Development/LineCoordinatesCheck/LineCoordinatesCheck.csproj -c Release
```

93 项检查链接真实 Domain、Calculator、LinePipeAlign、Reader、Editor 与 LocatedElement；NativeApiFakes 隔离模型与事务，不加载 Bentley 或访问用户 DGN。检查六轴坐标及 UOR/毫米往返、G17 精度、未编辑轴保留原UOR、二维限制、有限数值和非零长度、只读/锁定/参考/子元素拒绝、模型与单位变化、外部编辑冲突、保留 ID 和附加属性、单次写入的事务边界、几何/写入/回读失败回退；另含快速对齐纯计算：四个正交规整的锚点规则、方向容差（分量≤线长×1e-6）边界、管底标高（轴线低端−外径/2）、水平线贴 Floor(管底)、竖直线移到点取位置且终点贴管底、斜线/立管/缺外径/二维/零长/无效点取拒绝。

页面状态、延迟回调、草稿不自动写入、撤销失效、四档 DPI 与固定操作区由 `Development/ToolPagesUiCheck` 验证；首页入口及分类由 HomeCheck/HomeUiCheck 验证。

宿主试用：画一条普通直线，核对属性中的两端坐标与本页毫米值，分别改起点/终点的各轴，检查图层/颜色/线型/EC/ID；用 OPM 撤销及重做；点取后外部改线/删除/切换模型再应用应拒绝。确认折线、复杂链、块内线、参考、只读和锁定元素不会修改；验证二维 Z、不同模型单位、捕捉恢复、离开/关闭及重复开始点取。离线 API 替身不能证明原生 ReplaceInModel、视图刷新和宿主 Undo 已实测。
