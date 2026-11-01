# Schema 增补工具（SchemaPatcher.exe）

给一个 OpenPlant 工作集的 Schema 补上本插件需要的类和字段。界面里选目录、选备份文件夹、选修改内容，先检查再修改；修改前自动备份，修改后输出记录。

规则与 `Deployment/Install-NativeSupportEditing.ps1`、`Install-PipeClampIsoTag.ps1` 一致：两边装出来的内容互相识别为“已具备”，可以混用。修改规则时两边同步，并跑 `Development/SchemaPatcherCheck` 的检查。

## 修改内容

| 下拉项 | 改哪些文件 | 做什么 |
| --- | --- | --- |
| 增加耳轴 | OpenPlant_3D / Modeling / Isoextractor | 自带耳轴三类（SINGLE/DOUBLE_PIPE_TRUNNION、SIMPLE_ELBOW_SUPPORT）加 `SSP_RECIPE`；创建属性改指向本插件 `NativePipeSupportComponent`；`IE_TAG=this.ALIAS` |
| 增加正式管夹 | 三份 | 新增隔离类 `SSP_PIPE_CLAMP`（继承 `SUPPORT_LOCATION`） |
| 修改轴测图出图 | Isoextractor | `SUPPORT_LOCATION` 增加 `BOM_LABELS`：`DEVICE_TYPE_CODE=SSPPC` 时引注取 `ALIAS`（管架编号），否则保持原表达式 |
| 增加自定义执行机构 | OpenPlant_3D / Modeling | 新增 `SSP_CEL_VALVE_ACTUATOR`（继承 `GEARBOX_OPERATOR`，6 个 CEL 快照字段）；创建属性复制自 `GEARBOX_OPERATOR`，处理器改为本插件 `CelValveActuatorComponent` |
| 全部 | 三份 | 依次执行以上四项 |

注意：“增加耳轴”改的是 OPM 自带类，改后该工作集所有耳轴（包括原生工具放的）都要本插件才能编辑；管夹和执行机构是新增隔离类，不影响原生构件。以上三类构件都依赖本插件的处理器，插件不在时编辑会报“找不到 SteelSectionProbe”。

## 使用

1. 保存并关闭 OPM（检测到 `OpenPlantModeler.exe` / `ustation.exe` 在运行会拒绝修改）。
2. 双击 `dist\SchemaPatcher.exe`。
3. **Schema 目录**：工作集的 `...\WorkSets\<工作集>\Standards\OpenPlant\Schemas`，里面要有三份 `.01.08.ecschema.xml`。
4. **备份文件夹**：不能放在 Schema 目录里面。
5. 选修改内容，点 **检查（只读）** 查看结果：蓝色“新增/修改”是要改的，绿色“已具备”是已经有的，红色“冲突/错误”需要人工处理。
6. 点 **执行修改**，确认后写入。全部已具备时会提示“当前选择的 Schema 文件已经具备这些字段，无需修改”，不会写文件、也不产生备份。
7. 重启 OPM 生效。

路径和上次的选择会记住（`%APPDATA%\SteelSectionProbe\SchemaPatcher\settings.json`）。

## 备份与记录

每次修改在备份文件夹下新建 `SchemaPatch_<时间>_<修改内容>\`：

- `<schema文件名>.bak`：修改前的原文件，逐字节一致；
- `SchemaPatch.log`：每一处改动的文件、XPath 位置、原文件行号、修改后行号、插入的完整内容或“字段：旧值 → 新值”；
- `receipt.json`：修改前后 SHA256、备份路径和改动清单。

**保存日志…** 把窗口里的状态和本次会话的详细记录另存为一个文件。

回退：关闭 OPM，把 `.bak` 去掉后缀覆盖回 Schema 目录。

## 安全规则

- 只在需要的位置插入或改值，其余字节（编码、BOM、换行、字符引用）原样保留。PowerShell 脚本是整份重写，会把属性里的 `&#xA;` 变成空格；本工具不会。
- 写入前在内存里完成全部修改并自检：重新检查必须全部“已具备”，未涉及的顶层节点必须逐字节不变，新增的顶层类必须与计划一致。
- 多个文件全部备份并校验后才逐个替换；任一文件失败，已写的文件自动从备份恢复。
- 检查之后文件被别的程序改过，拒绝写入，要求重新检查。
- 目标已有项目自定义内容（例如 `SUPPORT_LOCATION` 已有别的 `BOM_LABELS`、耳轴已指向其它组件）一律报冲突，不覆盖。
- 写入 ProgramData 被拒绝时，以管理员身份运行本工具。

## 命令行

不带参数打开界面；带参数走命令行（只在用 Python 运行源码时有输出）：

```powershell
python SchemaPatcher.py --schema-dir "<Schemas目录>" --feature all            # 只读检查
python SchemaPatcher.py --schema-dir "<Schemas目录>" --feature valve_actuator --backup-dir "<备份>" --apply
```

`--feature` 可选 `trunnion`、`pipe_clamp`、`iso_tag`、`valve_actuator`、`all`。退出码：0 成功或无需修改，2 有冲突，1 写入失败。

## 打包

```powershell
.\build_exe.ps1            # 默认用 %LOCALAPPDATA%\Programs\Python\Python312\python.exe
.\build_exe.ps1 -Python "<带 tkinter 的 python.exe>"
```

脚本在 `.build-venv` 里装 PyInstaller，输出 `dist\SchemaPatcher.exe`（单文件、无控制台）。`build/`、`dist/`、`.build-venv/` 不入库。只用标准库，运行 exe 不需要安装 Python。

## 检查

```powershell
cd ..\..\Development\SchemaPatcherCheck
python -B test_schema_patcher.py   # 合成夹具各分支 + 真实原始 Schema 与 PowerShell 结果比对/互认
python -B gui_smoke.py             # 驱动真实界面走一遍并截图到 obj\smoke
```

## 文件

| 文件 | 作用 |
| --- | --- |
| `SchemaPatcher.py` | 入口 |
| `schema_patcher/xmlspan.py` | 带字节位置的 XML 读取、插入/改值、结构比较 |
| `schema_patcher/features.py` | 四项增补的判定与修改规则 |
| `schema_patcher/engine.py` | 检查、自检、备份、写入、回滚、日志与收据 |
| `schema_patcher/gui.py` | tkinter 界面 |
| `schema_patcher/cli.py` | 命令行 |
| `build_exe.ps1` | 打包 |
