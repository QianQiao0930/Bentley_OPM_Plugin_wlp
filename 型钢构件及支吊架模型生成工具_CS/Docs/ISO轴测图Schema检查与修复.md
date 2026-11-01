# ISO 轴测图生成失败：Schema 检查点与修复方法

> 用途：给 `Deployment/SchemaPatcher`（tkinter / Fluent 两版共用引擎）增加“修复轴测图 Schema”功能的规则说明与验收依据。
> 来源：2026-10-26 排查记录 + Bentley KB0098072 + 本机 Schema 只读盘点（2026-11-01）。
> 结论先行：**三个空节点是明确的 Schema 缺陷，值得修；但它不是“生成失败”的充分条件，修完必须用真实管线重出 ISO 才算验证。**

## 1. 症状与官方依据

| 项目 | 内容 |
| --- | --- |
| 现象 | OpenPlant Modeler 2024 无法生成 ISO 轴测图，切换 ISO Style 仍失败 |
| 日志 1 | `Unable to cast object of type 'System.DBNull' to type 'System.String'` |
| 日志 2 | `StringToBoolean` 转换失败，调用栈含 `StylePersister.AddData`、`CreateECInstance` |
| 官方案例 | Bentley KB0098072《To Resolve Error Message "Unable to cast object of type 'System.DBNull' to type 'System.String'"》，产品为 OpenPlant Isometrics Manager CONNECT Edition |
| 官方结论 | Schema 文件中自定义属性节点不完整，导致取属性时得到 DBNull，ISO 生成中断 |

两类日志的来源不同，必须分开处理：

- **DBNull**：与 KB 案例吻合，指向 Isoextractor Schema 的自定义属性缺子节点。
- **StringToBoolean / StylePersister**：更像 ISO Style 配置里的布尔属性存了非法字符串，属于样式侧；只修 Schema 不一定消失。

## 2. 本机现状（只读盘点，未改任何文件）

盘点范围：`C:\ProgramData\Bentley`、`D:\Program Files\Bentley`、`E:\Code` 下全部 `OpenPlant_3D_Supplemental_Isometrics_Isoextractor*.xml`。

| 项目 | 结果 |
| --- | --- |
| 副本数量 | 28 份（当前工作集、Backup、OpenPlantExample、OPPA 各版本、仓库分发副本、测试夹具） |
| 三个节点状态 | **28/28 均带预期子节点**，没有发现空壳 |
| 当前工作集文件 | `...\CINF_F1263AA\Standards\OpenPlant\Schemas\OpenPlant_3D_Supplemental_Isometrics_Isoextractor.01.08.ecschema.xml`，276,659 B，SHA256 `1B20A603694F636E2D405B99C5583BEA55276A72AB5CC6BA443F24949D263E30`，mtime 2026-10-15 19:37:44 |
| 仓库分发副本 | `bin/Release/Schemas/` 同名文件，字节与工作集完全一致（同 SHA256） |
| 命名空间 | 根节点声明 `Bentley_Standard_CustomAttributes` **01.14**，文件内 6 处 `xmlns` 均为 01.14，无 01.00 混用 |
| 依赖可用性 | OPM 2024 安装目录存在 `Bentley_Standard_CustomAttributes.01.14.ecschema.xml` |

> 含义：**这台机器当前这份 Schema 已经是“修好”的状态**（或它原本就完整）。如果现在仍然出不了 ISO，问题多半不在三个节点，应按第 3 节的 P1/P2 继续查。
>
> 若 2026-10-26 排查时确实看到的是空节点，那份文件应不是当前工作集这一份（可能来自另一台机器、另一个 WorkSet，或后来被替换过）。本机 `Backup` 里 2026-07-29 的原始副本、OPPA 各版本副本也都带子节点，说明“官方基线本来就有”，空壳更可能是某次手工编辑/合并造成的。

## 3. 检查点清单

### P0：Schema 结构（可自动修复）

| 编号 | 检查点 | 怎么查 | 通过标准 | 不通过处理 |
| --- | --- | --- | --- | --- |
| P0-1 | 找到实际加载的文件 | 工作集 `Standards\OpenPlant\Schemas\OpenPlant_3D_Supplemental_Isometrics_Isoextractor.01.08.ecschema.xml` | 文件存在、`schemaName` 正确、UTF-8 | 报错，不出计划 |
| P0-2 | 类存在 | `ECClass[@typeName='PLANT_BASE_OBJECT']` | 唯一存在 | 报错 |
| P0-3 | 三个节点存在 | `ECCustomAttributes` 下的 `IE_Mappings`、`L00_LABEL_SECTION_LABELS`、`SPECIFIC_BOM_LABELS` | 三个都唯一存在 | 缺失 → 新增节点；重复 → 冲突 |
| P0-4 | 节点不是空壳 | 每个节点必须有下表的子节点 | 子节点齐全 | 缺哪个补哪个 |
| P0-5 | 子节点未被项目改写 | 检查预期子节点是否为空元素 | 为空、无文本 | 有内容/多出别的子节点 → 冲突，不覆盖 |
| P0-6 | 命名空间正确 | 三个节点的 `xmlns` | `OpenPlant_IsoExtractor_Custom_Attributes.01.08` | 不同 → 冲突，不改写 |

三个节点与必需子节点（以当前工作集为准）：

| 节点 | 必需子节点（顺序） |
| --- | --- |
| `IE_Mappings` | `END_POINT_ORDER_MAP`、`OVR_END_PREPARATION` |
| `L00_LABEL_SECTION_LABELS` | `LBL_SECT_LABELS` |
| `SPECIFIC_BOM_LABELS` | `ATTRIBUTES` |

> **误报防护**：`PLANT_BASE_OBJECT` 上的 `IE_Component`、`IE_Port` 本来就是自闭合的空节点，是正常写法；只有上表三个节点必须带子节点。规则要写死这三个，**不要**做成“所有空节点都补”。

### P1：Schema 引用与版本一致性（只报告，不自动改）

| 编号 | 检查点 | 怎么查 | 通过标准 | 不通过处理 |
| --- | --- | --- | --- | --- |
| P1-1 | 自定义属性命名空间一致 | 根节点 `ECSchemaReference name="Bentley_Standard_CustomAttributes" version="…"` 与文件内 `xmlns="Bentley_Standard_CustomAttributes.xx.xx"` | 两者完全一致 | 冲突，提示人工统一；不要自动替换命名空间 |
| P1-2 | 引用的版本本机存在 | 在 OPM 的 `ECSchemas\Standard` 或工作集里找对应 `.ecschema.xml` | 找得到 | 错误：先补齐依赖，再谈修 Schema |
| P1-3 | 只处理所选目录 | 工具只读取用户选择的 Schema 目录，不扫描 `Backup`、`Versions` 或安装目录 | 计划只涉及该目录内的文件 | 其他目录的同名副本需人工另行确认，工具不代选 |
| P1-4 | XML 完整性 | 现有引擎的 `Document` 解析 | 可解析、根节点正确 | 报错，不写 |

> 本次盘点中 28 份文件的 `ECSchemaReference` 与 `xmlns` 全部自洽（工作集 01.14，OPPA 各版本 01.13），没有发现混用；但 01.00/01.14 的混用确实会造成加载或属性解析异常，必须作为独立检查项保留。

### P2：日志与样式（人工判断）

| 编号 | 检查点 | 判据 | 说明 |
| --- | --- | --- | --- |
| P2-1 | `DBNull` 是否消失 | 修复后重新生成，`IsometricException.log` 不再出现该异常 | 与 Schema 修复直接相关 |
| P2-2 | `StringToBoolean` 是否消失 | 同上 | 若仍在，转查 ISO Style 的布尔属性/自定义属性类型 |
| P2-3 | 是否换了管线/Style 才成功 | 用同一管线、同一 Style 复现 | 否则不能归因于本次修复 |

## 4. 修复方法（三处 XML）

原则：**只补缺失的子节点，不重排、不覆盖已有内容、不动命名空间、字节级插入。** 现有 `xmlspan.append_child` 已能处理“自闭合 → 展开后插入”和缩进探测。

### 4.1 IE_Mappings

```xml
<IE_Mappings xmlns="OpenPlant_IsoExtractor_Custom_Attributes.01.08">
    <END_POINT_ORDER_MAP />
    <OVR_END_PREPARATION />
</IE_Mappings>
```

### 4.2 L00_LABEL_SECTION_LABELS

```xml
<L00_LABEL_SECTION_LABELS xmlns="OpenPlant_IsoExtractor_Custom_Attributes.01.08">
    <LBL_SECT_LABELS />
</L00_LABEL_SECTION_LABELS>
```

### 4.3 SPECIFIC_BOM_LABELS

```xml
<SPECIFIC_BOM_LABELS xmlns="OpenPlant_IsoExtractor_Custom_Attributes.01.08">
    <ATTRIBUTES />
</SPECIFIC_BOM_LABELS>
```

判定与状态：

| 现场 | 状态 | 动作 |
| --- | --- | --- |
| 节点自闭合，或只有空白、无元素子节点 | 新增 | 补必需子节点 |
| 节点存在，缺 1～2 个必需子节点 | 新增 | 只补缺的，保持已有顺序 |
| 三个子节点齐全且为空 | 已具备 | 不写 |
| 出现额外子节点、预期子节点带文本/子元素、或同名节点重复 | 冲突 | 不写，提示人工核对 |
| 节点缺失 | 新增 | 插入整段节点（含子节点） |
| 类或 `ECCustomAttributes` 缺失 | 错误 | 停止 |

冲突不覆盖是硬规则：项目可能在这里加了自定义映射，写坏了 ISO 更难查。

## 5. 已加入 SchemaPatcher（`iso_schema`）

### 5.1 Feature

| 项 | 值 |
| --- | --- |
| key | `iso_schema` |
| label | `修复轴测图 Schema` |
| 涉及文件 | 仅 `ISO`（`OpenPlant_3D_Supplemental_Isometrics_Isoextractor.01.08.ecschema.xml`） |
| 说明 | 检查 `PLANT_BASE_OBJECT` 的三个自定义属性节点，按 KB0098072 补必需子节点；不改其他类、不改命名空间 |

已与现有四项并列加入 `FEATURES`（位于“修改轴测图出图”之后）；**未并入 `all`**：前三项是装插件能力，这一项是修环境，语义不同。

### 5.2 planner 行为

```python
ISO_SCHEMA_NODES = (
    ("IE_Mappings", ("END_POINT_ORDER_MAP", "OVR_END_PREPARATION")),
    ("L00_LABEL_SECTION_LABELS", ("LBL_SECT_LABELS",)),
    ("SPECIFIC_BOM_LABELS", ("ATTRIBUTES",)),
)

def plan_iso_schema(ctx):
    doc = ctx.docs[ISO]        # 只来自用户选择的 Schema 目录
    ...
```

要点：

- **只读所选目录**：`ctx.docs[ISO]` 由 `load_plan(schema_dir, …)` 加载，不会去 `Backup`、`Versions`、OPM 安装目录找副本；目录里没有 Isoextractor 就报“缺少 Schema 文件”，不猜；
- 一个节点一条台账记录，`target` 形如
  `ECClass[@typeName='PLANT_BASE_OBJECT']/ECCustomAttributes/IE_Mappings`；
- 节点缺失 → 插入整段；节点是空壳或只缺部分子节点 → 保留原开始标签（含 `xmlns`），按官方顺序重建该节点；项目自定义（额外子节点、带内容的子节点、重复节点、命名空间不符）→ 冲突，不写；
- `details` 里放插入的 XML 片段，Fluent 版详情面板直接显示“将插入”；
- 只触碰这三个节点，类里其他 `IE_*` 属性、其他顶层类逐字节不变；
- 复用引擎已有的“内存改完自检 → 复检全部已具备 → 备份 → 原子替换 → 失败回滚”。

### 5.3 范围边界

1. 不扫描其他目录，不判断“哪一份才是 OPM 实际加载的”；用户必须自己选对工作集 `Standards\OpenPlant\Schemas`。
2. 不检查 `Bentley_Standard_CustomAttributes` 的版本一致性（P1-1/P1-2 仍靠人工，或后续单独加只读诊断）。
3. 不改 ISO Style、不改 DGN、不改插件 DLL。

## 6. 测试计划

| 用例 | 夹具 | 期望 |
| --- | --- | --- |
| T1 三节点全空壳 | 由真实 Schema 删除三个节点的子节点 | 3 条“新增”，写入后复检全部“已具备” |
| T2 只缺 `OVR_END_PREPARATION` | 只删一个子节点 | 1 条“新增”，其余“已具备” |
| T3 已有额外子节点 | 在 `IE_Mappings` 加 `<CUSTOM_MAP />` | “冲突”，不写任何文件 |
| T4 全部齐全 | 真实工作集副本 | 无需修改，不产生备份 |
| T5 类缺失 | 删除 `PLANT_BASE_OBJECT` | “错误”，不写 |
| T6 幂等 | T1 应用后再检查 | 全部“已具备”，无待改项 |
| T7 未涉及节点不变 | T1 应用后比对文件 | 根节点前、根节点后、其他顶层类逐字节一致 |
| T8 真实副本回归 | 分别把本机 28 份 ISO Schema 所在目录作为“所选目录” | 全部“已具备”，一份都不写 |

复用 `Development/SchemaPatcherCheck` 的合成夹具 + 真实 Schema 对比框架；新增分支不依赖 PowerShell（该修复没有对应安装脚本）。已落地：`SchemaPatcherCheck` 15 项（含 3 个 `iso_schema` 用例）与 Fluent 16 项通过。

## 7. 修复后的现场验证

由用户在 OPM 中执行，开发侧只提供步骤：

1. 保存并完全退出 OPM；备份工作集 `Standards\OpenPlant\Schemas` 目录。
2. 应用修复（工具会先备份 `.bak` + `receipt.json`）。
3. 重启 OPM，确认打开的是同一 WorkSet。
4. 用**同一条管线**、**同一个 ISO Style** 重新生成：`4002-MP-PPW-0001-A1B-100-NT`。
5. 检查 `IsometricException.log`：
   - `DBNull` 消失 → 本次修复有效；
   - 仍有 `StringToBoolean`/`StylePersister` → 转查 ISO Style 配置；
   - 出现新异常 → 保留日志与新旧 Schema 哈希。
6. 换一条管线再出一次，排除单条管线数据问题。
7. 记录：修复前后 Schema SHA256、ISO Style 名称、管线号、日志时间戳。

## 8. 风险与边界

- KB0098072 针对 Isometrics Manager CE，OPM 2024 的 Schema 版本是 01.08；规则相同，但仍需现场验证，不能把“补了节点”当成“修好了”。
- 三个节点只是 Schema 侧的一个明确缺陷；`StringToBoolean` 很可能来自 Style 配置，修复后仍可能失败。
- 不覆盖项目自定义：额外子节点、带内容的子节点一律冲突。
- 不在 OPM 运行时写入（沿用引擎的进程检测）。
- 必须改“实际加载的那一份”；同名副本（Backup/Versions/bin）只提示，不自动选择。
- 该修复会改动公共 Isoextractor Schema，影响该 WorkSet 所有项目的 ISO 输出，应用前必须备份。

## 9. 附：只读快速自检（PowerShell）

```powershell
$f = "...\WorkSets\<工作集>\Standards\OpenPlant\Schemas\OpenPlant_3D_Supplemental_Isometrics_Isoextractor.01.08.ecschema.xml"
[xml]$x = Get-Content -LiteralPath $f
$ns = New-Object System.Xml.XmlNamespaceManager($x.NameTable)
$ns.AddNamespace('ec', $x.DocumentElement.NamespaceURI)
$cls = $x.SelectSingleNode("//ec:ECClass[@typeName='PLANT_BASE_OBJECT']", $ns)
foreach ($n in 'IE_Mappings','L00_LABEL_SECTION_LABELS','SPECIFIC_BOM_LABELS') {
    $node = $cls.SelectSingleNode("ec:ECCustomAttributes/*[local-name()='$n']", $ns)
    "{0}: {1}" -f $n, $(if ($null -eq $node) { '缺失' } elseif ($node.ChildNodes.Count -eq 0) { '空壳' } else { ($node.ChildNodes | ForEach-Object LocalName) -join ',' })
}
```
