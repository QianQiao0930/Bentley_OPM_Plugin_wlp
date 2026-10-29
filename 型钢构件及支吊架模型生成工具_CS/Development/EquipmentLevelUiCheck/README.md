# 设备图层与颜色页面检查

此工程编译正式 EquipmentLevelPage 的 XAML 和代码、共享主题/Chrome、NativePanelLayout、页面契约与领域选项。文档、设备和模型写入服务采用隔离替身；不加载 OPM、不读写用户模型。

构建：`dotnet build Development/EquipmentLevelUiCheck/EquipmentLevelUiCheck.csproj -c Release`。

运行生成的 `bin/Release/net48/EquipmentLevelUiCheck.exe [截图输出目录]`。若源码目录是网络映射盘，应将编译目录复制到本机目录再运行，以避免 .NET Framework 的远程程序集加载限制。

覆盖默认活动层、设备/拒绝数量、三种颜色选项、无效 RGB、进度与计时文字、忙时控件禁用/拒绝离开、成功/失败结果、Undo/模型切换失效及重新读取。真实页面在400×560/600/880/1080和520×720布局，检查固定应用区、滚动独立、目标层显示和1/1.25/1.5/2倍DPI并导出PNG。

业务另运行 EquipmentLevelCheck（真实服务/图层读取配宿主API替身）。本检查不能证明真实COM持久化、原生色板交互、长任务宿主响应、保存重开或撤销/重做已验收。
