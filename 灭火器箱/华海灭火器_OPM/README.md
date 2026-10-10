# 华海灭火器 OPM Python 插件

入口：`huahai_opm.py`。在 OPM 中选择 2、4、5、6、8 kg 规格，可点选位置生成三维灭火器命名单元，并导出单个或全部规格的 Bentley V8 `.cel` 单元库。

## 使用

1. 在支持 Bentley MSPy Python 的 OpenPlant Modeler 中打开可编辑的 **三维 DGN**。
2. 打开 **Python Manager / Python 管理器**，添加并运行本目录的 `huahai_opm.py`。
3. 选择灭火器规格，输入绕 Z 轴的旋转角度，点击 **点选位置并建模**。
4. 对话框关闭后，在模型中点取灭火器底部中心。可连续放置；右键结束。各部件组合为一个命名单元，可整体选中、移动和复制。
5. 需要单元库时，重新运行入口，点击 **导出此规格 CEL** 或 **导出全部规格 CEL**，选择新的 `.cel` 文件名。导出完成后，可在 OPM 的单元库界面附加该文件，按单元名称放置。

旋转角度只作用于当前模型的点选放置；CEL 中各单元统一使用零角度、底部中心为原点。X、Y 为水平面，Z 向上，标签与压力表朝 −Y。

## 五种规格

| 容量 | 型号 | 筒径 / mm | 总高 / mm | 喷射配置 | 单元名称 |
|---|---|---:|---:|---|---|
| 2 kg | MF/ABCE2 | 110 | 360 | 直喷嘴，无软管 | HUAHAI_MF_ABCE2 |
| 4 kg | MF/ABCE4 | 130 | 485 | 400 mm 软管，外径 18 mm | HUAHAI_MF_ABCE4 |
| 5 kg | MF/ABCE5 | 140 | 535 | 同上 | HUAHAI_MF_ABCE5 |
| 6 kg | MF/ABCE6 | 150 | 575 | 同上 | HUAHAI_MF_ABCE6 |
| 8 kg | MF/ABCE8 | 160 | 605 | 同上 | HUAHAI_MF_ABCE8 |

型号、标称尺寸、充装质量及参数说明直接沿用原项目 `specs.json`。原项目：`E:\金建设计工作\TEXTtoCAD\models\huahai_extinguisher`。

## 迁移方式

原 `build123d` 配方改为 Bentley 原生旋转体、圆锥/圆柱、长方体、圆环和圆截面放样体。保留筒体上下边缘圆角、肩部、底座、阀门、双手柄、销轴、压力表及指针、保险拉环、喷嘴、软管固定夹与标签板。

筒体和肩部在 Bentley 单元内使用相交的独立原生实体，未进行布尔合并。软管采用平滑 Hermite 中心线的 80 段圆截面放样；对放样中心线长度求解至 400 mm，外形接近原脚本，但不保证与 OpenCascade 的插值样条逐点一致。原项目对细节的外观简化假设继续适用。此模型用于布置与展示，不是压力容器结构或质量计算模型。

尺寸使用 `GetUorPerMeter() / 1000` 转换，不要求工程的主单位为毫米。颜色采用 RGB 真彩色，不依赖项目色表中红色的索引。

CEL 导出使用 `Cell.AddLibDescr` 写入命名单元，经过 Bentley 的保存接口落盘。它会临时附加导出库，并在结束或出错时恢复原附加库。当前模型不会留下临时几何。已有目标文件不覆盖；失败时保留带唯一后缀的 `.partial.cel` 供检查，最终文件仅在全部步骤成功后生成。

种子优先读取本目录的 `seed3d.dgn`，其次读取本机 OPM 安装目录的种子。无法自动找到时，界面会要求选择 **Bentley 提供的空白三维种子**。请勿使用已有工程 DGN 作为种子，否则复制出的库会包含该工程的内容。

## 文件

- `huahai_opm.py`：中文规格界面及入口。
- `huahai_geometry.py`：独立的毫米配方，无第三方依赖。
- `huahai_bentley.py`：Bentley 原生实体、点选放置及 CEL 保存。
- `specs.json`：原项目五种规格参数。
- `test_offline.py`：离线尺寸、单位换算与导出异常处理测试。
- `verify_in_opm.py`：在 OPM 内运行的原生模型与实际 CEL 验证。
- `run_host_check.py`：本机开发验证用自动化入口，固定使用 D 盘 OPM 安装路径；日常使用不需要运行。

`last_selection.json` 记录上次选型。失败详情写入 `huahai_debug.log`。请将整个目录放在可写位置；多文件之间须保持同目录关系。

## 验证

本轮离线 9 项测试及全部 Python 文件语法检查已通过。按用户要求由用户在 OPM 中测试；原生宿主验证尚未完成，当前未交付预生成的 CEL 文件。可使用界面导出，或运行下面的宿主验证脚本生成。

在普通 Python 3.12 或 Bentley Python 中运行：

```powershell
cd 'E:\Code\Bentley_Python_plugin\灭火器箱\华海灭火器_OPM'
& 'C:\ProgramData\Bentley\PowerPlatformPython\python\python.exe' -m unittest -v test_offline
```

离线测试检查全部规格筒径、总高、底座标高、喷射配置、软管中心线长度、毫米到 UOR 的转换及旋转，还有导出成功/失败时的库恢复和防覆盖。CEL 部分采用模拟接口，不能替代 OPM 内的原生验证。

在 OPM Python Manager 中运行 `verify_in_opm.py`，会在内存中创建五种灭火器，查询实际范围并检查总高，随后实际导出带时间戳的 `.cel`，输出 `opm_validation_report.json`。该报告的 `native_host_validated` 为 `true` 才表示原生验证及 CEL 保存均通过。它不在当前工程中添加模型。

界面可在普通 Python 中预览，建模按钮会禁用：

```powershell
& 'C:\ProgramData\Bentley\PowerPlatformPython\python\python.exe' huahai_opm.py --ui-preview
```

此插件生成普通 Bentley 三维图形单元。未注册 OpenPlant 工艺对象类别、数据库组件或连接端口。

接口依据：本机 `C:\ProgramData\Bentley\PowerPlatformPython\Examples\Microstation\Intellisense` 声明、Bentley 官方 COM / 单元示例，以及[官方 Python 示例说明](https://bentleysystems.service-now.com/community?id=kb_article_view&sysparm_article=KB0038652)。
