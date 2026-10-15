# A1 原生编辑试验清理（2026-10-15）

## 背景

`SSP_A1_NATIVE_TEST` / `STEELPROBE A1TEST` 是最早用于验证"原生支吊架 + 参数化操作柄 + 随管移动 + ISO 出图"的概念验证。该机制后来已沉淀到正式功能：

- 正式九类管夹 → `SSP_PIPE_CLAMP` + `NativePipeSupportComponent`
- 耳轴随动 → 自带耳轴三类（`SINGLE/DOUBLE_PIPE_TRUNNION`、`SIMPLE_ELBOW_SUPPORT`）

A1 试验对正式功能没有任何依赖，用户确认不再保留，予以彻底删除。

## 本目录内容

`改前源码/型钢构件及支吊架模型生成工具_CS/` 保存了删除/修改前的相关文件（含 A1 源码、Key-in、安装脚本、检查工程、被改动的文档与工程文件）。

## 删除项

- 源码目录：`App/OpenPlant/Domain/Infrastructure/Services` 下的 `A1NativeSupport/`
- Key-in：`Registration/Keyins.cs` 的 `A1Test`、`Registration/commands.xml` 的 `A1TEST`
- 部署脚本：`Deployment/Install-A1NativeEditingTrial.ps1`
- 检查工程：`Development/A1NativeSupportCheck/`
- 文档：`Docs/A1原生编辑与随动验证.md`、`Docs/A1原生关联试验.md`
- `Deployment/Install-NativeSupportSchema.ps1` 的 `A1Trial` 模式
- 主工程 `SteelSupportModeler.csproj` 的 `Compile Remove ... A1NativeSupportCheck`

## 保留（迁移到别处）

`NativeApiFakes.cs`、`ParametricSetupFakes.cs`、`Check-NativeEditingSchema.ps1` 是**共用替身/检查**（正式 `PipeClampIsoCheck` 也在用），已移入 `Development/PipeClampIsoCheck/`，并剥离 A1 相关片段。

## 注意

共用组件 `NativeParametricSupportGraphics`、`NativePipeSupportWriter`、`NativeSupportData/Elements` 等是正式功能在用，**未删除**。
