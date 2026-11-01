# Bentley OPM 插件集合

本仓库包含两个分别维护的版本，源码按版本集中存放。Git 仓库仍保留在当前根目录。

| 版本 | 入口 | 运行环境 |
| --- | --- | --- |
| Python | [型钢构件及支吊架模型生成工具_Python/README.md](型钢构件及支吊架模型生成工具_Python/README.md) | Bentley MSPython / Power Platform Python |
| C# | [型钢构件及支吊架模型生成工具_CS/README.md](型钢构件及支吊架模型生成工具_CS/README.md) | .NET Framework 4.8、OpenPlant Modeler 2024 |

## 目录结构

```text
Bentley_Python_plugin/
├── 型钢构件及支吊架模型生成工具_CS/       # 原目录、工程和部署路径保留
├── 型钢构件及支吊架模型生成工具_Python/   # Python 入口、共享库、旧脚本及分发说明
├── 资料/                                   # 保留 C# 工程引用的 CEL 等资料
├── 迁移备份/                               # 两个版本的本地历史备份，不入库
├── 型钢构件及支吊架模型生成工具.code-workspace
├── .gitignore
└── README.md
```

打开根目录的 `.code-workspace` 可以同时查看两个版本。仅开发某个版本时，也可以直接打开相应目录。

## Python 版

原根目录下的 22 个 Python 功能及共享库目录整体归入 [型钢构件及支吊架模型生成工具_Python](型钢构件及支吊架模型生成工具_Python)，包括 `bentley_ui`、`型钢截面生成器`、`管道信息查询`、`管道支吊架` 等。内部目录结构与源码保持原样，公共库和功能目录继续同级。

- 使用方法与模块说明：[Python README](型钢构件及支吊架模型生成工具_Python/README.md)。
- 打包：从 Python 版根目录执行 [分发打包说明](型钢构件及支吊架模型生成工具_Python/分发打包说明.md) 中的命令。
- 现有两个分发 ZIP 和 `.ruff_cache` 随 Python 目录迁移，仍由原有忽略规则管理。
- OPM Python Project 或快捷方式若保存旧入口的绝对路径，需要重新选择迁移后的脚本；本次未修改仓库外的配置。

## C# 版与保留资料

C# 工程的位置、源码、资源、部署和加载路径保留。工程内的 Python 规格导出及 Schema 工具属于 C# 开发流程，继续留在原处。

`SteelSupportModeler.csproj` 引用 `../资料/地面冲洗水盘管.cel`，因此 [资料](资料) 保留在根目录。根目录 `迁移备份` 混有两个版本的历史快照，也保留原位。原根目录 `管道对齐` 历史文档已移除；管道标高对齐功能继续由 C# 工程维护。

根目录 `.workbuddy` 为已有协作笔记；`Directory` 和 `HKEY_CLASSES_ROOT` 为已有误生成目录。本次保留这些本地内容，未进行删除清理。

## 两个版本的数据互通

两个版本共用 DGN 中的 `PipeSupportComponents` ItemType 数据契约；修改属性字段或统计口径时，需要核对两侧实现。这属于数据兼容约定，两个源码目录无需互相导入。

## 整理基线

2026-11-01 整理前已提交基线：`ab743954b2d03e1737df65c4ebfeb3c7edbd68c7`（`chore: snapshot baseline before Python directory reorganization`）。

本次只整理目录、说明文档、忽略规则和工作区入口，不拆分 Git 历史、不修改业务实现。已有忽略文件不在基线提交范围；本次随目录移动的本地文件另做 SHA-256 校验。

## License

仅用于项目内部，版权归作者所有。
