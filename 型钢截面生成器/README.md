# 型钢截面生成器（OpenPlant Modeler MSPython）

这是一个统一入口插件：先选“型钢型式”，再选对应“截面规格”，最后选择插入基准与放置方式（放置截面或沿路径扫掠）。它不依赖或调用旧插件目录中的模块，三个现有型式的数据与几何核心均已内置到本目录。

## 当前可放置型式

| 型式 | 内置数据 | 截面特点 |
| --- | ---: | --- |
| 平行腿槽钢 | 34 种 | 平行翼缘、两处根部圆角 |
| 普通热轧工字钢 | 45 种 | 1:6 翼缘坡度、r1/r2 真圆弧 |
| 热轧 H 型钢 | 431 种 | 平行等厚翼缘、四处根部真圆弧 |
| 斜腿槽钢 | 41 种 | 1:10 翼缘坡度、r1/r2 真圆弧 |
| 等边角钢 | 144 种 | r2=t/3、一个内圆角与两个端部圆角 |
| 不等边角钢 | 71 种 | 长边 BL、短边 BS，r2=t/3 与三处真圆弧 |
| HK 系列 H 型钢 | 378 种 | 平行翼缘、复用 H 型钢的四处根部真圆弧 |

目前已提供规格表的型钢均可直接放置；后续型钢仍可通过注册表继续扩展。

## 使用

1. 完全关闭并重新打开 OPM（清除旧插件可能留下的 Python 缓存）。
2. 在 OPM Python 脚本管理器运行 `steel_main.py`。
3. 在窗口中依次选择型钢型式、规格和插入基准。
4. 在“放置方式”中选择：
   - **放置截面（只生成二维截面）**：在模型中连续点取插入点放置闭合二维截面，右键 Reset 退出；不会再调用 Bentley 拉伸命令。
   - **沿路径扫掠**：在模型中选择一条开放路径线（直线、折线、SmartLine、复杂链、圆弧或样条）。截面会自动生成在路径起点、截面平面垂直于路径起点切向，然后沿路径扫掠为 SmartSolid。可勾选“扫掠完成后删除路径线”，扫掠成功后自动删除所选路径线。
5. 扫掠时截面绕路径轴的初始朝向以世界 Z 轴为参考；路径接近竖直时自动改用其它世界轴作为参考，保证截面不扭转、不共线退化。

首次运行后可使用：

```text
PYSTEEL PLACE
PYSTEEL DEFAULT
```

`PYSTEEL DEFAULT` 默认在点取处放置平行腿槽钢 20a 的二维截面。

## 后续增加型钢的接口

统一扩展点在 `steel_sections/steel_registry.py` 的 `_FAMILIES`。新型式需要三部分：

1. `steel_sections/steel_<family>_data.py`：提供 `DEFAULT_PROFILE`、`profile_names()`、`get_section()` 和 `validate_section()`。
2. `steel_sections/steel_<family>_geometry.py`：提供 `Point2d`、`INSERTION_MODES`、`scale_section()`、`build_<family>_geometry()` 与 `to_bentley_curve_vector()`。
3. 在 `_FAMILIES` 中将对应的待导入定义改为可用定义，并声明显示字段、几何构造函数名及圆弧转换方式。

这样 UI、参数表、动态预览、连续放置及键入命令都无需重复开发。

## 目录结构

插件根目录只保留唯一入口 `steel_main.py` 与键入命令表，其余依赖模块全部放在 `steel_sections/` 包内：

```text
型钢截面生成器/
├── steel_main.py                       # 唯一入口 + PYSTEEL 命令注册
├── SteelSectionGenerator.commands.xml  # 键入命令表
├── README.md
├── 型钢截面生成器_debug_log.txt         # 运行日志（自动生成）
├── steel_sections/                     # 全部依赖模块（Python 包）
│   ├── __init__.py
│   ├── steel_ui.py
│   ├── steel_tool.py
│   ├── steel_registry.py
│   ├── steel_sweep_geometry.py
│   └── steel_<family>_data.py / steel_<family>_geometry.py
└── tests/                              # 纯逻辑单元测试
```

## 文件说明

- `steel_main.py`：唯一入口与 `PYSTEEL` 键入命令注册；负责把插件根目录加入 `sys.path` 并导入 `steel_sections` 包。
- `steel_sections/steel_ui.py`：两级选择框、放置方式（放置截面 / 沿路径扫掠）与参数表。
- `steel_sections/steel_tool.py`：截面自由放置工具与沿路径扫掠工具（`SolidUtil.Create.BodyFromSweep`）；日志写在插件根目录。
- `steel_sections/steel_sweep_geometry.py`：扫掠坐标架与截面圆弧采样的纯几何计算（可脱离 Bentley 单元测试）。
- `steel_sections/steel_registry.py`：型式注册表及未来扩展接口。
- `steel_sections/steel_channel_*`、`steel_ibeam_*`、`steel_hbeam_*`、`steel_tapered_channel_*`、`steel_equal_angle_*`、`steel_unequal_angle_*`：内置数据和几何适配器；`steel_hk_data.py` 复用 H 型钢几何适配器。

> 包内模块一律使用相对导入（`from . import ...`）。仓库内其它插件（如 `管道支吊架`）通过 `from steel_sections import ...` 复用本插件的型钢数据与几何，因此插件根目录必须位于其 `sys.path` 上。
