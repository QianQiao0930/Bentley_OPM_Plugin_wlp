# 管道对齐（PipeAlign）

按一根**基准管**的标高，把一批**目标管**的管底 / 管中心 / 管顶对齐过去。OpenPlant Modeler 2024 的独立 C# AddIn。

最新版本支持连通组整体移动及锁 Z 轴移动（水平管随动、立管伸缩、远端固定），并改为自动预览、成功状态栏反馈。详见 [本次更新与实机验证说明](锁Z移动与撤销修复_2026-10-04.md)。

```text
管道对齐/
├─ 管道对齐插件开发指南.md        需求与开发规范（本插件的唯一需求来源）
├─ PipeAlign_CS/                  ★ 插件工程
│   ├─ README.md                  使用、架构、验证状态（先读这个）
│   ├─ AGENTS.md                  接续开发必读的协作规范
│   └─ Domain/ Data/ Services/ OpenPlant/ Tools/ UI/ App/ Registration/ Infrastructure/
└─ Development/                   开发期工具（不参与主工程编译）
    ├─ ApiDump/                   只读元数据转储：查 Bentley 程序集的真实签名
    ├─ ApiProbe/                  API 可用性探针：C# 到底能消费哪些成员
    └─ PipeAlignCheck/            纯计算自检：覆盖指南 §34 算例与 T01～T20
```

## 常用命令

```powershell
# 编译插件
dotnet build 管道对齐\PipeAlign_CS\PipeAlign.csproj -c Release

# 纯计算自检（不需要装 OPM）
dotnet run --project 管道对齐\Development\PipeAlignCheck\PipeAlignCheck.csproj -c Release

# 在 OPM 里：先 MDL LOAD PipeAlign，然后
#   PIPEALIGN                     打开窗口
#   PIPEALIGN BOTTOM|CENTER|TOP   指定对齐模式
#   PIPEALIGN DEBUG [DUMP]        只读打印选中管道的调试数据
#   PIPEALIGN OPTIONS             把运行参数写回配置
```

## 三条先知道再动手的事

1. **选择符合意图的移动模式。** 单管安全模式会拒绝影响未选中的连接对象；连通组模式整体平移；锁 Z 模式让水平段随动、立管伸缩。连接未知时拒绝移动并显示原因。
2. **探测不通过时插件会拒绝移动，这是有意的。** OpenPlant 几何接口的坐标单位没有官方保证，插件坚持只用"在该元素上用其自身几何证实过"的单位；证实不了就拒绝，而不是猜。
3. **移动是否真的生效尚未在 OPM 实测。** 详细判据见 [`PipeAlign_CS/README.md`](PipeAlign_CS/README.md) 第 9 节。

详细说明：[`PipeAlign_CS/README.md`](PipeAlign_CS/README.md)｜协作规范：[`PipeAlign_CS/AGENTS.md`](PipeAlign_CS/AGENTS.md)｜需求来源：[`管道对齐插件开发指南.md`](管道对齐插件开发指南.md)
