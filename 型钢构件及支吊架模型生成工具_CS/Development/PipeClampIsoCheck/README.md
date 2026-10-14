# 管夹正式模块原生ISO集成检查

运行 `dotnet run --project Development/PipeClampIsoCheck/PipeClampIsoCheck.csproj -c Release`。

链接真实PipeClampPreviewSession、PipeClampTransientPreview、共用原生Writer/Data/Elements/Source、JSON记录存储、定义与原领域/目录/计算。原生图形桥、COM、模型、事务和各Builder/Statistics采用隔离替身；真实SDK签名及unsafe桥由主工程编译检查。共用API替身位于A1NativeSupportCheck/NativeApiFakes.cs，其他九类Builder与材料替身在ExtraFakes.cs。

6484项覆盖九类别×三档UOR×三种Schema坐标单位×三个方向配置、非零标高、正确局部化再放置、SUPPORT_LOCATION字符串DN、双材料记录、Design/SHOP、父管、暂态预览、普通/参考分支、源轴/单位/模型/身份变化、16种确认故障及回滚、暂态更新/清理失败、失败重试、撤销不复活普通预览。增加ALIAS严格等于原材料AssemblyTag（包括无连字符、度数、长号与用户E1-B-107示例），原生NAME按CODE/NUMBER重算后不影响显示；重复同编号的两件保留独立原生身份，ALIAS/标记保存丢失及重读丢失必须回滚。组合中的方向仍遵循类别范围：U3立管、E1/K1水平，其余包含斜向。

运行 `powershell -NoProfile -ExecutionPolicy Bypass -File Development/PipeClampIsoCheck/Check-IsoTagMapping.ps1`，16项验证真实部署脚本的只读预览、备份字节一致、SHA256/重复幂等、原生回落、其他类/BOM描述不变、已有类属性保留、类缺失增量创建、已有项目映射冲突拒绝及错误Schema拒绝。夹具隔离在检查工程obj目录，不改实际工作集。该检查不执行ISO表达式。

Builder替身只提供可测采样点，不能证明真实扫掠/相并；COM替身不能证明容器显示与图形复制；事务替身不能证明原生Undo/Redo。逐类宿主验证见[接入说明](../../Docs/原生支吊架与轴测图接入.md)。
