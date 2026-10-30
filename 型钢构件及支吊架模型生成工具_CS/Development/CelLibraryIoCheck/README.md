# CEL 库读取与离线几何检查

`dotnet run --project Development/CelLibraryIoCheck/CelLibraryIoCheck.csproj -c Release`

链接真实 Reader、Geometry 和领域快照，宿主接口使用替身。18 场景、38 断言覆盖只读打开/关闭、三维可放置筛选、重名/单位/源原点错误、原活动文件保留、原附加库及原未附库状态恢复、部分附加失败、恢复失败、插入点 UOR 到主单位换算、TrueScale 仅启用一次及世界 Z 旋转矩阵。

检查使用临时假 CEL，不读取真实二进制几何，不证明 Bentley 中的导入、单位、原点或实体效果已实测。
