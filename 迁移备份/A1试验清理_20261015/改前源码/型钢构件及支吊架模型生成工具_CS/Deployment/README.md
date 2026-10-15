# Deployment 脚本说明

本目录存放 `SteelSupportModeler.csproj` 的**编译产物部署**与**工作集 Schema 安装**脚本。它们只负责"把编译好的 DLL 放到该放的地方"和"改造工作集 schema"，不包含业务逻辑。

## 通用约定（所有 Schema 安装脚本都遵守）

- **默认只读预览**：不加 `-Apply` 时只打印将要写入的内容，不改任何文件。
- **`-Apply` 必须配 `-BackupDirectory`**：无备份目录一律拒绝写入。
- **写前备份 + SHA256 校验**，全部改动准备并校验通过后才替换；任一失败自动回滚；备份校验失败即停止。
- **冲突拒绝覆盖**：目标已有项目自定义内容时抛错，不静默覆盖。
- **重复运行幂等**：已安装且一致时只报告"已安装/无需修改"，不产生新备份。
- **必须先关闭 OPM**（`OpenPlantModeler` / `ustation` 进程不得在运行），否则拒绝或写入失败。
- 需要重启 OPM 后新放的元素才生效。

两类脚本的参数形态不同：

- 多数安装脚本用 `-SchemaDirectory`（工作集 `Standards/OpenPlant/Schemas` 目录，一次处理三份 schema）；
- 两个 `*IsoTag.ps1` 用 `-SchemaPath`（指向**单个** Isoextractor 的 `.ecschema.xml` 文件）。

---

## 一、编译与部署 DLL（不碰 Schema）

| 文件 | 作用 |
| --- | --- |
| `build_version.ps1` | 编译工程到隔离目录并打印 SHA256。`-Edition Licensed`（默认）→ `EnableLicensing=true`、输出 `bin\Release\net48_full\`；`-Edition Unlicensed` → `EnableLicensing=false`、输出 `bin\Release\Unlicensed\`。**只编译，不覆盖 OPM 正在加载的 DLL**。 |
| `install_new_version.ps1` | 把 `bin\Release\net48_full\SteelSectionProbe.dll` 复制回常规产物 `bin\Release\net48\SteelSectionProbe.dll` 并校验 SHA256 一致；被 OPM 占用时失败并提示先关闭。**只在本工程 `bin` 内操作，不涉及 OPM 安装目录。** |
| `install_new_version.cmd` | 上面 ps1 的批处理包装，供双击运行。 |

> 注意：部署到 OPM 实际加载目录（`mdlapps`）属于宿主环境操作，不在本目录脚本范围内，需手动替换 DLL/PDB。

---

## 二、工作集 Schema 安装

### 2.1 核心脚本（真正做改动的两个）

| 文件 | 参数 | 作用 |
| --- | --- | --- |
| `Install-NativeSupportSchema.ps1` | `-SchemaDirectory -Mode A1Trial\|PipeClamp\|Trunnion -BackupDirectory -Apply` | **共用核心**：向基础 / Modeling / Isoextractor 三份 schema 各**新增一个隔离类**。`A1Trial`→`SSP_A1_NATIVE_TEST`（+`SSP_A1_DN`/`SSP_A1_OPENING`）＝A1 试验；`PipeClamp`→`SSP_PIPE_CLAMP`（+`SSP_RECIPE` string）＝正式管夹；`Trunnion`→`SSP_TRUNNION`（+`SSP_RECIPE`）＝耳轴早期隔离类方案（**已被自带类方案取代，仅保留供离线检查**）。不修改自带 `SUPPORT_LOCATION`。 |
| `Install-TrunnionStockParametric.ps1` | `-SchemaDirectory -BackupDirectory -Apply` | 改造**自带**耳轴三类（`SINGLE_PIPE_TRUNNION` / `DOUBLE_PIPE_TRUNNION` / `SIMPLE_ELBOW_SUPPORT`）：基础 schema 各加 `SSP_RECIPE`；Modeling 的 `CREATION_ATTRIBUTE` 指向本插件 `NativePipeSupportComponent`（否则没有操作柄）；Isoextractor `IE_TAG=this.ALIAS`。**保留原 `ClassMap`（`SUPP_TRUNNION`/`SUPP_ELBOW`）与其它属性。** |

### 2.2 薄入口（只是把上面对应脚本调起来）

| 文件 | 等价于 |
| --- | --- |
| `Install-PipeClampNativeEditing.ps1` | `Install-NativeSupportSchema.ps1 -Mode PipeClamp` |
| `Install-A1NativeEditingTrial.ps1` | `Install-NativeSupportSchema.ps1 -Mode A1Trial` |
| `Install-TrunnionNativeEditing.ps1` | `Install-TrunnionStockParametric.ps1` |
| `Install-NativeSupportEditing.ps1` | **统一入口**（2026-10-15 新增）：一次执行 `Install-TrunnionStockParametric.ps1` + `Install-NativeSupportSchema.ps1 -Mode PipeClamp`，即同时装**自带耳轴三类**与**正式管夹类**；`-Apply` 时额外输出三份 schema 的最终 SHA256 统一收据。只做编排，不复制安装逻辑。 |

### 2.3 Isoextractor 引注补丁（针对单个 schema 文件）

| 文件 | 参数 | 作用 |
| --- | --- | --- |
| `Install-PipeClampIsoTag.ps1` | `-SchemaPath -BackupDirectory -Apply` | 给 `SUPPORT_LOCATION` 补 `BOM_LABELS`，`IE_TAG` 用条件表达式：当 `DEVICE_TYPE_CODE="SSPPC"` 时取 `ALIAS`，否则回落原表达式。用于**旧的非参数化管夹件**引注（正式方案改用 `SSP_PIPE_CLAMP` 后一般不需要）。 |
| `Install-TrunnionStockIsoTag.ps1` | `-SchemaPath -BackupDirectory -Apply` | 给自带耳轴三类补 `IE_TAG=this.ALIAS`，不动 `ClassMap`/`IE_Component`。是 `Install-TrunnionStockParametric.ps1` 中 Isoextractor 部分的**单独版本**。 |

---

## 三、我该跑哪个？（决策表）

| 场景 | 用哪个 |
| --- | --- |
| 只更新插件 DLL | `build_version.ps1` → `install_new_version.ps1`（或 `.cmd`） |
| 首次给工作集装正式功能（耳轴 + 管夹一起） | `Install-NativeSupportEditing.ps1` |
| 只装正式管夹 `SSP_PIPE_CLAMP` | `Install-PipeClampNativeEditing.ps1` |
| 只装自带耳轴三类参数化 | `Install-TrunnionNativeEditing.ps1` |
| 装 A1 试验类（`STEELPROBE A1TEST` 用） | `Install-A1NativeEditingTrial.ps1` |
| 修旧非参数化管夹件的 ISO 引注 | `Install-PipeClampIsoTag.ps1 -SchemaPath <Isoextractor.xml>` |
| 单独补自带耳轴三类的 ISO 引注 | `Install-TrunnionStockIsoTag.ps1 -SchemaPath <Isoextractor.xml>` |

---

## 四、常用命令

编译：

```powershell
.\Deployment\build_version.ps1 -Edition Licensed
.\Deployment\build_version.ps1 -Edition Unlicensed
```

统一安装（预览 → 安装）：

```powershell
# 只读预览
.\Deployment\Install-NativeSupportEditing.ps1 -SchemaDirectory '<工作集...\Standards\OpenPlant\Schemas>'

# 关闭 OPM 后正式写入
.\Deployment\Install-NativeSupportEditing.ps1 `
  -SchemaDirectory '<工作集...\Standards\OpenPlant\Schemas>' `
  -BackupDirectory '<备份目录>' -Apply
```

常用工作集 schema 目录（本机示例）：

```text
C:\ProgramData\Bentley\OpenPlant 2024\Configuration\WorkSpaces\
  CINF_International_Projects_Workspace\WorkSets\CINF_F1263AA\Standards\OpenPlant\Schemas
```

三份被处理的 schema 文件固定为：

```text
OpenPlant_3D.01.08.ecschema.xml
OpenPlant_3D_Supplemental_Modeling.01.08.ecschema.xml
OpenPlant_3D_Supplemental_Isometrics_Isoextractor.01.08.ecschema.xml
```

---

## 五、相关离线检查

以下检查工程在隔离的 `obj` XML 夹具上运行上面的**真实**安装脚本（不触碰真实工作集），验证预览不改文件、无备份被拒、备份字节一致、幂等、冲突拒绝与回滚：

- `Development\A1NativeSupportCheck\Check-NativeEditingSchema.ps1 -Mode A1Trial|PipeClamp`（`Trunnion` 模式转调下面那个）
- `Development\PipeClampIsoCheck\Check-TrunnionStockIsoTag.ps1`

因此这些脚本名与参数被检查引用，**改名/改参数需同步更新对应检查**。

---

## 六、回退

每个 `-Apply` 都会在 `-BackupDirectory` 留下：

- `<schema文件名>.<guid>.bak`：安装前的**字节级**备份；
- `*.json` 收据：记录 `BeforeSHA256` / `AfterSHA256` / `Schema` / `Backup` 等。

回退时关闭 OPM，把 `.bak` 覆盖回对应 schema 文件即可，再重启 OPM。
