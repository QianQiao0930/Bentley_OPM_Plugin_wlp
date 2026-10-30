# 预览所有权故障回归

运行：`dotnet run --project Development/PreviewOwnershipCheck/PreviewOwnershipCheck.csproj -c Release`。

直接链接 EquipmentBracket、PadPlate、PortalFrame、LBracket、SteelHandrail、SquareManhole、TFrame、TriangleBracket 的真实预览会话与 `Tools/PreviewElementOwnership.cs`，用 Bentley 模型 API 和建模/统计替身注入故障。

覆盖构建、写入返回错误/异常、旧件删除失败、新件回收失败、多个残留后的更新和取消重试、取消继续清理其他件、失败后禁止确认、统计失败、外部删除、确认后取消保留正式件、D15 筋板编号与人孔成功写入耗时。

这些检查只验证真实会话状态和所有权流程，不能代替 OPM 内的实体、实际 DeleteFromModel、关闭重试和 Undo 验证。主工程必须排除本目录源码。
