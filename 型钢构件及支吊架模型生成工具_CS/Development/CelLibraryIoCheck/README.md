# CEL 库读取与离线几何检查

`dotnet run --project Development/CelLibraryIoCheck/CelLibraryIoCheck.csproj -c Release`

链接正式 CEL Reader、Geometry 和领域模型，宿主接口使用替身。18 场景、38 断言覆盖只读打开/关闭、三维可放置筛选、重名/单位/源原点错误、原活动文件保留、原附加库及原未附库状态恢复、部分附加失败、恢复失败、插入点 UOR 到主单位换算、TrueScale 仅启用一次、世界 Z 旋转矩阵，以及目标模型、线程与输入校验。

2026-11-01 按用户要求清理已停止的原生 CEL 固化 N 系列：移除该系列的测试源码引用和专用用例，保留正式 CEL 库功能的回归检查。

检查使用临时假 CEL，不读取真实二进制几何，不证明 Bentley 中的导入、单位、原点或实体效果已实测。
