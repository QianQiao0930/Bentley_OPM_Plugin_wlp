# 磁翻板液位计检查

运行 `dotnet run --project Development/MagneticGaugeCheck/MagneticGaugeCheck.csproj -c Release`，当前67447项检查通过。

`Development/export_magnetic_gauge_reference.py`只以AST白名单读取原`磁翻板液位计/magnetic_level_gauge.py`的layout函数与四种RGB常量；不导入MSPy/Qt、不执行任何建模。11组参考覆盖350/6000范围端点、24mm翻片数量跃迁、10mm刻度数量边界、1400默认和非整数L1。

逐一对照原版全部构件的类型、起点/终点、尺寸、半径、RGB和顺序；检查翻片偶数/严格50%红白分界、片间余量、刻度、两个真圆环手轮、参数快照和非法输入。

真实Builder链接记录式模型API替身：覆盖350/1400/6000及1/1000 UOR/mm，全部子构件离线、整台单Cell、原点/90°旋转、精确RGB、箱体顶点/拉伸方向、圆柱轴线/半径、手轮完整2π圆环及平面；构件生成/颜色失败明确报错，二维、坐标和模型单位拒绝。替身不模拟Bentley几何内核，不证明宿主实体成功。

真实PreviewSession使用API替身检查确认、失效、写入失败、旧块删除失败、回收失败保留所有权、重试清理及外部删除。ModelingUiCheck还链接实际GaugePage/Calculator/PreviewSession，覆盖预览状态、L1越界、失败保留、取消/退出队列守卫、重复关闭及四档DPI。

OPM待验证：环形手轮镂空与轮辐、四种颜色、非毫米主单位、定位/捕捉恢复、预览更新/取消、确认后连续放置、普通Cell整体操作和Undo。模型是原版外观简化，非制造模型或智能仪表；没有模型文字，未来文字必须走ModelTextFactory。
