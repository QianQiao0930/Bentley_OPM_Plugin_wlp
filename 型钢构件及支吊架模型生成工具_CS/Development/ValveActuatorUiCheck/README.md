# 阀门执行机构 CEL 选择界面离线检查

运行 `dotnet run --project Development/ValveActuatorUiCheck/ValveActuatorUiCheck.csproj -c Release`。

46 项检查链接真实 ActuatorCelAsset、ActuatorCelInstanceData、ActuatorControlLayout、ActuatorCelAssetReader 单位校核、页面代码与 XAML；覆盖调节柄范围/单位换算及扁平/细长/无效范围、快照深拷贝、两件资源互不覆盖、原文件缺失时从字节恢复、缓存/属性损坏及版本保护、空/超大文件、单位与原点限制、先选后放、放置期间锁定选择、预览失败可放、结束失败保留页面、读取失败清旧选择、离开关闭和四档 DPI 布局。图像输出到可执行文件旁 artifacts，仅显示离线夹具，不是实际 CEL 预览效果。

EC 属性容器、文件模型列表、预览和原生放置接口均用替身；不加载 OPM。宿主二进制持久化、原生调整/关联/随动/重生成/重开由用户按 [操作说明](../../Docs/阀门执行机构CEL选择界面.md) 验证。
