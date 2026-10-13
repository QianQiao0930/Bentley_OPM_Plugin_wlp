# Q1 / Q2 原型界面检查

链接生产页面 Q1SupportPage.xaml、局部主题、展示转换器和新增数值步进事件。隔离夹具只提供选型文本和页面状态，不加载 Bentley、用户偏好或真实点取工具。

运行：

```powershell
dotnet run --project Development/QSupportUiCheck/QSupportUiCheck.csproj -c Release -- "E:/Code/Bentley_Python_plugin/型钢构件及支吊架模型生成工具_CS"
```

37 项检查覆盖 400×880 外框、63 模块头、302 固定操作区、46 底栏、原具名控件、参数滚动不移动操作区、数值步进、Q2 类型4角度入口、1/1.25/1.5/2倍 DPI，以及其他模块恢复原外边距和底栏。previews 输出 Q1 初始/选型结果/镜像及 Q2 类型4界面。夹具数据仅用于展示。

Q1SupportCheck 独立运行真实领域与计算源码的 16976 项回归。业务页面原 Q1SupportPage.xaml.cs 保持改造前内容；原控件名、参数事件与业务按钮处理函数另作源码对照。宿主内真实点取、角度、滑动、取消、生成和原生窗口切换需要 OPM 实测，离线截图不代表该实测完成。
