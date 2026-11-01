# 原生手轮换 CEL 外形：V2 显式非参数化构造验证

状态：V1 已由用户测试，失败点为设置几何后 `IsParametric` 仍为 True，尚未调用序列化；回滚检查通过。V2 使用不同的显式构造入口，本机 OPM 24.00.03.53 SDK 编译通过，0 警告、0 错误；V2 尚未在 OPM 中运行。宿主操作由用户执行。

## 验证原理

先由 OPM 原生命令把普通 `HAND_WHEEL` 手轮装到阀门上，沿用它已经建立的 `VALVE_HAS_VALVE_OPERATING_DEVICE` 关联。V2 对同一实例显式构造 `new BMECObject(wheel, true)`，核对非参数化模式后，再把已定位 CEL 的局部图形交给 `SetNonParametricElement` 和 `BMECObjectWriter.Serialize`。原手轮实例 ID、类、安装变换及父阀门均要重读核对；不调用 `Create`、不新增关系，不修改任何 Schema 或全局手轮处理器。

`HAND_WHEEL` 继承的手动执行机构基类有 `Geometry/binary`；这是候选接口依据。V2 要求显式构造时即为非参数化模式，并要求写入后按默认方式重读及存在的文档缓存都保持该模式、Geometry 非空、范围匹配。任一项失败则停止并回滚。特别是默认重读仍为参数化时，不以显式包装器显示正常作为成功；随后转向独立测试类的几何回调，不放宽检查硬写。

第一轮保留 `HAND_WHEEL` 业务身份，只验证外形和交互。它不会因此变成正式电动/气动执行机构；ISO、BOM 及正式类别另行验收。

## 用户操作

1. 先正常退出 OPM，释放 V1 试验资源；重开测试 DGN 副本。若 V1 的原手轮和输入 CEL 已恢复，可直接继续使用。否则重新用原生命令给阀门安装普通手轮，并放置 CEL。先确认只移动阀门时，原手轮能随动。
2. 使用已经验证正常的 CEL 放置功能，放置“气动执行-DN800”。将其摆到目标安装位置：新增圆柱底部圆心落在你指定的阀门外表面交点，轴线和朝向正确。此时 CEL 与原手轮暂时重叠属于测试准备状态。
3. 在 OPM 键入窗口加载本验证 DLL，完整路径可以放在引号中：

   ```text
   mdl load "E:\Code\Bentley_Python_plugin\型钢构件及支吊架模型生成工具_CS\Development\ValveActuatorCelValidation\Prototype\bin\Release\net48\ValveActuatorCelCheckV2.dll"
   ```

4. 只选中原生手轮，执行：

   ```text
   ACTUATORCHECK2 PROBE
   ```

   预期日志包含 `Class=HAND_WHEEL`、手轮实例 ID、变换以及反向的 `VALVE_HAS_VALVE_OPERATING_DEVICE` 和一个父阀门。若选中了阀体，日志会显示阀门类及正向关系；重新选择手轮。若两者共用同一根图元，本原型停止，需根据日志调整路线。

5. 同时选中这只原生手轮和已经摆好的 CEL（共两件，不选阀体），执行：

   ```text
   ACTUATORCHECK2 SWAP
   ```

   **预期效果：**普通手轮外形被 CEL 外形替代，位置与手动摆放时一致；选择属性仍为原手轮。作为输入的普通 CEL 在成功后被同一事务删除，画面最终只有一套执行机构。原型重读核对 Geometry 非空、非参数化模式、实例和关联保持、包络匹配及父阀门包络未变，失败则回滚并检查原手轮与源 CEL 恢复。失败提示若指出回滚未核实，停止使用此测试副本并保留日志。

6. 成功后只选父阀门，使用 OPM 原生命令平移、旋转，再移回。

   **预期效果：**CEL 外形跟随阀门；连接圆柱底部圆心始终保持在同一局部表面交点；不重复生成、不中途恢复普通手轮。不要同时选中执行机构来代替这个测试。

7. 使用你平时的原生更新/重生成操作，并检查手轮属性编辑触发更新后的外形。

   **预期效果：**仍为 CEL 外形。若恢复普通手轮、消失、漂移或多出一套，本路线在该场景失败。第一轮不把原手轮直径/杆长参数映射为 CEL 的缩放参数。

8. 撤销后续移动，再撤销这次 SWAP；随后重做。

   **预期效果：**撤销 SWAP 同时恢复原手轮外形和输入 CEL；重做后再次只保留一套原生关联的 CEL 外形。

9. 保存测试 DGN，正常退出 OPM，再重开。先不加载验证 DLL，检查外形并只移动阀门；随后可加载 DLL 再运行 PROBE 留证据。

   **预期效果：**不需要再次 SWAP；原生手轮类及保存的 Geometry 足以恢复 CEL 外形和随动。若只能在当前进程或加载验证 DLL 后工作，持久化验收未通过。原始外部 CEL 不参与移动回调，但脱离 CEL 的完整验证仍待独立测试副本执行。

## 日志与反馈

每条命令独立记录于：

```text
%LOCALAPPDATA%\SteelSectionProbe\logs\ValveActuatorCelCheckV2\时间目录\probe.log 或 swap.log
```

请优先反馈 PROBE 和第一次 SWAP 日志，以及移动、重生成、重开三个结果。日志中“命令完成”仅表示本条命令完成，不能代替后续场景通过。

为保持尚未核实的原生句柄所有权安全，原型为每次尝试固定保留少量几何描述符，单进程最多 8 次 SWAP。执行过 SWAP 后请正常退出 OPM 释放，不单独卸载验证 DLL；退出 OPM 本身不受阻止。该限制仅属于本轮开发验证包。

## 构建与范围

```powershell
dotnet build Development/ValveActuatorCelValidation/Prototype/ValveActuatorCelCheck.csproj -c Release
```

使用 .NET Framework 4.8、x64。Bentley 程序集均为 `Private=false`，包内仅提供本验证 DLL/PDB；主工程排除本目录全部检查源码。主工程也已编译通过，验证输出位于独立 `bin/Release/ActuatorValidationBuild`，没有部署到宿主目录。

本轮固定当前 CEL 的 14 个直接子图形、活动可写三维模型、普通 `HAND_WHEEL` 独立实例及唯一父阀门。自动寻找阀门表面安装点、新建执行机构、其他阀门/执行机构类型、正式 UI、ISO/BOM 均不在本轮通过范围。
