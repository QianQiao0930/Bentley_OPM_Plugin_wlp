# Bentley_OPM_Plugin_wlp

为 **Bentley OpenPlant Modeler（OPM）** 开发的 Python 插件集合。所有脚本运行在 Bentley Power Platform Python 环境（`MSPyBentley` / `MSPyBentleyGeom` / `MSPyDgnPlatform` / `MSPyMstnPlatform`）中，直接在三维 DGN 模型内创建 MicroStation SmartSolid 实体。

> 这些是**几何建模**工具，生成的是活动 OPM 模型中的 SmartSolid 图元。若需注册为带 Class / Tag / 规格属性的 OpenPlant 智能组件，还需结合项目使用的 OPM 类库、EC Schema 和目录规范。

## 目录结构

| 目录 | 说明 |
| --- | --- |
| `安保围栏` | 参数化安全围栏建模，按约束生成围栏实体钢管、围栏片、立柱和螺栓 |
| `实体管口` | CL150 法兰等级管口生成器：空心钢管 + 法兰 + 密封面凸台 + 可选螺栓孔（首版） |
| `方形人孔` | 带盖板的方形人孔：筒体、盖板、U 型把手，按几何规则装配 |
| `水箱爬梯` | 水箱爬梯建模库（`ladder_lib.py`），提供爬梯 / 踏步 / 护笼等建模基础能力 |
| `灭火器箱` | 灭火器箱体生成工具：生成箱体、门与隔板，并通过 ItemType 构件并统计生成 JSON 清单 |
| `竖直弯头耳轴` | 参数化竖直弯头耳轴：A/B/C 型底板、空心/实心耳轴、鞍口布尔运算、通气孔 |
| `端焊三角架` | 端焊三角架放置工具：A–D 变体、L1/E 参数，并生成独立 BOM ItemType |

## 环境要求

- Bentley OpenPlant Modeler（基于 MicroStation）
- Power Platform Python 环境（MSPy 模块）
- 三维、公制 DGN 模型

## 通用使用方法

1. 在 OPM 中打开或新建一个**三维**、公制的 DGN 模型。
2. 打开 **Utilities（实用工具）→ Python** 的 Python Editor。
3. 新建 Python Project，选择或复制对应目录中的脚本，然后执行。
4. 在弹出窗口中设置参数，确认后在模型内点取放置点；右键可取消。
5. 每个脚本的**具体参数与几何规则**见各自目录下的 `README.md`。

> 注意：脚本按当前 DGN 的 `MASTER_UNITS_PER_METRE` 换算单位，因此输入尺寸统一按 mm 解释，不要求把主单位设成 mm。

## 各模块单独说明

- `安保围栏`：见 `安保围栏/README.md`（立柱布局、GS-M16 尺寸对应、可选混凝土基础）。
- `实体管口`：见 `实体管口/README.md`（法兰尺寸数据与建模逻辑分离，位于 `flange_data.json`）。
- `方形人孔`：见 `方形人孔/README.md`。
- `竖直弯头耳轴`：见 `竖直弯头耳轴/README.md`。

## 排错

部分脚本在 Bentley 几何内核返回错误时会向各自目录写入 `*_debug_log.txt`，排查时请查看对应日志。

## License

仅用于项目内部，版权归作者所有。
