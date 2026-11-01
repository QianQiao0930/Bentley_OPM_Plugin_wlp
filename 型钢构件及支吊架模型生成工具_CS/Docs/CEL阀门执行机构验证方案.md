# CEL 阀门执行机构验证方案

日期：2026-10-31。当前状态：用户确认V4官方流程能放置，随后要求GEARBOX基准与“先选择CEL、再放置”的UI。当前V6在主插件新增停靠选择页面及按实例保存资源的新类，编译和离线检查通过；Schema仅准备副本，真实DGN二进制保存、原生按钮/关联/随动/重开仍由用户验证。详见第18节。V3手工Create路线已停用。

## 1. 目标与基线

将用户制作的三维 CEL 单元用作阀门执行机构外形，验证安装定位、原生阀门关联、移动旋转、重生成、撤销重做和保存重开。普通 CEL 放置成功仅证明几何读取可行，不能作为原生执行机构接入成功的依据。

改动前基线提交：`9dc12b952410abab4d32cf43bfa7352c7e6871e8`（短号 `9dc12b9`），提交信息 `chore: checkpoint before CEL valve actuator validation`。提交前工作区干净，基线为空提交，其源码树与上一提交 `ba63b08` 一致。

初版交付仅增加方案、盘点证据及文档入口。当前接续记录见第 12 节；后续实现先限定一个执行机构单元、一种实际阀门类，在测试工作集和测试 DGN 副本中验证。

## 2. 已确认的基础与待查入口

证据：[本机磁盘 Schema 盘点](../Development/ValveActuatorCelValidation/schema-inventory.json)。采集于本机 C 盘 `CINF_F1263AA` 工作集，OPM 可执行文件版本为 `24.00.03.53`。盘点不是宿主当前加载配置的证明，也不是 DGN 嵌入 Schema 的读取结果。

| 项目 | 已确认内容 | 对方案的影响 |
| --- | --- | --- |
| 基类 | `VALVE_OPERATING_DEVICE`；`VALVE_ACTUATOR` 继承它 | 应研究执行机构体系，不能复用支架的 `Support` 身份 |
| 电动执行机构 | `ELECTRIC_VALVE_ACTUATOR` → `ElectricActuatorScript` | 可作为电动执行机构原生对照 |
| 气动执行机构 | `PNEUMATIC_VALVE_ACTUATOR` → `PnematicActuatorScript` | 类名保留磁盘配置的原始拼写；后续再扩大覆盖范围 |
| 创建配置 | `HANDLER_TYPE=Topwork`、`PLACEMENT_TOOL=TopworksPlacementTool` | 父阀门关联、安装架、创建顺序须单独核实 |
| 单元字段 | 创建配置含 `CELL_LIBRARY=TopWorksPreview.cel` 和 `DIAGRAM_CELL_NAME` | 不能直接认定改这两个字段就能替换正式三维几何 |
| 几何属性候选 | `MANUAL_VALVE_OPERATING_DEVICE` 和 `VALVE_ACTUATOR` 均有 `Geometry/binary` | 手轮继承前者；电动执行机构继承后者。字段存在仍不代表几何持久化及重生成已验证 |
| 项目已有 CEL 能力 | `CelLibraryReader` 只读枚举；`CelLibraryGeometry` 创建离线普通单元 | 可复用库读取、单位检查；现有工厂只提供世界 Z 旋转，三维安装架须扩展 |

本机磁盘现已核对关联类名 `VALVE_HAS_VALVE_OPERATING_DEVICE`，原生手轮处理器为 `Handwheel`；接口原型见第 13 节。实际 DGN 中的关系、安装架和几何持久化仍需用户运行验证，不将磁盘结构视为宿主已通过，也不将 `DEVICE_HAS_SUPPORT` 用于执行机构。

## 3. 用户提供的 CEL 与测试输入

首轮一个普通三维图形单元即可，保留真实尺寸及颜色。约定如下：

- 原点为用户新增圆柱的底部圆心，业务含义是执行机构连接杆与阀门外表面的交点（用户于 2026-10-31 明确）。新增圆柱已属于 CEL 几何，不再额外重复生成连接杆。
- 安装轴采用该圆柱的轴线。阀门侧目标点必须与上述表面交点对应；原生接口若返回阀杆端点或其他 Topwork 基点，须核对并转换到此接触基准，不直接混用，也不用包围盒中心替代。
- 局部 `+Z` 从阀门指向执行机构，沿安装轴。
- 局部 `+X` 指向明确的电机或手轮特征；`+Y` 按右手坐标系确定。对称模型可另附方向说明，无须为测试更改正式外形。
- 提供单元名称、型号、源单位和至少一项可核对的实际尺寸，例如总高或手轮外径；不同型号使用不同单元名称。
- 第一轮优先使用可独立读取的实体和普通嵌套单元。若含共享单元、参数化单元、参考附件、外部纹理，先盘点依赖，再决定支持或明确拒绝，不能静默漏件。

阀门样本可使用现有项目阀门的测试副本。记录其实际 EC 类名、原执行机构类名、阀杆连接位置及预期方向；未指定时先选择测试模型中能正常放置、移动和重开的一个原生阀门，不假定它的原点就是安装点。

CEL 文件到位后计算 SHA256，记录模型名、单位、源原点、几何数量和包围尺寸。原始 CEL 只读保留。

## 4. 分阶段验证与通过条件

| 阶段 | 操作及证据 | 通过条件 |
| --- | --- | --- |
| A：原生对照与只读探查 | 在测试 DGN 放一个原生阀门和默认执行机构，读取实例、关联、变换、安装点与几何归属；做一次移动、旋转、撤销重做及保存重开 | 找到真实 Topwork 接入方式，明确原执行机构是独立实例还是由阀门生成；对照自身稳定 |
| B：CEL 几何与定位 | 读取指定单元，在局部原点建立离线几何副本，变换到安装架；预览、调整角度、取消 | 单位、原点、方向、分件颜色正确；源库及阀门不变；取消无残留 |
| C：原生接入原型 | 通过已核实的接口创建独立测试执行机构类型或受支持的自定义几何实例，关联父阀门并持久化，重读核对 | 被识别为正确的执行机构；几何与关联落地；重生成仍保持 CEL 外形 |
| D：已有执行机构替换 | 对有默认执行机构的测试阀门执行替换；原件身份和归属校验后，在同一可撤销操作中完成替换 | 最终恰好一套执行机构；不叠图、不重复关系、不改变阀体和管线连接；失败恢复原件 |
| E：稳定性与回滚 | 执行下表全部主验收及故障场景，保存每个场景结果和日志 | 全部必测场景通过，回滚可验证；任何崩溃均判本阶段失败 |

A 阶段若无法取得受支持的 Topwork 几何入口，记录限制和可选路线，不将普通 Cell 附加属性当作 C 阶段通过。若原生对照也崩溃，先隔离宿主/样本问题，停止对该样本执行替换。

## 5. 几何与持久化设计候选

安装变换按阀门实际阀杆坐标架计算：

`世界点 = 阀杆安装架 × 绕局部 Z 的朝向旋转 × 局部安装偏移 × CEL 局部点`

偏移以毫米保存，并明确是阀杆局部坐标。零偏移时 CEL 原点与安装点重合。单位转换仅在 Bentley 边界执行一次；不得用包围盒中心替代 CEL 原点，也不得从管道轴推定阀杆方向。安装轴与参考方向接近平行时，使用确定的替代参考轴并验证右手性，不产生 NaN。

优先验证将导入几何的版本副本保存于 DGN 的受支持组件机制中，移动时使用已保存几何和当前变换。必须证明关闭程序后仍可恢复，不能仅保存在进程内缓存。保存单元名、型号、源库哈希、几何版本和安装参数；几何版本与 Schema 版本分开。

不得在每个移动/重生成回调中反复附加或切换外部 CEL 库。现有 `CelLibraryGeometry.Create` 会临时切换附加库，适合受控导入；不能未经验证直接放入 Topwork 重生成回调。需要验证离线 COM 单元到原生图形的转换，以及 ElementHolder 克隆、缓存和释放边界。

若 SDK 必须依赖外部 CEL，采用固定版本资源部署并验证缺库后的行为，明确报告此限制。未证明离线几何可持久化前，不承诺旧模型脱离 CEL 仍可编辑。

CEL 默认按型号选型，不做非等比缩放。更换阀门 DN 不代表执行机构应同比缩放，需明确保留型号、重新选型或拒绝不兼容安装。

## 6. 宿主验收矩阵

下列次数和误差是本原型的验收目标，不代表工程制造公差。位置比较先换算为毫米，目标误差不超过 `max(0.1 mm, 2 UOR)`；方向误差目标不超过 `0.1°`。记录实际值，不只写“正常”。

| 编号 | 场景 | 验收要求 |
| --- | --- | --- |
| V01 | 单元原始尺寸、颜色及嵌套结构 | 与 CEL 对照一致；无漏件、黑块或统一改色 |
| V02 | 阀杆沿 +Z、-Z、水平及倾斜方向；局部朝向 0/90/180/270° | 原点重合、无镜像、方向连续；选定阀门类不能表达的姿态记录为不支持 |
| V03 | 不同主单位/UOR 的测试 DGN | 实际毫米尺寸一致，无重复单位换算 |
| V04 | 预览取消、右键、退出、无效输入 | 无正式执行机构、关系或材料残留；原默认件保留 |
| V05 | 创建与替换后强制重生成 | CEL 外形保持；默认简化执行机构不重新出现 |
| V06 | 单独移动/旋转阀门，往返 20 次 | 执行机构跟随，不漂移、不重复、不崩溃；关系和几何数量稳定 |
| V07 | 使用 OPM 原生命令移动包含该阀门的管线组，往返 20 次 | 记录原生命令/模式；阀门实际参与移动时执行机构跟随；阀门连接不变 |
| V08 | 调整执行机构朝向及安装偏移，随后移动阀门 | 局部安装参数保持，无二次旋转或平移 |
| V09 | 创建、替换、移动的 Undo/Redo，各 10 轮 | 图形、属性、原件和关联一并恢复，无孤儿和重复实例 |
| V10 | 保存关闭，退出 OPM 后重开，重复 3 次 | 型号、外形、位置与关系保持，重开后仍可移动和重生成 |
| V11 | 导入后在测试副本中使外部 CEL 不可用，重启并重生成 | 内嵌方案应继续工作；外部依赖方案应按事先定义的行为报错并保留已有模型 |
| V12 | 删除执行机构、删除父阀门、复制阀门/执行机构 | 行为符合原生对照和已定义策略；不会引用错误父阀门或删除无关件 |
| V13 | 替换/规格变化及连续更换 CEL 型号 | 原生对照支持的操作逐项验证；型号选择明确，不自动拉伸电机、手轮等尺寸 |
| V14 | 原有阀门、执行机构及支架的混合模型 | 新功能不接管旧件；旧件显示、移动、重生成行为与对照一致 |
| V15 | ISO 与统计观察 | 记录原生类别、符号、方向、数量及描述；三维通过不能自动判 ISO/BOM 通过，不出现重复材料 |

故障场景至少包括：缺库/单元不存在、非三维单元、非法单位、预览后父阀门删除或模型切换、安装轴无效、关联创建失败、几何写入失败、提交/回滚失败、未知几何版本。可注入业务失败先用替身测试；真实宿主至少验证可安全复现的缺库、缺单元、取消及保存重开。

异常必须在已核实的 API 契约下处理，禁止靠吞异常、返回任意空图形或继续使用失效句柄避免提示。回滚失败时保留可追踪对象身份，明确标记模型需检查。

## 7. Schema 验证边界

先验证现有接口能否接纳自定义几何。必须新增类型时，在独立测试工作集建立专用执行机构类，保留原类映射；不得全局替换 `ELECTRIC_VALVE_ACTUATOR` 等已有类的处理器。

对照矩阵：旧默认件 + 原环境、旧默认件 + 新测试定义、新 CEL 件 + 新定义、新 CEL 件 + 新 DLL/旧数据、未知版本件的安全拒绝。每种组合均检查重开和移动，不能只测新建件。

Schema 或 DLL 切换在关闭测试宿主后执行，核对基础/Modeling/ISO 补充定义、DGN 中实际定义和加载 DLL 的路径/哈希。CEL 外形迭代优先更新几何资源版本，不反复更改同名 Schema 类契约。

## 8. 代码组织与复用边界（后续实现）

| 层 | 计划职责 |
| --- | --- |
| `Domain/ValveActuator/` | 毫米偏移、角度、型号和资源版本等纯数据，不持有 Bentley 对象 |
| `Data/ValveActuator/` | 只读父阀门/原执行机构身份、安装架和 CEL 目录；复用现有库读取规则 |
| `Services/ValveActuator/` | 安装变换、几何导入和离线克隆；复用已验证单位处理，不复制库切换代码 |
| `OpenPlant/ValveActuator/` | 按核实的 Topwork 契约创建、关联、重读、重生成和事务回滚 |
| `Tools/ValveActuator/` | 点取、动态预览、确认取消；复用 `ProbeLocateTool` 规则 |
| `Development/ValveActuatorCelValidation/` | 盘点证据、场景结果和必要的离线检查；检查源码从主工程排除 |

原型入口待 A 阶段确认后决定，首轮无需完整产品页面。不将执行机构写入 `PipeSupportComponents`；BOM 是否沿用原生执行机构通道以实际结果为准。现有管夹和普通 CEL 放置流程保持独立。

## 9. 日志、验收记录与回滚

每次运行使用独立目录，拟记录插件/宿主版本及哈希、测试 DGN、Schema 哈希、CEL 哈希/单元名、阀门和执行机构实例 ID、关联、安装架、当前变换、单位、几何数量、阶段与异常堆栈。逐场景保存结果，不用一个覆盖式 latest 文件代替全部证据。若宿主崩溃，保留该次日志、OPM 异常报告/转储和最近的测试 DGN 副本，停止连续写入同一副本。

结果分为通过、失败、不支持、未测；不支持必须解释范围，必测能力不支持时整体原型不能判通过。通过结论限定到实际阀门类、执行机构类型、CEL 和 OPM 版本。

Git 基线只保护已跟踪源码，不保护已安装 DLL、Schema、CEL 或 DGN。每次宿主验证前另存测试 DGN 和工作集副本；如需部署，备份实际加载 DLL/PDB、Schema 和资源并记录 SHA256、路径和恢复清单。

源码回查可使用 `git show 9dc12b9:<仓库相对路径>`；需要构建基线时优先创建独立检出目录或 worktree，不用 `reset --hard` 覆盖后续工作。仅回退源码无法修复已写入的模型数据。

运行环境回退：关闭测试宿主 → 按部署清单恢复配套 DLL/Schema/资源 → 打开测试前 DGN 副本 → 核对加载版本 → 执行原生对照移动与重开。含新自定义类的 DGN 不直接作为已回退环境的兼容证明。

## 10. 当前完成与下一步

已完成：改动前基线提交、现有 CEL/支架代码复用盘点、本机执行机构磁盘 Schema 只读盘点、分阶段方案及验收/回滚定义；CEL 只读结构盘点；用户确认普通放置没有问题，并明确表面接触安装原点。

已准备独立手轮换外形验证代码及 DLL，SDK 编译通过。尚未完成：真实父阀门和默认执行机构探查、原型在宿主加载、原生替换/随动/重生成及完整稳定性验收。公开方法签名与编译结果不代表运行契约或持久化已通过。

下一步从 A 阶段的原生阀门/默认执行机构对照继续，重点核对原生安装架与用户指定表面接触基准的差值，再做单一型号最小接入。宿主操作由用户执行；普通放置成功不扩展认定为 B 阶段全部或 C～E 阶段通过。

## 11. 换设备接续记录（2026-10-31）

用户已确认用途为阀门执行机构，CEL 用于其外形，不再沿管夹/支架入口实现。第一版计划交互为：启动功能 → 选择 CEL 库和单元型号 → 点击“选择阀门”并在模型中点取原生阀门 → 按实际阀杆安装架预览 → 调整朝向和必要偏移 → 确认安装；已有执行机构时明确提示替换。启动功能与许可证激活是独立操作。自动安装点读取能力仍须按 A 阶段核实，必要时设计手动指定安装点和轴向的补充操作。

下一台设备接续时：

1. 拉取仓库 `main` 的最新提交，保留改前基线 `9dc12b9`；方案初版提交为 `4eb51db`。
2. 先阅读本方案及项目 `AGENTS.md`，确认用户 CEL 是否已提供；当前尚未提供，亦无原型功能按钮或执行机构替换代码。
3. 核对新设备实际 OPM/SDK 版本、工作集和 Schema；盘点 JSON 中的本机绝对路径与哈希仅为历史证据，不作为新设备配置。
4. 用户准备的 CEL 采用安装中心为原点、局部 Z 沿安装轴、真实尺寸和单位、不同型号分别建单元；后续再确认 +Z 朝向及 +X 特征方向。
5. 从只读原生样本探查及最小原型开始，按本方案逐阶段验证，不将磁盘 Schema 盘点或普通 CEL 放置成功视为 Topwork 接入通过。

Git 推送只同步已跟踪文件；本机已安装 DLL/Schema、未提供的 CEL、正在运行的 OPM 会话和未纳入版本控制的 DGN 不随仓库迁移。本次换设备交接未关闭或修改当前 OPM 会话。

## 12. CEL 到位与用户验证记录（2026-10-31）

- 用户提供库：`C:\ProgramData\Bentley\OpenPlant 2024\Configuration\Organization\Cell\阀门执行机构.cel`，81920 字节，SHA256 `4DD17E6A4F44542380CB82DBCC60A32D1EA836DD99EA1987575F84458275FF6C`。
- 只读盘点见 `Development/ValveActuatorCelValidation/Runs/20261031_02/cel-native-inventory.json`：一个可放置三维图形单元“气动执行-DN800”，主单位定义为 mm，11 个 SmartSolid 和 3 个 Cone，模型无参考附件。仅枚举到的结构通过，不据此证明材质/所有外部资源或实体内核有效性。
- 无活动模型时 COM 范围读数的单位上下文尚未校准，不将该次范围原始值作为毫米尺寸结论。后续采用只读副本建立活动坐标上下文时出现 RPC 失败，记录于 `Runs/20261031_03`，不能判该项通过；按用户要求停止自行宿主测试，保留证据。
- 用户确认：“放置本身没有问题”。此为用户实测反馈，仅确认普通放置，不推定不同角度、尺寸、Undo/Redo、保存重开或原生关联全部通过。
- 用户明确：“安装原点是我自己增加那个圆柱的底部圆心，我将其视为执行结构连接杆与阀门外表面的交点”。后续零偏移定位应使该圆心与阀门侧对应接触点重合，绕安装轴调整朝向时该点保持固定。
- 用户确认 CEL 基于刚才制作的型号。原 STEP 的 770 × 700 × 444 mm 仅为原执行机构包络；新增连接几何后的总高不沿用 444 mm。原 STEP 的厂家安装面尺寸仍未核实；用户现指定的是本项目使用的定位约定，不作为厂家连接尺寸认证。
- 库内“气动”命名与原模型“电动装置”描述不一致，原始文件保留，不能依据该单元名自动选择原生气动/电动 EC 类。
- 测试分工：Agent 准备代码、方法和预期效果；用户执行 OPM 宿主测试并反馈。未重新授权前不自行启动或操作宿主测试。

## 13. 原生手轮换外形验证原型（2026-10-31）

用户指定优先验证“常规手轮保留原生交互、外形改成 CEL”。已实现独立开发 AddIn `ValveActuatorCelCheck.dll`，不修改已有 `HAND_WHEEL` Schema/处理器、不部署到宿主目录、不替换主插件。主工程仅增加本验证目录的源码排除项。

磁盘契约脚本 `Development/ValveActuatorCelValidation/Check-HandwheelContract.ps1` 的 13 项检查通过，证据见同目录 `handwheel-contract.json`：`HAND_WHEEL → MANUAL_VALVE_OPERATING_DEVICE → VALVE_OPERATING_DEVICE`；手动基类含 `Geometry/binary`；手轮使用 `Handwheel`/`TopworksPlacementTool`/`Topwork`；`VALVE_HAS_VALVE_OPERATING_DEVICE` 为前向 embedding 关系，源 PIPING_COMPONENT、目标 VALVE_OPERATING_DEVICE，双方基数均 `(0,1)`。这些仅为本机磁盘 Schema 契约。

原型两条命令：

- `ACTUATORCHECK PROBE`：读取所选件及正反向关系、实例 ID、类名、安装变换、Geometry 长度/哈希和图形范围；不写模型。
- `ACTUATORCHECK SWAP`：选择已关联父阀门的普通 HAND_WHEEL 独立实例和已正确摆放的当前 CEL；把源 CEL 的直接图形转到原手轮局部坐标，尝试 `SetNonParametricElement` + `BMECObjectWriter.Serialize` 原位保存。保留实例及原关联；不调用 Create、不新增关系。若宿主不允许切换几何模式则拒绝。成功重读后才在同一撤销事务删除输入 CEL，避免叠图；失败回滚并核对原件、Geometry 和源 CEL。

使用现有原生安装架，手动摆好的 CEL 表达相对该架的实际局部偏移；本轮不自动把阀杆端点当作用户定义的外表面交点。若手轮与阀体共用根元素，则停止该独立实例路线并要求保留日志，而不覆盖阀体图形。

本原型刻意保留 HAND_WHEEL 业务身份，只用于交互试验，不能作为正式电动/气动分类、ISO 或材料统计已经正确的证明。句柄所有权未取得公开文档保证，验证包固定保留每次提交的描述符至进程退出，最多 8 次，禁止提交后单独卸载 DLL，允许 OPM 正常退出。正式产品须进一步验证并收敛此生命周期。

验证包与主工程独立输出的 Release 编译均为 0 警告、0 错误；未运行 OPM 宿主、未修改安装目录、Schema 或业务 DGN。完整用户步骤和逐项预期效果见 [手轮验证包说明](../Development/ValveActuatorCelValidation/Prototype/README.md)。

## 14. 用户 V1 实测失败及 V2 接续（2026-10-31 20:34）

用户已运行 V1。日志及备份位于 `Development/ValveActuatorCelValidation/Runs/20261031_UserHandwheelSwapFailed/`；[失败分析](../Development/ValveActuatorCelValidation/Runs/20261031_UserHandwheelSwapFailed/结论.md)记录实例、范围和精确阶段。加载 DLL 的 MVID 与日志一致。

真实样本为手轮 HAND_WHEEL/图元5727、父蝶阀 BUTTERFLY_VALVE/图元1713，关系 `VALVE_HAS_VALVE_OPERATING_DEVICE` 已读到；两者独立根。CEL/图元4417的14直接图形和局部转换已通过本次命令的前置检查。关键失败为 `AfterSetNonParametricElement.IsParametric=True`，保护分支在 Serialize 之前停止，随后 `RollbackVerified=true`。本轮没有执行几何序列化或源CEL删除，不能解释为CEL导入失败或关联失败，也未测到移动/重生成/重开。

原假设“给现有参数化对象设置几何即可切换模式”已被该样本否定，不重复要求用户运行 V1、不删除该保护继续写。两基点在本次阀门局部约相差235mm，仍不能直接把手轮原点视作用户定义的表面接触点。

V2 采用公开构造入口 `new BMECObject(existingHandwheelInstance, true)`，在构造时明确指定非参数化模式，保留原手轮变换。仍不调用 Create、不新增关联、不修改Schema。V2分别记录构造、设置几何、序列化、默认重读、文档缓存重读状态；只有持久 Geometry、模式、身份、父关系和包络均符合才消耗源CEL并提交，任一失败回滚。显式包装器能显示几何不代表模式已保存，默认/缓存重读回到参数化时必须拒绝。

V2 为独立 `ValveActuatorCelCheckV2.dll`、命令 `ACTUATORCHECK2 PROBE/SWAP`、独立日志目录 `ValveActuatorCelCheckV2`；编译0警告0错误，未启动或操作宿主。PROBE补充显式构造只读模式及端口点坐标。若V2仍不接受持久非参数化模式，再研究独立测试执行机构类的Create3DElements回调，不全局替换原手轮处理器。新版[操作说明](../Development/ValveActuatorCelValidation/Prototype/README.md)要求退出OPM释放V1资源后重开验证。

## 15. 按现行管夹机制改用参数化几何回调（V3）

用户要求对照“支架位置外形改为自建模型”的方案。已核实两代实现区别：旧版存在非参数化SUPPORT_LOCATION；现行管夹采用继承SUPPORT_LOCATION的SSP_PIPE_CLAMP，并在`NativePipeSupportComponent : Supports`中重写`Create3DElements()`，保留原生参数化交互，通过Modeling创建属性指定自定义处理器。V1/V2的非参数化模式切换没有复用这个现行机制，V2暂缓。

本机SDK的`Handwheel.Create3DElements()`同样为public virtual。已新增`Development/ValveActuatorCelValidation/CallbackPrototype/`：公开`CelHandwheelComponent : Handwheel`，继承原生Setup，只覆盖三维几何回调，返回嵌入DLL的固定版本CEL的原生ElementHolder克隆。组件本身不调用SetNonParametricElement、不转非参数化。模板按文档/模型上下文缓存，初次通过BMApplication.GetCellElement读入固定资源，以后回调克隆；不逐次附加切换外部CEL库。

隔离测试类`SSP_CEL_HAND_WHEEL`继承HAND_WHEEL，保留Topwork/TopworksPlacementTool和VALVE_HAS_VALVE_OPERATING_DEVICE关系。`Prepare-TestSchema.ps1`仅在工作区生成两个Schema副本，只新增测试类和资源版本属性；检查全部原有节点及HAND_WHEEL定义不变并记录源文件哈希。当前未修改原工作集、未在OPM加载新类；XML预检不是Bentley加载验收。

独立DLL`ValveActuatorCallbackCheck.dll`提供`ACTUATORCALLBACK CREATE/PROBE`。CREATE首轮接受没有执行机构的原生阀门和已定位CEL；以CEL底部原点和方向创建参数化测试Topwork。新实例、唯一父关系、处理器、参数化状态和外形包络重读成功后才同事务删除输入CEL，失败回滚核验。现有手轮不被代码删除或全局改造，本轮先验证继承的手轮机制，已有执行机构替换留待后续。

CEL原始SHA256与DLL嵌入资源一致，编译元数据确认派生Handwheel并重写Create3DElements；V3及主工程独立输出Release均0警告0错误。测试环境定义、DLL加载、创建、父阀门随动、重生成、Undo/Redo、退出重开仍由用户验证，不提前判通过。完整步骤及预期见[参数化回调验证说明](../Development/ValveActuatorCelValidation/CallbackPrototype/README.md)。

## 16. V3回调已运行，V4直接使用官方放置工具

用户21:08、21:09日志证实V3参数化CEL几何回调已成功返回，NativeCreateStatus=0；随后关系检查失败并RollbackVerified=true。因此看起来没有新件保留。原日志未分别记正反向数量，不能排除查询范围/缓存因素，更不能把结果解释为CEL回调未运行。日志、源码/DLL备份及[分析结论](../Development/ValveActuatorCelValidation/Runs/20261031_V3CallbackSucceededRelationFailed/结论.md)已保留。

用户明确要求“激活命令，然后选择阀门”的官方操作。V4使用本机公开SDK入口`BMECApi.Instance.StartPlacement(component)`，component由既有测试类解析为TopworksPlacementTool及CelHandwheelComponent。只提供待放实例和外形，点选阀门、安装架、关系、方向确认及取消交由官方工具；插件代码不再设置RelatedInstance、不手工Create/Serialize、不安装自定义点取工具、不删除普通CEL。旧CREATE命令仅为PLACE别名，旧两件预选流程已移除。

启动命令`ACTUATORCALLBACK PLACE`先清空旧选择集，保留官方操作提示；命令返回仅表示启动请求返回。放置后再用PROBE从图元加载完整关系，六参数查询明确包含派生类，同时记录正反向数量和RawRelation。后续必须由实际交互及持久化关系判通过，不把place启动日志作为关联成功证明。

DLL程序集名/处理器类名保持V3兼容，版本升至4.0.0，无Schema修改需求。V4及主工程独立输出Release均0警告0错误；未操作宿主。用户只需退出OPM更新同名验证DLL，再激活命令点阀门。详细[官方放置V4操作说明](../Development/ValveActuatorCelValidation/CallbackPrototype/README-V4.md)。原生安装架是否与用户指定外表面交点一致，仍需根据新交互结果校核偏移。

## 17. 用户确认 V4 放置成功，V5 改以齿轮箱为基准

用户反馈“nice，成功了，是可以放置的”，同时指出手轮只有一个位置调整按钮，要求改用 GEARBOX_OPERATOR。该反馈仅确认官方流程能够放置，没有将双向关联、随动、Undo/Redo、重生成与重开全部判通过。成功版本源码、DLL、启动日志和反馈备份于 `Runs/20261031_V4PlacementUserConfirmed`。

本机 Schema 确认 GEARBOX_OPERATOR 同样继承 MANUAL_VALVE_OPERATING_DEVICE，使用 `GearBoxOperatorScript`、Topwork 和 TopworksPlacementTool；包含 TOTAL_HEIGHT、箱体三项尺寸、手轮四项尺寸及 HANDLE_OFFSET 九个原生字段。SDK 元数据确认 Setup 和 Create3DElements 可覆写，GearBoxOperatorDraw 在原点生成方向(-1,0,0)、朝向(0,0,1)的点串标记，然后生成实体。

V5新增 `CelGearboxComponent : GearBoxOperatorScript`，继承Setup，三维回调返回固定CEL克隆及上述原生标记，不生成原生箱体/手轮实体。新增 `SSP_CEL_GEARBOX_OPERATOR` 继承 GEARBOX_OPERATOR；保留此前手轮类与处理器，已有手轮件不会自动转换。PLACE/CREATE默认齿轮箱，GEARBOX显式同路，HANDWHEEL保留旧路线；全部继续通过官方StartPlacement点阀门。

本版为固定整体CEL，不响应原生箱体尺寸或局部手轮偏移变形。原生字段初始化为1、HANDLE_OFFSET及ANGLE为0，仅满足Setup输入，不作为实际执行机构尺寸。若某个原生按钮只修改这些尺寸而不修改整体安装变换，需要后续明确映射；不能宣称仅继承齿轮箱基类就已获得全部按钮及效果。PROBE增加九项参数和ANGLE等记录，用于比较操作前后。

Prepare-TestSchema新增BaseClassName参数，齿轮箱副本只追加新类，全部旧节点（包括原生齿轮箱和已装手轮测试定义）保持；记录源哈希并在保存回读后再次核对旧节点。未改实际工作集Schema、已加载DLL或DGN。V5和主工程独立输出Release均0警告0错误，资源仍为原CEL哈希。用户更新DLL及两份Schema后，核验原生齿轮箱对照按钮、位置/方向实际变化、安装圆柱底部圆心、关联及随动，具体步骤见[V5说明](../Development/ValveActuatorCelValidation/CallbackPrototype/README-V5.md)。

## 18. V6：先选 CEL 再安装的停靠界面

用户要求先选择哪个CEL再放置。新功能接入主插件首页valve-actuator，复用现有停靠工作区、ModelingTheme、PrototypeChrome、CelLibraryReader和真实预览；选择文件及库内单元后，点击开始冻结整个文件快照并校核模型，官方StartPlacement负责点阀门、方向与确认。放置中锁选项，结束后可换选。旧ACTUATORCALLBACK命令仍为历史固定资源路线。

新增SSP_CEL_VALVE_ACTUATOR继承GEARBOX_OPERATOR，主插件处理器CelValveActuatorComponent保留GearBoxOperatorScript.Setup，回调返回该实例的CEL及原生方向标记。每实例保存SSP_CEL_VERSION/NAME/SOURCE/SHA256/DATA/TOKEN；DATA为完整库文件binary，SOURCE只追溯，回调从DATA恢复哈希缓存，不读全局当前选择、不回退固定CEL。当前16MiB及单位/原点限制见[操作说明](阀门执行机构CEL选择界面.md)。整个库按件保存会增加DGN体积，正式驱动类型与BOM/ISO分类尚未据此确认。

STEELPROBE ACTUATOR打开界面；ACTUATORCHECK从所选图元加载完整关系并含派生类查询，记持久数据哈希/单元名/字节数、参数化状态/处理器、变换与原生参数。退出本页只结束带本请求Token的工具，失败保留页面；验证期原生包装/模板有界保留，持有资源时拒绝命令卸载，正常宿主退出不调用销毁中的放置API。

准备脚本-SelectableCel只追加新类至两份Schema副本，旧节点及保存回读保持，未安装实际Schema/DLL。主插件不内嵌固定阀门CEL。38项快照/属性协议/真实XAML及四档DPI检查、首页纯计算/83项WPF、68项停靠检查通过；EC/CAD用替身，不代表实际二进制保存或官方放置通过。授权/无授权主工程独立编译均0警告0错误，Agent未运行OPM。用户更新主插件及两份Schema后，验证不同CEL互不影响、原文件移走后重开/重生成、关联/随动/调整及Undo/Redo。
