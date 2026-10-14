# 墙面爬梯迁移检查

运行 `dotnet run --project Development/WallLadderCheck/WallLadderCheck.csproj -c Release`。本检查不加载Bentley宿主、不写DGN。

`Development/export_wall_ladder_reference.py`以AST白名单抽取原`墙面爬梯/wall_ladder.py`的12个纯布局函数，生成16组`python_reference.json`；不导入MSPy、不调用原生建模或折线回退。对照短梯、250/300分段边界、4500/5500/6000选型边界、不同距墙/梯宽/离地/支架间距及护笼开关。

检查真实Calculator的立柱、横担、墙板坐标/尺寸、角钢外形基准、普通环/顶环完整路径、真圆弧起点/中点/终点、R355、11根竖杆的真实弧长站位和环间距。角钢在C#复用真实目录，替代原Python两矩形L；验证外包位置保持、目录含真圆角。

真实Builder链接记录式Bentley API替身：检查完整路径一次扫掠、圆弧类型未变成直线、1和1000 UOR/mm转换、放置点/90°旋转、竖直起始截面、两Cell及子构件均离线、失败重试仍为真圆弧、全失败明确报错、无护笼及二维拒绝。替身只记录调用，不模拟内核实体，也不能证明OPM扫掠与相并结果。

真实WallLadderPreviewSession链接模型API替身：覆盖双块确认、第二块写入失败回收第一块、回收失败保留所有权、旧块删除失败、部分清理、再次取消、参数失效、护笼切换及外部删除。实际WallLadderPage/Calculator/PreviewSession还由ModelingUiCheck验证参数黑点/确认失效、失败保留旧块、护笼开关、延迟回调取消、退出及重复关闭。

当前12372项尺寸/路径/建模调用/所有权检查通过，ModelingUiCheck的十一页144项展示和爬梯状态检查通过，HomeCheck回归通过。

宿主待验证：R355圆头、顶部空间倒L路径的截面方向和整条扫掠、真实角钢圆角、参考附件/活动模型单位、AccuSnap恢复、原生预览写入/删除、确认与Undo。圆弧失败不得增加分段块或多段线作为回退。
