using System;
using System.Collections.Generic;
using System.Linq;
using Bentley.DgnPlatformNET;
using SteelSectionProbe;

namespace EquipmentLevelCheck
{
    internal static class Program
    {
        private static int passed;
        private static void Main()
        {
            Check("COM 递归读取厂家外形及嵌套单元", () =>
            {
                Store.Add(1, true, 2, 3); Store.Add(2); Store.Add(3, true, 4); Store.Add(4);
                var snapshot = new EquipmentLevelTree().Capture(1);
                Assert(snapshot.Nodes.Count == 3 && snapshot.Nodes[4].ParentId == 3, "完整包含关系");
                Assert(Store.Writes.Count == 0 && Store.Data[2].Level == 1, "读取不得修改");
                var result = Apply(1);
                Assert(result.Succeeded && result.ChangedElementCount == 2 && result.VerifiedElementCount == 2, "真实计数");
                Assert(Store.Data[2].Level == 2 && Store.Data[4].Color == -1, "层与颜色均落地");
                Assert(!Store.Writes.Contains(1), "不写设备根");
            });
            Check("包围盒内的独立邻近对象不改", () =>
            {
                Basic(); Store.Add(99);
                Assert(Apply(1).Succeeded && !Store.Writes.Contains(99) && Store.Data[99].Color == 7, "只改实际包含的图形");
            });
            Check("颜色不同但图层已正确仍须写入", () =>
            {
                Basic(); Store.Data[2].Level = 2;
                var result = Apply(1);
                Assert(result.Succeeded && result.ChangedElementCount == 1 && Store.Data[2].Color == -1, "颜色单独修复");
            });
            Check("原本正确的不虚报改动", () =>
            {
                Basic(); Store.Data[2].Level = 2; Store.Data[2].Color = -1;
                var result = Apply(1);
                Assert(result.Succeeded && result.ChangedElementCount == 0 && result.AlreadyOnTargetCount == 1, "区分已符合");
                Assert(result.VerifiedElementCount == 1 && Store.Writes.Count == 0, "仍重新读取校验");
            });
            Check("父容器覆盖子元素时保证父先子后", () =>
            {
                Store.Add(1, true, 2); Store.Add(2, true, 3); Store.Add(3);
                Store.AfterRewrite = id => { if (id == 2) { Store.Data[3].Level = 1; Store.Data[3].Color = 7; } };
                Assert(Apply(1).Succeeded && Store.Writes.IndexOf(2) < Store.Writes.IndexOf(3), "父容器先写");
                Assert(Store.Data[3].Color == -1, "最终子元素符合");
            });
            Check("容器不接受属性时内部图形仍严格校验", () =>
            {
                Store.Add(1, true, 2); Store.Add(2, true, 3).BlockWrite = true; Store.Add(3);
                var result = Apply(1);
                Assert(result.Succeeded && result.ContainersNotChanged == 1 && result.VerifiedElementCount == 1, "如实报告容器");
            });
            Check("容器头 Level 为空时继续处理内部图形", () =>
            {
                Store.Add(1, true, 2); Store.Add(2, true, 3).NullLevel = true; Store.Add(3);
                var result = Apply(1);
                Assert(result.Succeeded && result.VerifiedElementCount == 1 && result.ContainersNotChanged == 1, "容器无图层不阻断叶子");
                Assert(!Store.Writes.Contains(2) && Store.Data[3].Color == -1, "保留不可读容器属性");
            });
            Check("容器头图层 getter 内部空引用时继续处理内部图形", () =>
            {
                Store.Add(1, true, 2); Store.Add(2, true, 3).ThrowLevelRead = true; Store.Add(3);
                Assert(Apply(1).Succeeded && Store.Data[3].Level == 2, "处理 COM getter 异常");
            });
            Check("叶子图层为空时不能猜层号或静默排除", () =>
            {
                Basic(); Store.Data[2].NullLevel = true;
                var result = Apply(1);
                Assert(!result.Succeeded && result.Summary.Contains("图元 2") && result.Summary.Contains("COM Level 返回空"), "具体错误包含图元 ID");
                Assert(Store.Marks == 0, "只读失败不开始事务");
            });
            Check("AsCellElement 返回空时明确报告父单元", () =>
            {
                Basic(); Store.Data[1].NullCellCast = true;
                var result = Apply(1);
                Assert(!result.Succeeded && result.Summary.Contains("图元 1") && result.Summary.Contains("AsCellElement 返回空"), "避免空引用");
            });
            Check("AsComplexElement 返回空时明确报告复杂图元", () =>
            {
                Basic(); Store.Data[2].Complex = true; Store.Data[2].Type = "ComplexString"; Store.Data[2].NullComplexCast = true;
                var result = Apply(1);
                Assert(!result.Succeeded && result.Summary.Contains("图元 2") && result.Summary.Contains("AsComplexElement 返回空"), "避免复杂元素空引用");
            });
            Check("COM 上下文为空时明确报告阶段", () =>
            {
                Basic(); Bentley.MstnPlatformNET.InteropServices.Utilities.ComApp = null;
                var result = Apply(1);
                Assert(!result.Succeeded && result.Summary.Contains("读取目标图层") && result.Summary.Contains("COM 应用对象不可用"), "明确上下文错误");
            });
            Check("复杂链头与组成线均需要校验", () =>
            {
                Store.Add(1, true, 2); var chain = Store.Add(2, false, 3); chain.Complex = true; chain.Type = "ComplexString"; Store.Add(3);
                var result = Apply(1);
                Assert(result.Succeeded && result.VerifiedElementCount == 2 && Store.Data[2].Color == -1, "复杂图形头不是可忽略单元头");
            });
            Check("Rewrite 无报错但不落地时回滚", () =>
            {
                Basic(); Store.Data[2].Level = 2; Store.Data[2].BlockWrite = true;
                var result = Apply(1);
                Assert(!result.Succeeded && result.Summary.Contains("已整批回滚"), "不能信 setter 或 Rewrite 返回");
                Assert(Store.Cancels == 1 && Store.Data[2].Color == 7, "恢复原色");
            });
            Check("先前设备写成功后后续设备失败整批回滚", () =>
            {
                Basic(); Store.Add(10, true, 11); Store.Add(11).ThrowWrite = true;
                var result = Apply(1, 10);
                Assert(!result.Succeeded && Store.Data[2].Level == 1 && Store.Data[2].Color == 7, "跨设备原子性");
                Assert(result.ChangedElementCount == 0, "失败无成功数量");
            });
            Check("回滚接口返回错误不能声称已回滚", () =>
            {
                Basic(); Store.Data[2].ThrowWrite = true; Store.FailRollback = true;
                Assert(Apply(1).Summary.Contains("回滚未完成"), "明确通知恢复失败");
            });
            Check("回滚返回成功但属性未恢复也要识别", () =>
            {
                Store.Add(1, true, 2, 3); Store.Add(2); Store.Add(3).ThrowWrite = true; Store.NoOpRollback = true;
                var result = Apply(1);
                Assert(result.Summary.Contains("回滚未完成") && Store.Data[2].Level == 2, "重新核对回滚结果");
            });
            Check("结构数量变化拒绝提交", () =>
            {
                Basic(); Store.AfterRewrite = id => Store.Data[1].Children.Clear();
                Assert(!Apply(1).Succeeded && Store.Data[1].Children.Count == 1, "结构回滚");
            });
            Check("相同数量但持久 ID 变化拒绝提交", () =>
            {
                Basic(); Store.AfterRewrite = id => { Store.Add(3); Store.Data[1].Children[0] = 3; };
                Assert(!Apply(1).Succeeded && !Store.Data.ContainsKey(3), "不只校验数量");
            });
            Check("相同 ID 但图形类型变化拒绝提交", () =>
            {
                Basic(); Store.AfterRewrite = id => Store.Data[2].Type = "Mesh";
                Assert(!Apply(1).Succeeded && Store.Data[2].Type == "Solid", "类型变化回滚");
            });
            Check("空设备不再用依赖管嘴冒充完成", () =>
            {
                Store.Add(1, true); Store.Add(20, true, 21); Store.Add(21);
                Assert(!Apply(1).Succeeded && Store.Writes.Count == 0, "没有实际内部件就拒绝");
            });
            Check("嵌套共享单元只写实例，不展开公共定义", () =>
            {
                Store.Add(1, true, 2); var shared = Shared(2, 3); shared.Cell = true;
                shared.FailEnumeration = true; Store.Add(3).ThrowWrite = true;
                var snapshot = new EquipmentLevelTree().Capture(1);
                Assert(snapshot.Nodes.Count == 1 && snapshot.Nodes[2].IsSharedInstance && !snapshot.Nodes[2].IsContainer, "共享实例是一个原子图形");
                var result = Apply(1);
                Assert(result.Succeeded && result.VerifiedElementCount == 1 && Store.SharedWrites.SequenceEqual(new ulong[] { 2 }), "实例接口写回");
                Assert(Store.Data[2].OverrideLevel && Store.Data[2].OverrideColor && Store.Data[2].Level == 2 && Store.Data[2].Color == -1, "层色覆盖均落地");
                Assert(Store.Data[3].Level == 1 && !Store.Writes.Contains(3), "公共定义内部图元保持不变");
                Assert(result.Summary.Contains("共享实例") && result.Details.Any(d => d.Contains("公共定义")), "向用户说明实例覆盖边界");
            });
            Check("读取嵌套单元失败不能静默漏掉", () =>
            {
                Store.Add(1, true, 2); Store.Add(2, true, 3).FailEnumeration = true; Store.Add(3);
                Assert(!Apply(1).Succeeded && Store.Writes.Count == 0, "不完整读取不写入");
            });
            Check("无法读取的内部件在写前拒绝", () =>
            {
                Store.Add(1, true, 2);
                Assert(!Apply(1).Succeeded && Store.Marks == 0, "缺失子元素不能跳过");
            });
            Check("锁定叶子图形在写前拒绝", () =>
            {
                Basic(); Store.Data[2].Locked = true;
                Assert(!Apply(1).Succeeded && Store.Writes.Count == 0, "尊重元素锁");
            });
            Check("锁定目标层在写前拒绝", () =>
            {
                Basic(); Bentley.MstnPlatformNET.InteropServices.Utilities.ComApp.ActiveModelReference.Levels.Target.IsLocked = true;
                Assert(!Apply(1).Succeeded && Store.Marks == 0, "尊重图层锁");
            });
            Check("只读模型在写前拒绝", () =>
            {
                Basic();
                var result = EquipmentLevelApplier.Apply(new DgnModel { IsReadOnly = true },
                    new ulong[] { 1 }, new LevelId(2), "equipment");
                Assert(!result.Succeeded && Store.Marks == 0, "不写只读模型");
            });
            Check("COM 目标图层 ID 不一致时拒绝", () =>
            {
                Basic(); Bentley.MstnPlatformNET.InteropServices.Utilities.ComApp.ActiveModelReference.Levels.Target.ID = 3;
                Assert(!Apply(1).Succeeded && Store.Writes.Count == 0, "不能只按层名误写");
            });
            Check("包含关系成环时明确拒绝", () =>
            {
                Store.Add(1, true, 2); Store.Add(2, true, 1);
                Assert(!Apply(1).Succeeded && Store.Writes.Count == 0, "不能无限循环或静默截断");
            });
            Check("重复枚举按持久 ID 去重", () =>
            {
                Store.Add(1, true, 2, 2); Store.Add(2);
                var result = Apply(1, 1);
                Assert(result.Succeeded && result.VerifiedElementCount == 1 && Store.Writes.Count == 1, "去重计数与写入");
            });
            Check("重复枚举不误判容器为叶子", () =>
            {
                Store.Add(1, true, 3, 2); Store.Add(3); Store.Add(2, true, 3);
                var snapshot = new EquipmentLevelTree().Capture(1);
                Assert(snapshot.Nodes[2].IsContainer, "容器判定依据实际枚举");
            });
            Check("非图形控制元素不修改", () =>
            {
                Store.Add(1, true, 2, 3); Store.Add(2); Store.Add(3).Graphic = false;
                Assert(Apply(1).Succeeded && !Store.Writes.Contains(3), "跳过控制元素");
            });
            Check("嵌套选择消除所有权歧义", () =>
            {
                Store.Add(1, true, 2); Store.Add(2, true, 3); Store.Add(3);
                Assert(!Apply(1, 2).Succeeded && Store.Marks == 0, "只允许选外层");
            });
            Check("撤销过程中不开始写入", () =>
            {
                Basic(); Store.UndoInProgress = true;
                Assert(!Apply(1).Succeeded && Store.Writes.Count == 0 && Store.Cancels == 0, "没有事务则不回滚");
            });
            Check("最大深度允许边界并拒绝超限", () =>
            {
                Chain(EquipmentLevelTree.MaxDepth);
                Assert(new EquipmentLevelTree().Capture(1).Nodes.Count == EquipmentLevelTree.MaxDepth, "深度边界可读");
                Store.Reset(); Chain(EquipmentLevelTree.MaxDepth + 1);
                Assert(!Apply(1).Succeeded && Store.Writes.Count == 0, "超限不静默截断");
            });
            Check("图元数量允许边界并拒绝超限", () =>
            {
                Store.Add(1, true);
                for (ulong id = 2; id <= (ulong)EquipmentLevelTree.MaxElements + 1; id++)
                { Store.Data[1].Children.Add(id); Store.Add(id); }
                Assert(new EquipmentLevelTree().Capture(1).Nodes.Count == EquipmentLevelTree.MaxElements, "数量边界可读");
                Store.Data[1].Children.Add((ulong)EquipmentLevelTree.MaxElements + 2);
                Store.Add((ulong)EquipmentLevelTree.MaxElements + 2);
                Assert(!Apply(1).Succeeded && Store.Writes.Count == 0, "数量超限不修改");
            });
            Check("指定 RGB 颜色精确转换并落地", () =>
            {
                Basic();
                var result = EquipmentLevelApplier.Apply(new DgnModel(), new ulong[] { 1 },
                    new EquipmentAppearanceOptions { TargetLevelId = 2, TargetLevelName = "equipment",
                        ColorMode = EquipmentColorMode.CustomRgb, Rgb = 0x123456 });
                Assert(result.Succeeded && Store.Data[2].Color == 0x1563412, "RGB 转为 OLE RGB 后生成内部颜色");
                Assert(result.Summary.Contains("#123456"), "报告指定颜色");
            });
            Check("保持原色会核对并恢复父容器重写带来的颜色变化", () =>
            {
                Store.Add(1, true, 2); Store.Add(2, true, 3); Store.Add(3).Color = 42;
                Store.AfterRewrite = id => { if (id == 2) Store.Data[3].Color = 9; };
                var result = EquipmentLevelApplier.Apply(new DgnModel(), new ulong[] { 1 },
                    new EquipmentAppearanceOptions { TargetLevelId = 2, TargetLevelName = "equipment", ColorMode = EquipmentColorMode.KeepOriginal });
                Assert(result.Succeeded && Store.Data[3].Level == 2 && Store.Data[3].Color == 42, "原色保留");
            });
            Check("自定义色值校验拒绝格式错误", () =>
            {
                Assert(EquipmentAppearanceOptions.ParseRgb(" #a0B1c2 ") == 0xA0B1C2, "允许标准 RGB");
                bool rejected = false;
                try { EquipmentAppearanceOptions.ParseRgb("##112233"); } catch (InvalidOperationException) { rejected = true; }
                Assert(rejected, "拒绝重复井号");
            });
            Check("进度回调覆盖读取、写入、校验与完成，并留在调用线程", () =>
            {
                Basic(); var stages = new HashSet<string>(); int thread = System.Threading.Thread.CurrentThread.ManagedThreadId;
                var result = EquipmentLevelApplier.Apply(new DgnModel(), new ulong[] { 1 },
                    new EquipmentAppearanceOptions { TargetLevelId = 2, TargetLevelName = "equipment" }, progress =>
                    { Assert(thread == System.Threading.Thread.CurrentThread.ManagedThreadId, "不跨线程调用模型"); stages.Add(progress.Stage); });
                Assert(result.Succeeded && stages.Contains("读取设备内部图元") && stages.Contains("修改图层与颜色") &&
                    stages.Any(s => s.StartsWith("重新读取并校验")) && stages.Contains("处理完成"), "真实阶段反馈");
            });
            Check("进度刷新期间拒绝重入写入", () =>
            {
                Basic(); EquipmentLevelReport nested = null;
                var result = EquipmentLevelApplier.Apply(new DgnModel(), new ulong[] { 1 },
                    new EquipmentAppearanceOptions { TargetLevelId = 2, TargetLevelName = "equipment" }, progress =>
                    { if (nested == null) nested = Apply(1); });
                Assert(result.Succeeded && !nested.Succeeded && !EquipmentLevelApplier.IsRunning, "重入拒绝且释放忙状态");
            });
            Check("刷新期间文档切换中止写入并保留回滚通道", () =>
            {
                Basic(); bool contextValid = true;
                var result = EquipmentLevelApplier.Apply(new DgnModel(), new ulong[] { 1 },
                    new EquipmentAppearanceOptions { TargetLevelId = 2, TargetLevelName = "equipment" },
                    progress => { if (progress.Stage.StartsWith("重新读取并校验")) contextValid = false; },
                    () => { if (!contextValid) throw new InvalidOperationException("文档已切换"); });
                Assert(!result.Succeeded && Store.Cancels == 1 && Store.Data[2].Level == 1, "文档切换后仍执行整批回滚");
            });
            Check("提交后完成反馈不再触发上下文回滚", () =>
            {
                Basic(); bool contextValid = true;
                var result = EquipmentLevelApplier.Apply(new DgnModel(), new ulong[] { 1 },
                    new EquipmentAppearanceOptions { TargetLevelId = 2, TargetLevelName = "equipment" },
                    progress => { if (progress.Stage == "处理完成") contextValid = false; },
                    () => { if (!contextValid) throw new InvalidOperationException("完成后切换文档"); });
                Assert(result.Succeeded && Store.Cancels == 0, "提交后没有可失败的上下文读取");
            });
            Check("实际图层读取标记可用、只读、锁定和不可用", () =>
            {
                Store.LevelHandles.Add(new LevelHandle { LevelId = new LevelId(2), Name = "equipment" });
                Store.LevelHandles.Add(new LevelHandle { LevelId = new LevelId(3), Name = "readonly", ReadOnly = true });
                Store.LevelHandles.Add(new LevelHandle { LevelId = new LevelId(4), Name = "locked" });
                Store.LevelHandles.Add(new LevelHandle { LevelId = new LevelId(5), Name = "missing" });
                var levels = Bentley.MstnPlatformNET.InteropServices.Utilities.ComApp.ActiveModelReference.Levels;
                levels.Target.ElementColor = 0x112233;
                levels.Other["readonly"] = new Bentley.Interop.MicroStationDGN.Level { ID = 3 };
                levels.Other["locked"] = new Bentley.Interop.MicroStationDGN.Level { ID = 4, IsLocked = true };
                var document = EquipmentLevelUiReader.ReadDocument();
                Assert(document.ActiveLevelId == 2 && document.Levels.Count == 4, "真实图层枚举");
                Assert(document.Levels.Single(l => l.Id == 2).IsWritable && document.Levels.Single(l => l.Id == 2).ColorHex == "#332211", "层色正确转换");
                Assert(document.Levels.Where(l => l.Id != 2).All(l => !l.IsWritable), "禁用无权图层");
                Store.ActiveModel.File.IsReadOnly = true;
                Assert(EquipmentLevelUiReader.ReadDocument().Levels.All(l => !l.IsWritable), "只读文件禁用全部目标");
            });
            Check("选择读取去重设备并拒绝非设备及参考文件", () =>
            {
                Basic();
                var chosen = new Bentley.DgnPlatformNET.Elements.Element { ElementId = 1, DgnModelRef = new DgnModelRef { Model = Store.ActiveModel } };
                Bentley.MstnPlatformNET.SelectionSetManager.Items.Add(chosen);
                Bentley.MstnPlatformNET.SelectionSetManager.Items.Add(chosen);
                Bentley.MstnPlatformNET.SelectionSetManager.Items.Add(new Bentley.DgnPlatformNET.Elements.Element { ElementId = 2, DgnModelRef = chosen.DgnModelRef });
                Bentley.MstnPlatformNET.SelectionSetManager.Items.Add(new Bentley.DgnPlatformNET.Elements.Element { ElementId = 1, DgnModelRef = new DgnModelRef { Model = new DgnModel() } });
                var selection = EquipmentLevelUiReader.ReadSelection();
                Assert(selection.Equipment.Count == 1 && selection.Rejected.Count == 2, "明确范围与拒绝原因");
            });
            Check("活动文档切换使缓存选择失效", () =>
            {
                var document = EquipmentLevelUiReader.ReadDocument();
                Store.ActiveModel = new DgnModel();
                bool rejected = false;
                try { EquipmentLevelUiReader.ValidateDocument(document); } catch (InvalidOperationException) { rejected = true; }
                Assert(rejected, "不能将旧设备 ID 用于新文档");
            });
            Check("SmartSolid 在实体边界停止，不读写其内部存储与显示线", () =>
            {
                Store.Add(1, true, 2);
                var solid = Store.Add(2, false, 3, 4); solid.Type = "CellHeader"; solid.Smart = true;
                solid.Complex = true; solid.FailEnumeration = true;
                Store.Add(3).Type = "DgnStoreHeader"; Store.Add(4).Type = "Line";
                var snapshot = new EquipmentLevelTree().Capture(1);
                Assert(snapshot.Nodes.Count == 1 && snapshot.Nodes[2].IsAtomicSolid, "SmartSolid 是一个图形目标");
                var result = Apply(1);
                Assert(result.Succeeded && result.VerifiedElementCount == 1 && Store.SmartWrites.SequenceEqual(new ulong[] { 2 }), "用实体接口写回");
                Assert(!Store.Writes.Contains(3) && !Store.Writes.Contains(4) && Store.Data[4].Level == 1, "不改内部缓存线");
            });
            Check("无法识别的特殊 CellHeader 在写入前拒绝", () =>
            {
                Store.Add(1, true, 2); var special = Store.Add(2, false, 3);
                special.Type = "CellHeader"; special.Complex = true;
                Store.Add(3).Type = "Line";
                var result = Apply(1);
                Assert(!result.Succeeded && Store.Marks == 0 && result.Summary.Contains("特殊 CellHeader"), "不再盲目展开特殊实体");
            });
            Check("普通单元暴露 DgnStore 存储记录时拒绝写入", () =>
            {
                Store.Add(1, true, 2, 3); Store.Add(2); Store.Add(3).Type = "DgnStoreHeader";
                var result = Apply(1);
                Assert(!result.Succeeded && Store.Writes.Count == 0 && result.Summary.Contains("内部存储记录"), "不能绕过实体判定修改 BRep 内部表示");
            });
            Check("水泵式141个实体加数千缓存线只产生141个实体修改", () =>
            {
                Store.Add(1, true, 2); Store.Add(2, true).NullLevel = true;
                for (ulong i = 0; i < 141; i++)
                {
                    ulong bodyId = 100 + i * 100;
                    Store.Data[2].Children.Add(bodyId);
                    var body = Store.Add(bodyId); body.Smart = true; body.Complex = true;
                    body.Type = "CellHeader"; body.FailEnumeration = true;
                    Store.Add(bodyId + 1).Type = "DgnStoreHeader";
                    body.Children.Add(bodyId + 1);
                    for (ulong j = 2; j < 30; j++) { Store.Add(bodyId + j).Type = j % 2 == 0 ? "Line" : "Arc"; body.Children.Add(bodyId + j); }
                }
                Assert(Store.Data.Count > 4000, "夹具包含数千内部记录");
                var result = Apply(1);
                Assert(result.Succeeded && result.VerifiedElementCount == 141 && Store.Writes.Count == 141 && Store.SmartWrites.Count == 141, "数量按可改实体统计");
            });
            Check("共享实例字段已符合但覆盖开关关闭时仍须修改", () =>
            {
                Store.Add(1, true, 2); var shared = Shared(2); shared.Level = 2; shared.Color = -1;
                var result = Apply(1);
                Assert(result.Succeeded && result.ChangedElementCount == 1 && shared.OverrideLevel && shared.OverrideColor, "不只校验头属性");
            });
            Check("共享实例层色及覆盖开关均符合时不重复写入", () =>
            {
                Store.Add(1, true, 2); var shared = Shared(2); shared.Level = 2; shared.Color = -1;
                shared.OverrideLevel = shared.OverrideColor = true;
                var result = Apply(1);
                Assert(result.Succeeded && result.ChangedElementCount == 0 && Store.Writes.Count == 0, "正确识别已符合");
            });
            Check("同一公共定义的未选中实例不受影响", () =>
            {
                Store.Add(1, true, 2); Shared(2, 50); Shared(20, 50); Store.Add(50);
                Assert(Apply(1).Succeeded && Store.Data[20].Level == 1 && Store.Data[20].Color == 7 && !Store.Data[20].OverrideColor, "未选实例保持原样");
                Assert(Store.Writes.SequenceEqual(new ulong[] { 2 }) && Store.Data[50].Level == 1, "不写公共定义");
            });
            Check("多个设备引用同一公共定义可分别修改实例", () =>
            {
                Store.Add(1, true, 2); Shared(2, 50); Store.Add(10, true, 20); Shared(20, 50); Store.Add(50);
                var result = Apply(1, 10);
                Assert(result.Succeeded && result.EquipmentCount == 2 && result.VerifiedElementCount == 2, "不将公共定义重复引用误判为归属重叠");
                Assert(Store.SharedWrites.Count == 2 && !Store.Writes.Contains(50), "每个实例单独覆盖");
            });
            Check("指定 RGB 同时启用共享实例颜色覆盖", () =>
            {
                Store.Add(1, true, 2); Shared(2);
                var result = EquipmentLevelApplier.Apply(new DgnModel(), new ulong[] { 1 },
                    new EquipmentAppearanceOptions { TargetLevelId = 2, TargetLevelName = "equipment",
                        ColorMode = EquipmentColorMode.CustomRgb, Rgb = 0x123456 });
                Assert(result.Succeeded && Store.Data[2].OverrideColor && Store.Data[2].OverrideLevel && Store.Data[2].Color == 0x1563412, "指定色显示覆盖");
            });
            Check("保持原色保留共享实例原有颜色覆盖状态", () =>
            {
                foreach (bool wasOverridden in new[] { false, true })
                {
                    Store.Reset(); Store.Add(1, true, 2); var shared = Shared(2); shared.OverrideColor = wasOverridden;
                    var result = EquipmentLevelApplier.Apply(new DgnModel(), new ulong[] { 1 },
                        new EquipmentAppearanceOptions { TargetLevelId = 2, TargetLevelName = "equipment", ColorMode = EquipmentColorMode.KeepOriginal });
                    Assert(result.Succeeded && shared.OverrideColor == wasOverridden && shared.Color == 7 && shared.OverrideLevel, "只启用层覆盖，保持原颜色规则");
                }
            });
            Check("共享实例层覆盖未落地不能报告成功", () =>
            {
                Store.Add(1, true, 2); var shared = Shared(2); shared.BlockLevelOverride = true;
                var result = Apply(1);
                Assert(!result.Succeeded && result.Summary.Contains("已整批回滚"), "头属性正确也要检查层覆盖");
                Assert(!Store.Data[2].OverrideColor && Store.Data[2].Level == 1, "恢复原属性及开关");
            });
            Check("共享实例颜色覆盖未落地不能报告成功", () =>
            {
                Store.Add(1, true, 2); var shared = Shared(2); shared.BlockColorOverride = true;
                Assert(!Apply(1).Succeeded && Store.Cancels == 1 && !Store.Data[2].OverrideLevel, "检查颜色覆盖并回滚");
            });
            Check("后续图元写入失败会恢复共享实例层色及开关", () =>
            {
                Store.Add(1, true, 2, 3); Shared(2); Store.Add(3).ThrowWrite = true;
                var result = Apply(1);
                Assert(!result.Succeeded && result.Summary.Contains("已整批回滚") && Store.SharedWrites.Count == 1, "共享实例也参与整批事务");
                Assert(Store.Data[2].Level == 1 && Store.Data[2].Color == 7 && !Store.Data[2].OverrideColor && !Store.Data[2].OverrideLevel, "完整恢复覆盖状态");
            });
            Check("回滚未恢复共享覆盖开关时明确报告", () =>
            {
                Store.Add(1, true, 2, 3); var shared = Shared(2); shared.Level = 2; shared.Color = -1;
                Store.Add(3).ThrowWrite = true; Store.NoOpRollback = true;
                Assert(Apply(1).Summary.Contains("回滚未完成"), "属性未变仍需检查覆盖状态恢复");
            });
            Check("共享接口为空在写前拒绝并给出实例 ID", () =>
            {
                Store.Add(1, true, 2); Shared(2).NullSharedCast = true;
                var result = Apply(1);
                Assert(!result.Succeeded && Store.Marks == 0 && result.Summary.Contains("图元 2") && result.Summary.Contains("AsSharedCellElement"), "不能跳过不可读实例");
            });
            Check("锁定共享实例在写前拒绝", () =>
            {
                Store.Add(1, true, 2); Shared(2).Locked = true;
                Assert(!Apply(1).Succeeded && Store.Marks == 0, "遵守实例锁定");
            });
            Check("共享单元根仍不能冒充普通设备入口", () =>
            {
                var root = Shared(1, 2); root.Cell = true; Store.Add(2);
                Assert(!Apply(1).Succeeded && Store.Writes.Count == 0, "仅支持普通设备内部的共享实例");
            });
            Check("共享实例的定义引用变化时拒绝提交并恢复", () =>
            {
                Store.Add(1, true, 2); Shared(2); Store.AfterRewrite = id => Store.Data[2].SharedName = "OTHER_PART";
                Assert(!Apply(1).Succeeded && Store.Data[2].SharedName == "PUMP_PART", "不能只检查实例 ID");
            });
            Check("水泵739007的嵌套容器可同时处理实体和共享实例", () =>
            {
                Store.Add(739007, true, 739008);
                Store.Add(739008, true, 739025, 739026).NullLevel = true;
                var solid = Store.Add(739025); solid.Type = "CellHeader"; solid.Smart = solid.Complex = true; solid.FailEnumeration = true;
                Shared(739026, 739100).FailEnumeration = true; Store.Add(739100).ThrowWrite = true;
                var result = Apply(739007);
                Assert(result.Succeeded && result.VerifiedElementCount == 2 && result.ContainersNotChanged == 1, "不因共享实例拒绝整台设备");
                Assert(Store.SmartWrites.SequenceEqual(new ulong[] { 739025 }) && Store.SharedWrites.SequenceEqual(new ulong[] { 739026 }), "按各自原子接口处理");
                Assert(!Store.Writes.Contains(739100) && !Store.Writes.Contains(739007), "不展开定义或重建设备根");
            });
            Check("模型按内部 ID 返回外层单元时仍沿包含路径写正确组件", () =>
            {
                Basic();
                var direct = Bentley.MstnPlatformNET.InteropServices.Utilities.ComApp.ActiveModelReference.GetElementByID64(2);
                Assert(direct.ID64 == 1 && direct.IsCellElement(), "替身复现模型查找返回外层单元");
                var snapshot = new EquipmentLevelTree().Capture(1);
                var resolved = new EquipmentLevelTree().Resolve(snapshot, snapshot.Nodes[2]);
                Assert(resolved.ID64 == 2 && !resolved.IsCellElement(), "从包含路径精确定位");
                var result = Apply(1);
                Assert(result.Succeeded && Store.Writes.SequenceEqual(new ulong[] { 2 }) && Store.Data[1].Level == 1, "绝不将根当内部件代写");
                Assert(Store.Logs.Any(l => l.Contains("寻址对照") && l.Contains("查找 2 实际返回 id=1")), "保存模型查找的实际 ID 证据");
            });
            Check("模型按内部 ID 正确返回组件的宿主也能工作", () =>
            {
                Basic(); Store.ReturnOuterCell = false;
                Assert(Apply(1).Succeeded && Store.Writes.SequenceEqual(new ulong[] { 2 }), "不依赖模型查找行为");
            });
            Check("每次写入重新取得组件，不复用父容器重写前包装", () =>
            {
                Store.Add(1, true, 2); Store.Add(2, true, 3, 4).RejectStaleWrite = true;
                Store.Add(3).RejectStaleWrite = Store.Add(4).RejectStaleWrite = true;
                Assert(Apply(1).Succeeded && Store.Writes.SequenceEqual(new ulong[] { 2, 3, 4 }), "组件包装跨重写失效时仍安全定位");
            });
            Check("组件仍存在但已移出原父路径时不按全局 ID 误写", () =>
            {
                Store.Add(1, true, 2, 3); Store.Add(2); Store.Add(3); Store.Add(99, true);
                Store.AfterRewrite = id => { if (id == 2) { Store.Data[1].Children.Remove(3); Store.Data[99].Children.Add(3); } };
                var result = Apply(1);
                Assert(!result.Succeeded && result.Summary.Contains("找不到计划内部件 3"), "保留归属检查");
                Assert(!Store.Writes.Contains(3) && result.Summary.Contains("已整批回滚") && Store.Data[2].Level == 1, "拒绝越界并恢复之前写入");
            });
            Check("根查找返回相同类型的其他单元也在写前拒绝", () =>
            {
                Basic(); Store.Add(99, true, 100); Store.Add(100); Store.LookupRedirects[1] = 99;
                var result = Apply(1);
                Assert(!result.Succeeded && Store.Marks == 0 && Store.Writes.Count == 0, "不仅比较类型，还必须比较根 ID");
                Assert(result.Summary.Contains("查找 1 实际返回 id=99"), "具体列出返回身份");
            });
            Check("真正的组件类型变化仍拒绝并列出预期和实际", () =>
            {
                Basic(); bool changed = false;
                var result = EquipmentLevelApplier.Apply(new DgnModel(), new ulong[] { 1 },
                    new EquipmentAppearanceOptions { TargetLevelId = 2, TargetLevelName = "equipment" }, p =>
                    { if (!changed && p.Stage == "修改图层与颜色") { changed = true; Store.Data[2].Type = "Mesh"; } });
                Assert(!result.Succeeded && Store.Writes.Count == 0 && result.Summary.Contains("预期 id=2 类型=Solid") &&
                    result.Summary.Contains("实际 id=2 类型=Mesh"), "不能直接删除身份保护");
                Assert(Store.Data[2].Type == "Solid" && result.Summary.Contains("已整批回滚"), "类型变化回滚");
            });
            Check("原普通容器变成共享实例时不再沿旧路径进入公共定义", () =>
            {
                Store.Add(1, true, 2); Store.Add(2, true, 3); Store.Add(3); bool changed = false;
                var result = EquipmentLevelApplier.Apply(new DgnModel(), new ulong[] { 1 },
                    new EquipmentAppearanceOptions { TargetLevelId = 2, TargetLevelName = "equipment" }, p =>
                    { if (!changed && p.Stage == "修改图层与颜色") { changed = true; Store.Data[2].Shared = true; Store.Data[2].Type = "SharedCell"; } });
                Assert(!result.Succeeded && Store.Writes.Count == 0 && !Store.Data[2].Shared, "先检查每级身份再展开");
            });
            Check("四共享实例水泵在模型查找返回外层头时全部按实例覆盖", () =>
            {
                Store.Add(739007, true, 739008);
                Store.Add(739008, true, 739026, 739027, 739028, 739029).NullLevel = true;
                foreach (ulong id in new ulong[] { 739026, 739027, 739028, 739029 })
                { var shared = Shared(id, 800000); shared.SharedName = "Pt_" + id; shared.FailEnumeration = true; }
                Store.Add(800000).ThrowWrite = true;
                var result = Apply(739007);
                Assert(result.Succeeded && result.VerifiedElementCount == 4 && Store.SharedWrites.Count == 4, "四实例均通过重新读取校验");
                Assert(!Store.Writes.Contains(739007) && !Store.Writes.Contains(739008) && !Store.Writes.Contains(800000), "不代写外层头或公共定义");
            });
            Console.WriteLine("EquipmentLevelCheck: " + passed + " scenarios passed.");
        }

        private static void Check(string name, Action action)
        {
            Store.Reset();
            try { action(); passed++; Console.WriteLine("PASS " + name); }
            catch (Exception ex) { throw new Exception(name + ": " + ex.Message, ex); }
        }
        private static void Basic() { Store.Add(1, true, 2); Store.Add(2); }
        private static State Shared(ulong id, params ulong[] definitionChildren)
        {
            var shared = Store.Add(id, false, definitionChildren);
            shared.Shared = shared.Complex = true; shared.Type = "SharedCell";
            return shared;
        }
        private static void Chain(int depth)
        {
            for (ulong id = 1; id <= (ulong)depth; id++) Store.Add(id, true, id + 1);
            Store.Add((ulong)depth + 1);
        }
        private static EquipmentLevelReport Apply(params ulong[] ids)
        {
            return EquipmentLevelApplier.Apply(new DgnModel(), ids, new LevelId(2), "equipment");
        }
        private static void Assert(bool condition, string message)
        {
            if (!condition) throw new Exception(message);
        }
    }
}
