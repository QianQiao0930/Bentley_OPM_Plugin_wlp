# V4：激活官方执行机构工具，再点选阀门

V4 DLL 版本4.0.0，SDK编译0警告0错误；用户随后已确认官方流程能够放置（未据此判定所有关联、随动及重开项目通过）。原有V3测试类定义继续使用，无需重新修改Schema。当前新增[齿轮箱V5候选](README-V5.md)，V5首次使用须增加齿轮箱测试Schema；本页保留V4操作记录。

## 这次改了什么

V3用户日志已经证明参数化 `Handwheel.Create3DElements()` 回调能够返回CEL，原生Create返回0；但关联检查失败，随后RollbackVerified=true，所以画面看起来没有变化。不能将这次结果解释为“CEL几何回调失败”。

V4保留已经跑到的CEL几何回调，改用本机公开SDK的：

```csharp
BMECApi.Instance.StartPlacement(component);
```

component的放置工具由现有测试Schema解析为 `TopworksPlacementTool`。插件只提供执行机构实例及CEL外形；阀门点选、安装架、方向、确认、关系创建和取消交给官方放置工具。不再由插件设置RelatedInstance、调用Create/Serialize或删除源CEL，不安装自定义点取工具。

## 更新一次DLL

1. 正常退出OPM。
2. 用本包的 `ValveActuatorCallbackCheck.dll`（以及PDB）更新之前加载的同名验证DLL。上一轮日志中的位置是：

   ```text
   E:\Code\Bentley_Python_plugin\型钢构件及支吊架模型生成工具_CS\bin\Release\net48\ValveActuatorCallbackCheck.dll
   ```

   也可在重开OPM后直接加载当前编译文件的完整路径：

   ```text
   mdl load "E:\Code\Bentley_Python_plugin\型钢构件及支吊架模型生成工具_CS\Development\ValveActuatorCelValidation\CallbackPrototype\bin\Release\net48\ValveActuatorCallbackCheck.dll"
   ```

3. 继续使用已装有V3 `SSP_CEL_HAND_WHEEL` 测试定义的同一工作集。DLL程序集名、组件命名空间及类名均保持一致；未新增Schema变更。V1/V2不参与本轮。

## 使用流程及预期效果

1. 在测试DGN中准备一个没有执行机构的原生阀门。上轮单独放置的普通CEL可先移到旁边，避免与这次生成件重叠；它不参与本轮安装。
2. 不需要预选元素，直接激活：

   ```text
   ACTUATORCALLBACK PLACE
   ```

3. 按官方工具状态栏提示点选阀门，再按提示调整方向并确认；如果宿主要求额外的数据点，按其正常手轮/执行机构放置流程完成。

   **预期：**官方执行机构工具接管点选和安装；三维外形使用内置CEL。右键按官方流程取消或结束。命令返回只表示已请求启动工具，不代表已经创建或关联成功。原 `ACTUATORCALLBACK CREATE` 保留为新PLACE入口的别名，不再执行旧的“选阀门+CEL”逻辑。

4. 放置结束后，只选择阀门运行：

   ```text
   ACTUATORCALLBACK PROBE
   ```

   **预期：**阀门正向 `ForwardOperatorCount=1`，子件为SSP_CEL_HAND_WHEEL。再只选执行机构运行PROBE，预期 `ReverseParentCount=1` 并指向同一阀门。PROBE从图元加载完整关系，并显式包含派生类；同时记录RawRelation名称，以区分缺关系与查询范围问题。

5. 只移动/旋转阀门，再检查重生成、Undo/Redo和保存重开。

   **预期：**CEL外形跟随，重生成仍为CEL，无重复件。圆柱底部圆心与用户定义的阀门表面交点是否一致，需要按这次官方安装架的实际结果核对；尚未经过校核的原生基点不直接宣称为该表面交点。

## 日志

```text
%LOCALAPPDATA%\SteelSectionProbe\logs\ActuatorCallbackCheck\
```

最新place日志应有 `Version=4`、`Route=official BMECApi.StartPlacement(BMECObject)`、`PlacementTool=TopworksPlacementTool`；callback日志也标为Version=4。若仍显示Version=3，说明宿主加载的DLL还没更新。

请反馈最新place、callback以及放置后PROBE日志。`CurrentPlacementTool=null/pending`只记录即时状态，不据此断言工具安装成功或失败；以实际官方提示、交互和最终关系为准。该版本未由Agent启动宿主测试。

本轮继续固定已确认的CEL资源版本和1000000 UOR/m三维模型。每进程最多16次启动，正常退出OPM释放验证期对象。正式业务分类、自动补偿安装偏移、ISO/BOM仍待后续处理。
