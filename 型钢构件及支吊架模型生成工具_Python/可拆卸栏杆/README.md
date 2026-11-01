# 可拆卸钢结构栏杆插件（第一版）

`removable_handrail.py` 在 Bentley OpenPlant Modeler / MicroStation 的活动 3D 模型中，沿用户点选的水平或带单一坡度的智能线创建**可拆卸栏杆**。整道栏杆拆成两个普通单元：

| 单元名 | 内容 | 用途 |
| --- | --- | --- |
| `REMOVABLE_HANDRAIL_SOCKET` | DN50 套管（150 长） | 永久固定件 |
| `REMOVABLE_HANDRAIL_PANEL` | DN40 立杆 + 定位环 + 顶/中横杆 + 连接球 + 130 高挡板 | 可整片上拔的可拆面板 |

分开封装后，永久套管与可拆面板可以在模型里分别选中、隐藏、导出或统计，便于表达"拆"这个动作。生成时同步挂 **ItemType 钢材构件项**，可一键导出按规格汇总的 JSON 清单。

## 可拆卸原理

- **固定件**：只有一段 `DN50（φ60.3×4.5）` 套管，长 150，顶面比所选线段低 10（正好一个定位环厚度），让定位环坐在套管口、避免相碰（生根做法不建模，直接落在套管上）。
- **可拆件**：`DN40（φ48.3×3.2）` 立杆自所选线段向上为栏杆高度，向下一段插入套管。φ60.3 套管的内径约 `60.3 − 2×4.5 = 51.3`，与 φ48.3 立杆之间单边约 **1.5 mm** 环隙，构成可插拔的滑动配合。
- **定位环**：立杆在套管口装一片 **10 mm 厚钢片**（`locating collar`），钢片上边缘与所选线段平齐，限制插入深度并防止立杆落入管内。
- **单侧钻孔**：图纸要求横杆只在立柱单侧连接（`STANCHION DRILLED ON ONE SIDE ONLY`），松开该侧螺栓后立杆即可整根上拔。本插件不建螺栓，杆件交点的 φ76 连接球代表该处夹箍 / 连接件。
- **底部挡板**：`130×6` 挡板位于所选内侧，底边高于所选线段 10，内侧面与立杆外圆相切（中心线偏移 = 立杆半径 + 板厚 / 2）；总长比线段长 50（两端各外伸 25）。

## 尺寸与图纸对应

| 构件 | 尺寸或规则 |
| --- | --- |
| 可拆立杆 | DN40，`φ48.3×3.2`，自线段向上为栏杆高度，向下插入套管 |
| 固定套管 | DN50，`φ60.3×4.5`，长 150，顶面比所选线段低 10（让定位环坐在套管口） |
| 定位环 | 10 mm 厚钢片，外径 `φ76`，上边缘与所选线段平齐，下边缘坐在套管顶 |
| 顶部扶手 | `φ42.4×3.2` 空心钢管，中心标高 1017 mm（参照固定式护栏） |
| 中间横杆 | `φ33.7×3.2` 空心钢管，中心标高 560 mm |
| 连接球 | 立柱与两道横杆交点各一个，直径 76 mm |
| 底部挡板 | `130×6`，位于所选内侧，底边高于线段 10，内侧面与立杆外圆相切，总长比线段长 50 |
| 立柱分格 | 相邻立柱不超过 **1800**（`1800 MAX PANEL CRS NTS`），两端均设柱（退让 0） |
| 转角 | 横杆中心线 R140，转角两侧优先在距理论折点 300 mm 处设柱 |
| 颜色 | 精确 RGB (255, 204, 0) |

## 建模假定

图纸（`LOCATING COLLAR TO MANUFACTURER'S DETAILS TYP`）的定位环为厂家件；本版按 **10 mm 厚钢片**、上边缘与所选线段平齐建模。

所选路径线段即**安装基准面**：定位环 10 mm 厚、上边缘与该线段平齐；套管长 150、顶面比该线段低 10，定位环正好坐在套管口；立杆自该线段向上为栏杆高度、向下插入套管。若现场做法不同，改 `SLEEVE_LENGTH` / `STANCHION_INSERT` / `COLLAR_THICKNESS` 即可。底板、化学锚栓、抱梁卡板、预埋板等生根做法**不在本插件建模范围内**。

## 使用方法

1. 在 OpenPlant Modeler 中打开一个**三维** DGN 模型。
2. 打开 Python Editor，运行 `removable_handrail.py`。
3. 在面板中选择挡板侧（`路径左侧` / `路径右侧`），必要时勾选"反转路径方向"。
4. 可调整"立柱最大间距"（默认 1800，两端均设柱）。
5. 点选一条水平或带单一坡度的智能线，程序立即生成预览；改选项会自动重建一版。
6. 点【确定】保留预览；点【取消】删除本次预览。
7. 点【导出 JSON 清单】按规格汇总当前模型内的栏杆钢材（见下节）。

界面选项变化时采用"先成功创建新版、再删除旧版"的方式重建，因此几何创建失败不会误删上一版有效预览。

## 几何规则

- 立柱始终竖直；横杆、固定件的标高均相对路径局部标高计算。
- 立柱沿完整路径按 50 mm 工程模数排布，两端均设柱（退让 0），相邻立柱不超过设定上限；横杆同样沿完整路径扫掠。
- 纯变坡点保留尖折并强制设柱；水平转向折点自动转换为 R140 圆角；同一折点既转向又变坡时明确拒绝，以免生成不可控的空间弯头。
- 挡板沿与栏杆平行、且与立杆外圆相切的偏移路径一次扫掠；转角处按内外侧自动增减偏移半径，首末两端各外伸 25。
- 固定件（150 长套管）与可拆件（立杆 + 定位环 + 横杆 + 挡板）是独立实体，不做焊接布尔合并；整道栏杆是单元，不是布尔合体。

## 已知限制

- 不生成螺栓、夹箍实体、底板 / 锚栓 / 卡板 / 预埋板等生根件，也不生成支撑钢梁（`UNP / IWF / HB`）、格栅开孔或焊缝；固定件只有一段 150 长的套管，连接球是夹箍 / 连接件的简化表示。
- 套管与立杆之间的 1.5 mm 环隙只作视觉与逻辑表达，不建模为可动约束。
- 暂不支持竖直段、闭合路径、无规则空间折点，以及螺栓级别的单侧钻孔连接细节。

## 参数速查

| 常量 | 默认值 | 含义 |
| --- | --- | --- |
| `STANCHION_OD` / `STANCHION_WALL` | 48.3 / 3.2 | 可拆立杆（DN40）外径 / 壁厚 |
| `SLEEVE_OD` / `SLEEVE_WALL` | 60.3 / 4.5 | 固定套管（DN50）外径 / 壁厚 |
| `SLEEVE_LENGTH` | 150 | 套管长度（顶面比所选线段低 10，让定位环坐在套管口） |
| `STANCHION_INSERT` | 150 | 立杆插入套管深度 |
| `COLLAR_OD` / `COLLAR_THICKNESS` | 76 / 10 | 定位环外径 / 钢片厚度 |
| `TOP_RAIL_Z` / `KNEE_RAIL_Z` | 1017 / 560 | 顶部扶手 / 中间横杆中心标高 |
| `TOP_RAIL_OD` / `KNEE_RAIL_OD` | 42.4 / 33.7 | 顶部扶手 / 中间横杆外径 |
| `BALL_DIAMETER` | 76 | 连接球直径 |
| `KICKPLATE_HEIGHT` / `KICKPLATE_THICKNESS` | 130 / 6 | 挡板高 / 厚 |
| `KICKPLATE_BOTTOM_Z` | 10 | 挡板底边高于所选线段 |
| `KICKPLATE_END_EXTENSION` | 25 | 挡板首末各外伸（总长比线段长 2×） |
| `POST_SPACING_MAX` | 1800 | 立柱最大间距（`MAX PANEL CRS`） |
| `MODULE` / `CORNER_RADIUS` | 50 / 140 | 排柱模数 / 转角中心线半径 |
| `COLOR_RGB` | (255, 204, 0) | 构件颜色 |
| `SOCKET_CELL_NAME` / `PANEL_CELL_NAME` | `REMOVABLE_HANDRAIL_SOCKET` / `REMOVABLE_HANDRAIL_PANEL` | 两个单元名 |
| `ITEM_LIBRARY_NAME` / `ITEM_TYPE_PREFIX` | `RemovableHandrailComponents` / `RemovableHandrailComponent` | 钢材清单 ItemType 库 / 前缀 |
| `BOM_JSON_NAME` | `可拆卸栏杆_bom.json` | 清单导出文件名 |

## 钢材清单（ItemType + JSON）

沿用 `端焊三角架` / `灭火器箱` 的构件项做法：生成栏杆时给每个钢构件类型挂一个 **ItemType 构件项**（属性 `ComponentName`、`Specification`、`DesignLengthMm`、`Quantity`、`Unit`），定义写入 DGN 的 `RemovableHandrailComponents` 库；套管的项挂在 `REMOVABLE_HANDRAIL_SOCKET` 上，其余挂在 `REMOVABLE_HANDRAIL_PANEL` 上，两个单元合起来正好是一道栏杆，不会重复统计。

| 构件 | 规格 | 长度口径 |
| --- | --- | --- |
| 固定套管 | 钢管 φ60.3×4.5 | 150 × 根数 |
| 可拆立杆 | 钢管 φ48.3×3.2 | (插入 150 + 1017) × 根数 |
| 定位环 | 钢板 φ76×10 | 按件计（不累计长度） |
| 顶部扶手 | 钢管 φ42.4×3.2 | 各段中心线实长 |
| 中间横杆 | 钢管 φ33.7×3.2 | 各段中心线实长 |
| 底部挡板 | 钢板 130×6 | 路径实长 + 50 |

面板上的 **【导出 JSON 清单】** 按钮调用 `export_removable_handrail_bom_json()`，扫描当前 DGN 中本插件的构件项，按 `名称 + 规格 + 单位` 汇总数量与总长，写出 `records`（逐件明细）与 `summary`（汇总）两段 JSON。

## 调用方式

- 界面入口：`PyMain()`（脚本末尾有 `if __name__ == "__main__"`，在 Python Editor 中直接运行）。
- 编程调用：
  - `draw_removable_handrail_along_path(vertices, side="left", reverse=False, panel_spacing=1800)`：直接生成并写入模型，返回统计字典；
  - `replace_removable_handrail(..., previous_handles)`：预览用的重建接口，返回 `((固定件句柄, 面板句柄), 统计字典, 是否删掉旧预览)`；
  - `_build_removable_handrail_cells(...)`：只构建不写模型，返回 `(socket_builder, panel_builder, 统计字典)`；
  - `_socket_geometry(point, tangent)`：纯几何函数，返回套管 / 立杆 / 定位环的毫米坐标；
  - `_steel_inventory(pieces, post_count, total_length)`：纯函数，返回本道栏杆的钢材清单（含挂载单元、规格、长度、数量）；
  - `export_removable_handrail_bom_json(output_path=None)`：导出钢材清单 JSON，返回文件路径。

## 几何自检

`_geometry_selftest.py` 用 AST 抽取纯几何函数，**不需要 MicroStation**，任何 Python 3 都能跑：

```
python _geometry_selftest.py
```

覆盖模数化立柱排布（总额闭合、上限 1800、最多一个非模数尾数、两端均设柱）、R140 转角排柱、可拆卸节点几何（定位环 10 mm 上边缘齐线、套管 150 顶面比线低 10 且与定位环下边缘重合、立杆自线向上）、挡板偏移路径（与立杆外圆相切、两侧方向、首末各外伸 25、总长比线长 50）、钢材清单（管长口径、挡板长度、挂载分组），以及插入深度校验，全部通过时输出 `removable_handrail geometry self-test: OK`。

这是一份**几何建模**插件。若需要注册为带 Class / Tag / 规格属性的 OpenPlant 智能组件，还需结合项目使用的 OPM 类库、EC Schema 和目录规范。
