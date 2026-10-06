# 离线布局渲染

Stub.cs 使用无Bentley依赖的Form链接真实PipeAlignDialog.Layout.cs，提供示例行和空业务事件，仅用于检查480×960布局、卡片渲染及按钮是否溢出，不证明宿主功能正确。

用.NET Framework csc引用System.Drawing.dll和System.Windows.Forms.dll编译两个文件，隐藏启动UiLayoutCheck.exe，输出layout.png。启动不加载OpenPlant或读取/修改DGN。生成的截图使用示例数据。真实SDK停靠、150%/200% DPI、多选移除和锁Z自动预览仍需宿主验收。
