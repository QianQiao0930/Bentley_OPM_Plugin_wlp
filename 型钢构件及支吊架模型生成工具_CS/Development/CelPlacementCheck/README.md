# CEL 放置与统计检查

`dotnet run --project Development/CelPlacementCheck/CelPlacementCheck.csproj -c Release`

链接真实 Tool、Writer、ItemType Store、统计计算和导出，45 断言使用宿主替身检查：一键连续放置、动态缓存不写模型、重复开始清空选择且复用工具、附加项写入/重读失败整件回退、Add 后身份读取异常仍执行回滚、回滚失败明确报告、只读/授权保护、暂态删除失败保留并重试、结束事件仅一次、活动模型与全部根模型、复制/删除/嵌套统计边界和 CSV 输出。

主工程包含这些源文件并检查完整 WPF 集成。替身事务和暂态不能替代 OPM 的原生 Undo/Redo、保存重开及鼠标显示验收。

2026-10-30新增：原COM IsNew仍true、原包装ID为0但新根已落地、末尾旧件不可冒充新放置。SDK编译与替身只证明相应控制流，不能替代真实COM宿主验收。

连续放置新增：每次提交在EndDynamics后的普通显示阶段刷新视图，再恢复BeginDynamics；右键之前可见数量应已更新，刷新失败不得回滚已提交单元及附加项。
