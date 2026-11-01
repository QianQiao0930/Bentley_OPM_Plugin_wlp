# CEL 手轮参数化几何回调验证（V3）

当前为[齿轮箱V5测试版](README-V5.md)。用户已确认V4官方放置可用；本页及下方V3状态为历史记录，V5不使用旧的“阀门+CEL预选”流程。

本页为V3历史操作。用户已实测CEL回调成功、手工Create后的关联校验失败并回滚；当前改用[官方工具V4流程](README-V4.md)，沿用已安装的测试定义，只更新DLL，不再要求预选阀门与CEL。

状态：按当前管夹方案的参数化几何回调机制实现；SDK Release 编译0警告0错误。尚未在 OPM 中运行，Schema 仅生成副本，原工作集文件没有修改。由用户执行宿主验证。V2 非参数化路线暂缓。

## 与管夹方案的对应关系

| 当前管夹 | 本轮手轮/CEL |
| --- | --- |
| `SSP_PIPE_CLAMP` 继承 `SUPPORT_LOCATION` | `SSP_CEL_HAND_WHEEL` 继承 `HAND_WHEEL` |
| `NativePipeSupportComponent : Supports` | `CelHandwheelComponent : Handwheel` |
| `Create3DElements()` 返回 Builder 外形 | `Create3DElements()` 返回 CEL 原生几何克隆 |
| `Support` / `PipeSupportPlacementTool` | 保留 `Topwork` / `TopworksPlacementTool` |
| 父管关联由原生体系处理 | `VALVE_HAS_VALVE_OPERATING_DEVICE` 关联父阀门 |
| 参数化组件保持参与宿主编辑和重生成 | 本轮也要求 `IsParametric=True`，不切换非参数化模式 |

回调继承原生手轮的 Setup，只覆盖三维几何。CEL 固定版本已嵌入 DLL，首次按文档上下文调用原生 `BMApplication.GetCellElement` 读入模板，此后克隆模板；不在每次移动/重生成时重复附加或切换外部 CEL。第一次会在 LocalAppData 释放带哈希的固定资源副本。原 ProgramData CEL 不参与后续回调。

此为隔离测试类；软件自带 `HAND_WHEEL` 及其他执行机构的定义和处理器不改。第一轮只验证三维及原生交互，不把该测试类作为正式电动执行机构的 ISO/BOM 分类。

## 准备测试定义

`PreparedSchemas/` 是根据以下工作集的当前文件生成的两个副本：

```text
C:\ProgramData\Bentley\OpenPlant 2024\Configuration\WorkSpaces\CINF_International_Projects_Workspace\WorkSets\CINF_F1263AA\Standards\OpsenPlant\Schema
```

只新增测试类和 `SSP_CEL_VERSION/int` 属性；Modeling 测试类的创建属性指向 `ValveActuatorCallbackCheck / ActuatorCallbackCheck.CelHandwheelComponent`，保留原生 Topwork handler。准备脚本核对所有原有节点及 HAND_WHEEL 节点不变，收据见 `preparation-receipt.json`。这只是 XML 预检，尚未经过 Bentley Schema 加载验证。

1. 正常退出 OPM，释放 V1/V2 的试验资源。
2. 确认实际要测试的工作集。优先在独立测试工作集使用这些定义。先备份该工作集的这两个 Schema 文件：

   ```text
   OpenPlant_3D.01.08.ecschema.xml
   OpenPlant_3D_Supplemental_Modeling.01.08.ecschema.xml
   ```

3. 若确实使用上述 CINF_F1263AA 工作集，且源文件哈希仍与收据一致，将 `PreparedSchemas/` 的两个 XML 副本放入测试工作集的对应 Schema 目录。**不要把不同工作集的完整 Schema 文件互相覆盖。** 若是其他工作集或文件已更新，用准备脚本针对实际目录重新生成，指定一个新的输出目录：

   ```powershell
   .\Prepare-TestSchema.ps1 -SourceSchemaDirectory '实际测试工作集的Schemas目录' -OutputDirectory '新的准备输出目录'
   ```

   脚本只准备副本，不安装、不改原文件、不启动 OPM。

4. 重开相应工作集，新建一个测试三维 DGN，使用与已测试样本一致的 `1000000 UOR/m` 分辨率。先加载 DLL：

   ```text
   mdl load "E:\Code\Bentley_Python_plugin\型钢构件及支吊架模型生成工具_CS\Development\ValveActuatorCelValidation\CallbackPrototype\bin\Release\net48\ValveActuatorCallbackCheck.dll"
   ```

恢复时，正常退出 OPM，将测试前备份的两个 Schema 文件恢复。含新测试类的 DGN 保留为测试产物，不把它当作恢复到旧定义后的兼容性证明。

## 创建与预期效果

1. 放一个原生蝶阀。为避免两套执行机构，本轮使用**没有手轮/执行机构的阀门**；若有原生手轮，在测试副本中先用原生命令删除。不会由代码删除或覆盖已有执行机构。
2. 放置你的“气动执行-DN800” CEL，按已确认的方法摆好：新增圆柱底部圆心位于阀门表面交点，圆柱轴线与安装轴一致。可先对原阀门运行 `ACTUATORCALLBACK PROBE`，预期正向执行机构关系为空。
3. 只选中阀门和这套 CEL，共两件，执行：

   ```text
   ACTUATORCALLBACK CREATE
   ```

   **预期：**创建一个参数化的 `SSP_CEL_HAND_WHEEL` 原生 Topwork，外形与摆好的 CEL 一致。读回唯一父阀门关系、参数化模式、自定义处理器和包络通过后，才在同一个撤销事务删除输入的普通 CEL，最终只剩一套外形。属性显示测试手轮类属于本轮预期。失败回滚并核对阀体、源 CEL 和无新增父关系；回滚未核实则停止继续使用该测试副本并保留日志。

   若提示找不到 `SSP_CEL_HAND_WHEEL` 或加载的处理器不对，是测试定义/程序集尚未进入宿主；先保留日志，不将该结果当作几何回调失败。

4. 选中新执行机构运行：

   ```text
   ACTUATORCALLBACK PROBE
   ```

   **预期日志：**`Class=SSP_CEL_HAND_WHEEL`、`IsParametric=True`、`Component=ActuatorCallbackCheck.CelHandwheelComponent`，反向关联到正确阀门；同时出现独立 callback 日志，记录 CEL 克隆而非调用普通手轮外形。

5. 只选阀门，原生平移、旋转并移回；再使用原生更新/重生成操作。

   **预期：**CEL 外形随动，底部圆心保持与阀门表面同一局部交点；重生成仍为 CEL，不恢复圆形手轮、不重复生成。回调日志可证明宿主实际进入我们实现的 Create3DElements。若发生跳点或偏移，记录移动前后 PROBE 与 callback 日志；自动安装架和相对偏移仍需据此校核，不能用移动时同时选中两件替代父阀门随动测试。

6. 撤销移动，再撤销创建；重做。

   **预期：**撤销创建移除原生执行机构和关联，恢复输入 CEL；重做恢复一套原生 CEL 执行机构。

7. 保存、正常退出 OPM、重开同一测试环境。保持这个 DLL 可被宿主找到（本轮可重新加载它），再移动阀门和重生成。

   **预期：**依赖配置好的自定义处理器及嵌入 DLL 的固定 CEL 版本恢复，无需再运行 CREATE；不依赖进程内的旧几何缓存或原 ProgramData CEL。正式部署仍需固定 DLL 路径及资源版本，本轮不宣称脱离自定义 DLL 后仍可编辑。

## 日志及边界

```text
%LOCALAPPDATA%\SteelSectionProbe\logs\ActuatorCallbackCheck\
```

create、probe、callback 分别保存独立文件。请反馈首次 CREATE 与 callback 日志，以及只移动阀门、重生成、保存重开的结果。

当前固定 CEL 版本和资源哈希，限同源 `1000000 UOR/m` 模型、源单元额外缩放为1、14个直接图形、活动可写三维模型、空阀门。本轮复用参数化几何回调机制；自动点取阀门安装点、已有执行机构替换、其他型号和正式统计/ISO 未完成。每进程最多8次创建和8个几何模板上下文，正常退出 OPM 释放开发期资源；正式产品须进一步收敛模板及对象生命周期。

构建：

```powershell
dotnet build Development/ValveActuatorCelValidation/CallbackPrototype/ValveActuatorCallbackCheck.csproj -c Release
```
