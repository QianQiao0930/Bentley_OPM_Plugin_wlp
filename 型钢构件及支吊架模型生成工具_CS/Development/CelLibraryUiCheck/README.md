# CEL 页面及预览生命周期检查

`dotnet run --project Development/CelLibraryUiCheck/CelLibraryUiCheck.csproj -c Release -- Development/CelLibraryUiCheck/previews`

编译真实页面 XAML、页面代码和GetPicture预览包装，链接真实放置/统计服务，Bentley API 和 CEL 工厂使用替身。92 断言覆盖单元数量/名称、读取忙状态、角度校验、放置与数量展示、Undo 失效、关闭清理失败重试、读取/几何失败、关闭图像背景、仅预览副本等轴变换、实际像素白底与居中、等比缩放，以及多尺寸/四档 DPI 的固定预览与底部按钮。

包含实际停靠最小外框扣除共享底栏后的 398×512 页面空间，另有400×560/600/880和520×720。截图中预览区域明确标为离线检查，不绘制虚构盘管。预览现为WPF图像，离线以合成图形验证裁切、背景、居中和比例；真正CEL的GetPicture渲染必须进入OPM核对。

方向失败保留旧图且放置仍可继续，真实几何工厂失败仍阻止安装工具。x64检查另用Windows OleCreatePictureIndirect创建自有真实EMF图片，经生产IPicture.Render桥接重复读取24次并释放每次自有位图，验证白底和可重复借用；这项使用真实Windows OLE/GDI，但未加载Bentley宿主。接口/PICTDESC布局按Microsoft ocidl.h/olectl.h文档核对。
