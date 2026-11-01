# Schema 增补工具 · Fluent 版（SchemaPatcherFluent.exe）

`Deployment/SchemaPatcher` 的 Fluent 风格界面版（PySide6 + FluentQt），旧的 tkinter 版保留不动。检查、备份、写入、回滚的业务逻辑直接复用 `../SchemaPatcher/schema_patcher`，这里不复制规则。

## 使用

1. 保存并关闭 OPM（OPM 在运行时写入会被拒绝）。
2. 双击 `dist\SchemaPatcherFluent.exe`。
3. 顶部填 Schema 目录（`…\Standards\OpenPlant\Schemas`）、备份文件夹，选修改内容，点“检查”。
4. 台账按文件分组列出每一处改动：行号、状态（新增/修改/冲突/已具备）、位置、说明；选中一行，右侧显示改前改后或插入内容。窄窗口下选中行按回车或双击查看。
5. 没有冲突时“执行修改”可用，确认后先备份再写入；写入后自动复查，写入的行标为“已写入”。全部已具备时会提示无需修改。
6. “保存日志”另存本次会话的完整记录；每次写入的 `.bak`、`SchemaPatch.log`、`receipt.json` 在备份文件夹的 `SchemaPatch_<时间>_<内容>\` 下。

首次启动沿用 tkinter 版保存的目录和选择，之后单独保存到 `%APPDATA%\SteelSectionProbe\SchemaPatcherFluent\settings.json`。

## 结构

按 build-fluentqt-gui 技能的 PySide6 完整模板分层（`.fluentqt/architecture.json`）：

| 目录 | 职责 |
| --- | --- |
| `src/domain` | 台账快照等纯数据，不依赖 Qt |
| `src/application` | 检查/写入流程与视图状态（只用 QtCore，后台线程执行） |
| `src/infrastructure` | 适配 schema_patcher 引擎、设置存储 |
| `src/ui` | 外壳、台账页、组件、列表模型/委托、主题语义色 |
| `design/` | 设计简报、三套设计稿与选定结果（B 增补台账） |

## 打包与检查

```powershell
.\build_exe.ps1                                   # 生成 dist\SchemaPatcherFluent.exe（约 41 MB）
.\.venv\Scripts\python.exe -B tests\domain\test_ledger.py
.\.venv\Scripts\python.exe -B tests\application\test_controller.py
.\.venv\Scripts\python.exe -B tests\infrastructure\test_gateway.py
.\.venv\Scripts\python.exe tests\ui\capture_evidence.py   # 驱动真实窗口截图到 tests\.evidence
```

FluentQt 需要 Python 3.11–3.13；本机 `C:\Python314` 是残缺安装，打包脚本默认用 Python 3.12。`.venv/`、`build/`、`dist/`、`tests/.work/`、`tests/.evidence/` 不入库。
