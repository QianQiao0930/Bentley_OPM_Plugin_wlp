# 管道支吊架（OpenPlant Modeler MSPython）

把所有**管道支吊架**插件与清单工具集中在本目录，共用一套 ItemType 契约，因此
不同型式的支吊架（端焊三角架、L 型管架，以及今后新增的）可以**一起统计**。

## 目录内容

| 文件 | 说明 |
| --- | --- |
| `支吊架公共库.py` | **公共支吊架库**：统一 ItemType 契约、`attach_components()`、`collect_statistics()`、`export_combined_bom()`（JSON）、`export_combined_xlsx()`（Excel） |
| `支吊架统计.py` | **统计插件（只读）**：统计活动文件中的支吊架数量，导出 Excel「支吊架表 + 材料汇总表」/ JSON |
| `支吊架清单导出.py` | 独立 JSON 导出入口 |
| `端焊三角架_选线版_端板.py` | 端焊三角架（选线 + 端板版）放置工具 |
| `端焊三角架_选线版.py` | 端焊三角架选线版（被端板版复用） |
| `端焊三角架.py` | 端焊三角架（点取放置版） |
| `端焊三角架_基础.py` | 端焊三角架基础库（几何 / 单元 / 面板外观） |
| `L型管架.py` | L 型管架放置工具 |
| `L型管架_几何.py` | L 型管架纯几何 / 数据逻辑（可单测） |
| `L型管架.commands.xml` | `PYLPIPERACK` 键入命令注册表 |
| `混凝土锚板.py` | 混凝土锚板 + 膨胀锚栓建模库（供端板版调用） |
| `G2-混凝土锚板.py` | 混凝土锚板 + 膨胀锚栓放置工具（G2 表 1 子项 A~D） |
| `tests/` | 纯逻辑单测（公共库 + L 型管架几何） |

> L 型管架依赖 `型钢截面生成器/steel_*`（型钢截面），按仓库相对路径引用；
> 其余模块均在本目录内相互引用。

## 公共 ItemType 契约

所有支吊架统一写入库 `PipeSupportComponents`，属性：

| 属性 | 类型 | 说明 |
| --- | --- | --- |
| `RecordKind` | 字符串 | `Assembly`（整组）/ `Component`（构件） |
| `SupportType` | 字符串 | 支吊架类型，如 `端焊三角架` / `L型管架` |
| `AssemblyTag` | 字符串 | 支吊架编号 |
| `ComponentName` | 字符串 | 构件名 |
| `Specification` | 字符串 | 规格 |
| `DesignLengthMm` | 双精度 | 设计长度 / 特征尺寸 |
| `Quantity` | 整数 | 数量 |
| `Unit` | 字符串 | 单位（件 / 套） |

每个放置的支吊架在整组单元上写一条 `Assembly` 记录（用于按类型统计套数），
每个构件写一条 `Component` 记录（用于材料汇总）。属性值写在 ItemType 默认值里。

## 使用

### 端焊三角架（选线 + 端板）
运行 `端焊三角架_选线版_端板.py`：点选横担上表面直线 → 选子项 / L1 / E / 端板
子项 → 预览 → 确定。清单写入公共库，`SupportType='端焊三角架'`。

### L 型管架
运行 `L型管架.py`：点选 L 形折线（竖直线＝立杆轴线、水平线＝横担顶面）→
选子项 / 类型（1/2 立杆在下、3/4 立杆在上·吊架）→ 预览 → 确定。
清单写入公共库，`SupportType='L型管架'`。

> 各插件面板的「导出 JSON 清单」导出的是**全部管道支吊架**的统一清单。

### 统计插件
运行 `支吊架统计.py`：显示当前活动 DGN 的支吊架总套数与按类型分布，并可
- **导出 Excel 清单**：一个 `.xlsx`，含「汇总 / 支吊架表 / 材料汇总表」三个工作表；
- **导出 JSON**：统一清单。

## 添加新的支吊架插件

```python
import 支吊架公共库 as psb
psb.attach_components(
    cell,
    support_type='××支吊架',        # 中文显示名
    support_code='XXX',             # ASCII 代号（ItemType 命名）
    assembly_tag=编号, assembly_spec=规格,
    components=[{'code', 'name', 'specification', 'length', 'quantity'}, ...],
)
```

接入后即自动出现在统计插件的清单里。

## 运行测试

```text
python -m unittest discover -s 管道支吊架/tests
```
