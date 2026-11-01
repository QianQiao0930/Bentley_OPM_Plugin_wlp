extern alias NativeOPM;
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Runtime.InteropServices;
using System.Text;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.ECObjects.Instance;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
using Bentley.MstnPlatformNET.InteropServices;
using Bentley.OpenPlant.Modeler.Api;
using Com = Bentley.Interop.MicroStationDGN;

namespace ValveActuatorCelCheck
{
    /// <summary>Isolated host experiment: no schema edits, no handler replacement, no new relationships.</summary>
    public static class Commands
    {
        private const string Relation = "VALVE_HAS_VALVE_OPERATING_DEVICE";
        private const string CellName = "气动执行-DN800";
        private static bool running;
        // The public API's ownership of NonParametricElement is not documented.
        // Keep every submitted handle pinned until process exit, including failures.
        // This small, bounded host experiment must not be unloaded after a SWAP.
        private static readonly List<PinnedGeometry> leases = new List<PinnedGeometry>();
        // V2 explicitly owns a non-parametric wrapper. Keep it alive together with
        // submitted geometry, rather than disposing an object the native writer may retain.
        private static readonly List<BMECObject> explicitObjects = new List<BMECObject>();
        internal static bool HasNativeLeases { get { return leases.Count != 0 || explicitObjects.Count != 0; } }
        private sealed class PinnedGeometry
        {
            internal readonly Element Element;
            internal readonly GCHandle Pin;
            internal PinnedGeometry(Element element)
            { Element = element; Pin = GCHandle.Alloc(element.ElementHandle, GCHandleType.Pinned); }
        }

        public static void Probe(string args) { Run("probe", false, ExecuteProbe); }
        public static void Swap(string args) { Run("swap", true, ExecuteSwap); }

        private static void Run(string name, bool writable, Action<DgnModel, StringBuilder> action)
        {
            if (running) { NotificationManager.OutputPrompt("执行机构验证正在执行，请勿重复调用。"); return; }
            running = true;
            var log = new StringBuilder();
            string folder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "SteelSectionProbe", "logs", "ValveActuatorCelCheckV2", DateTime.Now.ToString("yyyyMMdd_HHmmss_fff"));
            try
            {
                Directory.CreateDirectory(folder);
                var model = Active(writable);
                log.AppendLine("Command=" + name + "; LocalTime=" + DateTimeOffset.Now.ToString("o"));
                log.AppendLine("PrototypeVersion=2; Route=explicit BMECObject(existingInstance, nonParametric:true); No Create call.");
                log.AppendLine("Assembly=" + typeof(Commands).Assembly.Location + "; MVID=" + typeof(Commands).Assembly.ManifestModule.ModuleVersionId);
                log.AppendLine("DGN=" + Session.Instance.GetActiveDgnFile().GetFileName() + "; Model=" + model.GetModelInfo().Name);
                log.AppendLine("UorPerMeter=" + model.GetModelInfo().UorPerMeter.ToString("R", CultureInfo.InvariantCulture));
                action(model, log);
                log.AppendLine("Result=CommandCompleted; host follow/move/regeneration/reopen acceptance remains separate.");
                NotificationManager.OutputPrompt("执行机构验证完成，日志：" + folder);
            }
            catch (Exception ex)
            {
                log.AppendLine("Result=Failed\r\n" + ex);
                NotificationManager.OutputPrompt("执行机构验证失败：" + ex.Message + "；日志：" + folder);
            }
            finally
            {
                try { File.WriteAllText(Path.Combine(folder, name + ".log"), log.ToString(), new UTF8Encoding(false)); }
                catch (Exception ex) { NotificationManager.OutputPrompt("日志保存失败：" + ex.Message); }
                running = false;
            }
        }

        private static DgnModel Active(bool writable)
        {
            var model = Session.Instance.GetActiveDgnModel();
            var file = Session.Instance.GetActiveDgnFile();
            if (!Utilities.IsMicroStationMainThread || model == null || file == null || !model.Is3d)
                throw new InvalidOperationException("请在 OPM 主线程打开三维模型。");
            if (TransactionManager.IsUndoInProgress) throw new InvalidOperationException("正在撤销/重做。");
            if (writable && (model.IsReadOnly || file.IsReadOnly)) throw new InvalidOperationException("模型不可写。");
            return model;
        }

        private static List<Element> Selection(DgnModel model)
        {
            uint count = SelectionSetManager.NumSelected();
            if (count == 0 || count > 2) throw new InvalidOperationException("只读探查请选择 1～2 件；替换请选择一个原生手轮和一个已定位的 CEL。");
            var result = new List<Element>();
            for (uint i = 0; i < count; i++)
            {
                Element element = null; DgnModelRef modelRef = null;
                if (SelectionSetManager.GetElement(i, ref element, ref modelRef) != StatusInt.Success || element == null
                    || element.GetNativeDgnModelRef() != ModelToken(model))
                    throw new InvalidOperationException("所选元素必须都在活动模型中，不能来自参考文件。");
                result.Add(element);
            }
            return result;
        }

        private static unsafe IntPtr ModelToken(DgnModel model)
        { return (IntPtr)DgnModelRef.GetNativeDgnModelRefP(model, false); }

        private static unsafe IECInstance Instance(Element element)
        {
            return BMECApi.Instance.FindInstance(
                (NativeOPM::Bentley.DgnPlatform.ElementRefBase*)element.GetNativeElementRef(),
                (NativeOPM::Bentley.DgnPlatform.DgnModelRef*)element.GetNativeDgnModelRef());
        }

        private static List<IECInstance> Related(IECInstance instance, bool forward)
        {
            return BMECApi.Instance.GetRelatedInstances(instance, Relation, forward, true).Cast<IECInstance>().ToList();
        }

        private static void ExecuteProbe(DgnModel model, StringBuilder log)
        {
            foreach (var element in Selection(model))
            {
                log.AppendLine("SelectedElement=" + (ulong)element.ElementId + "; Type=" + element.ElementType);
                LogRange(element, log, "Selected");
                var instance = Instance(element);
                if (instance == null) { log.AppendLine("NativeInstance=none (ordinary geometry)"); continue; }
                Describe(instance, log);
                foreach (var child in Related(instance, true)) { log.AppendLine("ForwardRelation=" + Relation); Describe(child, log); }
                foreach (var parent in Related(instance, false)) { log.AppendLine("ReverseRelation=" + Relation); Describe(parent, log); }
            }
        }

        private static void Describe(IECInstance instance, StringBuilder log)
        {
            using (var obj = new BMECObject(instance))
            {
                log.AppendLine("Instance=" + instance.InstanceId + "; Class=" + instance.ClassDefinition.Name
                    + "; Element=" + ElementId(instance) + "; IsParametric=" + obj.IsParametric + "; PlacementTool=" + obj.PlacementTool);
                log.AppendLine("Transform=" + obj.Transform3d);
                int portCount = obj.Ports == null ? 0 : obj.Ports.Count;
                log.AppendLine("NativePortCount=" + portCount);
                if (portCount > 16) throw new InvalidOperationException("端口数量超出本原型读取边界。");
                for (int i = 0; i < portCount; i++)
                    log.AppendLine("NativePort[" + i + "].PointUor=" + obj.GetNthPoint(i));
                log.AppendLine("Geometry=" + GeometrySignature(instance));
                foreach (var name in new[] {"NAME", "ANGLE", "LENGTH", "DIAMETER", "UPDATE_GRAPHICS"})
                    if (instance.ClassDefinition.Properties(true).Any(p => p.Name == name))
                        log.AppendLine(name + "=" + instance[name].XmlStringValue);
            }
            if (instance.ClassDefinition.Name == "HAND_WHEEL")
            using (var explicitObject = new BMECObject(instance, true))
                log.AppendLine("ReadOnlyExplicitConstructor.IsParametric=" + explicitObject.IsParametric
                    + "; IsValid=" + explicitObject.IsValid + "; NoSetNoSerialize=true");
        }

        private static string GeometrySignature(IECInstance instance)
        {
            if (!instance.ClassDefinition.Properties(true).Any(p => p.Name == "Geometry")) return "missing";
            var value = instance["Geometry"];
            if (value.IsNull) return "null";
            var bytes = value.NativeValue as byte[];
            if (bytes == null) throw new InvalidOperationException("Geometry 未返回预期二进制数组，停止验证。");
            using (var hash = SHA256.Create()) return bytes.Length + ":" + BitConverter.ToString(hash.ComputeHash(bytes)).Replace("-", "");
        }

        private static unsafe ulong ElementId(IECInstance instance)
        {
            var elementRef = BMECApi.Instance.GetElementRef(instance);
            if (elementRef == null) throw new InvalidOperationException("原生实例没有有效根图元。");
            using (var element = Element.GetFromElementRef((IntPtr)elementRef)) return (ulong)element.ElementId;
        }

        private static void LogRange(Element element, StringBuilder log, string label)
        {
            var range = Range(element);
            log.AppendLine(label + ".RangeUor=" + range.Low + " -> " + range.High);
        }

        private static DRange3d Range(Element element)
        {
            var displayable = element as DisplayableElement;
            var range = new DRange3d();
            if (displayable == null || displayable.CalcElementRange(out range) != StatusInt.Success)
                throw new InvalidOperationException("无法读取完整三维范围。");
            foreach (double coordinate in new[] {range.Low.X,range.Low.Y,range.Low.Z,range.High.X,range.High.Y,range.High.Z})
                if (double.IsNaN(coordinate) || double.IsInfinity(coordinate)) throw new InvalidOperationException("图形范围含无效坐标。");
            return range;
        }

        private static double RangeError(DRange3d a, DRange3d b)
        {
            return new[] {Math.Abs(a.Low.X-b.Low.X),Math.Abs(a.Low.Y-b.Low.Y),Math.Abs(a.Low.Z-b.Low.Z),
                Math.Abs(a.High.X-b.High.X),Math.Abs(a.High.Y-b.High.Y),Math.Abs(a.High.Z-b.High.Z)}.Max();
        }

        private static IECInstance Parent(IECInstance wheel)
        {
            var parents = Related(wheel, false);
            if (parents.Count != 1) throw new InvalidOperationException("手轮必须恰好关联一个父阀门，实际数量=" + parents.Count);
            var parent = parents[0];
            var children = Related(parent, true);
            if (children.Count != 1 || children[0].InstanceId != wheel.InstanceId)
                throw new InvalidOperationException("父阀门的执行机构必须恰好是所选手轮。");
            return parent;
        }

        private static Element LocalGeometry(Element source, DgnModel model, DTransform3d inverse, StringBuilder log)
        {
            // Rebuild only the root, excluding CEL placement ItemTypes on that root.
            // Read direct children only; SmartSolid internals remain atomic.
            var children = source.GetChildren().ToList();
            if (children.Count != 14) throw new InvalidOperationException("本原型只接收当前 14 个直接子图形的 CEL；实际=" + children.Count);
            var local = new CellHeaderElement(model, "ACTUATOR_CEL_CHECK", DPoint3d.Zero, DMatrix3d.Identity, children);
            try
            {
                if (RangeError(Range(local), Range(source)) > 2) throw new InvalidOperationException("复制后的 CEL 直接子图形包络不一致。");
                if (local.ApplyTransform(new TransformInfo(inverse)) != 0) throw new InvalidOperationException("世界几何到原手轮局部坐标转换失败。");
                log.AppendLine("ImportedDirectChildren=" + children.Count + "; CEL root ItemTypes not copied.");
                return local;
            }
            catch { local.Dispose(); throw; }
            finally { foreach (var child in children) child.Dispose(); }
        }

        private static unsafe void ExecuteSwap(DgnModel model, StringBuilder log)
        {
            var selected = Selection(model);
            if (selected.Count != 2) throw new InvalidOperationException("请选择已关联阀门的原生手轮，以及已经放到目标安装位置的 CEL，共两件。");
            var entries = selected.Select(e => new {Element=e, Instance=Instance(e)}).ToList();
            var wheels = entries.Where(e => e.Instance != null && e.Instance.ClassDefinition.Name == "HAND_WHEEL").ToList();
            var sources = entries.Where(e => IsSourceCell(e.Element)).ToList();
            if (wheels.Count != 1 || sources.Count != 1) throw new InvalidOperationException("必须为一个 HAND_WHEEL 原生实例和一个普通 CEL；本轮不处理其他执行机构类。");
            var wheel = wheels[0].Instance;
            var originalElement = wheels[0].Element;
            var source = sources[0].Element;
            var sourceCom = Utilities.ComApp.ActiveModelReference.GetElementByID64(checked((long)(ulong)source.ElementId));
            if (!sourceCom.IsCellElement() || sourceCom.IsSharedCellElement() || sourceCom.AsCellElement().Name != CellName)
                throw new InvalidOperationException("源件必须是普通 CEL 单元“" + CellName + "”。");
            var parent = Parent(wheel);
            foreach (var element in selected)
                if (element.IsEffectivelyLocked(true, true)) throw new InvalidOperationException("所选元素被锁定。");
            if (!BMECApi.Instance.IsInstanceModifiable(wheel) || !BMECApi.Instance.IsInstanceModifiable(parent))
                throw new InvalidOperationException("手轮或父阀门不可修改。");
            string wheelId = wheel.InstanceId, parentId = parent.InstanceId;
            ulong originalWheelElementId = originalElement.ElementId;
            ulong sourceId = source.ElementId;
            string oldGeometry = GeometrySignature(wheel);
            DRange3d oldWheelRange = Range(originalElement), sourceRange = Range(source);
            DRange3d parentRange;
            ulong parentElementId = ElementId(parent);
            if (parentElementId == (ulong)originalElement.ElementId)
                throw new InvalidOperationException("手轮与阀体共用一个根图元，本轮独立实例替换路线不适用；请保留 PROBE 日志。");
            using (var parentElement = Element.GetFromElementRef((IntPtr)BMECApi.Instance.GetElementRef(parent)))
            {
                if (parentElement.GetNativeDgnModelRef() != ModelToken(model))
                    throw new InvalidOperationException("父阀门不属于活动模型。");
                parentRange = Range(parentElement);
            }
            Describe(wheel, log);
            log.AppendLine("Parent=" + parentId + "; Source=" + sourceId + "; SourceName=" + CellName);
            var api = BMECApi.Instance;
            if (api.DeferCommits) throw new InvalidOperationException("OPM 存在延迟提交上下文，停止验证，避免触及其他待提交业务。");
            DTransform3d transform;
            using (var original = new BMECObject(wheel)) transform = original.Transform3d;
            if (explicitObjects.Count >= 8) throw new InvalidOperationException("V2 单进程最多 8 次显式对象试验，请退出并重开 OPM。");
            // V1 demonstrated that SetNonParametricElement does not switch the
            // parametric object's mode. V2 selects the mode at construction time.
            var obj = new BMECObject(wheel, true);
            explicitObjects.Add(obj);
            log.AppendLine("ExplicitConstructor.IsParametric=" + obj.IsParametric + "; IsValid=" + obj.IsValid);
            if (!obj.IsValid || obj.IsParametric) throw new InvalidOperationException("显式非参数化构造未产生有效的非参数化对象，停止本路线。");
            // The instance already has its relationship. Do not add or duplicate it.
            obj.RelatedInstance = parent;
            obj.AddRelationships = false;
            bool previousAllowGraphicsUpdate = obj.AllowGraphicsUpdate;
            var inverse = api.GetMatrixInverse(transform);
            Element local = LocalGeometry(source, model, inverse, log);
            if (RangeError(Range(source), sourceRange) > 2) {local.Dispose(); throw new InvalidOperationException("局部几何构造影响了源 CEL，停止验证。");}
            if (leases.Count >= 8) {local.Dispose(); throw new InvalidOperationException("本原型最多验证 8 次；请退出并重开 OPM 后继续。");}
            if (!TransactionManager.IsActive) TransactionManager.Activate();
            if (!TransactionManager.IsActive) {local.Dispose(); throw new InvalidOperationException("无法启用撤销事务。");}
            TransactionManager.CloseCurrentTransaction(true);
            var mark = TransactionManager.CurrentTransactionPosition;
            var file = Session.Instance.GetActiveDgnFile();
            PinnedGeometry lease = null;
            try
            {
                SelectionSetManager.EmptyAll();
                lease = new PinnedGeometry(local);
                leases.Add(lease);
                {
                    obj.SetNonParametricElement((NativeOPM::Bentley.DgnPlatform.EditElementHandle*)lease.Pin.AddrOfPinnedObject());
                    log.AppendLine("AfterSetNonParametricElement.IsParametric=" + obj.IsParametric);
                    if (obj.IsParametric) throw new InvalidOperationException("宿主未切换到自定义几何模式；本路线未通过，停止写入。日志可用于决定独立测试类回调方案。");
                    obj.Transform3d = transform;
                    obj.AllowGraphicsUpdate = true;
                    if (!new BMECObjectWriter(obj).Serialize()) throw new InvalidOperationException("手轮自定义几何序列化失败。");
                    log.AppendLine("ExplicitSerializeReturned=true");
                    ValidateSwap(model, wheelId, parentId, parentElementId, parentRange, sourceRange, log);
                    if (ElementId(Resolve(model, wheelId)) != originalWheelElementId)
                    using (var oldRoot = model.FindElementById(new ElementId(ref originalWheelElementId)))
                        if (oldRoot != null && oldRoot.IsValid && !oldRoot.IsDeleted)
                            throw new InvalidOperationException("替换产生新根，但旧手轮根仍存在，停止并回滚。");
                    // Consume the source only after native readback passes, in this same Undo step.
                    // Its placement ItemType is removed with its root, avoiding double counts.
                    var deleteStatus = source.DeleteFromModel();
                    if (deleteStatus != StatusInt.Success) throw new InvalidOperationException("源 CEL 删除失败：" + deleteStatus);
                    using (var remaining = model.FindElementById(new ElementId(ref sourceId)))
                        if (remaining != null && remaining.IsValid && !remaining.IsDeleted)
                            throw new InvalidOperationException("源 CEL 删除后仍可重读为有效根。");
                    if (Session.Instance.GetActiveDgnModel() != model || Session.Instance.GetActiveDgnFile() != file)
                        throw new InvalidOperationException("活动文档已改变。");
                    TransactionManager.CloseCurrentTransaction(true);
                }
                // End all pointer use before releasing the temporary descriptor.
                log.AppendLine("Committed; original HAND_WHEEL identity/relation retained; source CEL consumed in same transaction.");
                try { Utilities.ComApp.ActiveDesignFile.Views[1].Redraw(); }
                catch (Exception ex) { log.AppendLine("CommittedButViewRefreshFailed=" + ex.Message); }
            }
            catch (Exception error)
            {
                log.AppendLine("SwapError=" + error);
                try
                {
                    if (Session.Instance.GetActiveDgnModel() != model || Session.Instance.GetActiveDgnFile() != file)
                        throw new InvalidOperationException("活动文档改变，无法对其他文档回滚。");
                    if (TransactionManager.CancelToPosition(mark, false) != StatusInt.Success)
                        throw new InvalidOperationException("事务回滚返回失败。");
                    obj.Refresh(); obj.Resync();
                    var cached = api.ObjectCache.FindByInstanceId(wheelId);
                    if (cached != null && !ReferenceEquals(cached, obj)) {cached.Refresh(); cached.Resync();}
                    using (var readSource = model.FindElementById(new ElementId(ref sourceId)))
                        if (readSource == null || !readSource.IsValid || RangeError(Range(readSource), sourceRange) > 2)
                            throw new InvalidOperationException("源 CEL 未完整恢复。");
                    var readWheel = Resolve(model, wheelId);
                    if (Parent(readWheel).InstanceId != parentId || GeometrySignature(readWheel) != oldGeometry)
                        throw new InvalidOperationException("原手轮几何或关联未恢复。");
                    ulong readId = ElementId(readWheel);
                    using (var readElement = model.FindElementById(new ElementId(ref readId)))
                        if (RangeError(Range(readElement), oldWheelRange) > 2) throw new InvalidOperationException("原手轮图形范围未恢复。");
                    using (var parentElement = model.FindElementById(new ElementId(ref parentElementId)))
                        if (RangeError(Range(parentElement), parentRange) > 2) throw new InvalidOperationException("父阀门图形范围未恢复。");
                    log.AppendLine("RollbackVerified=true");
                }
                catch (Exception rollback)
                {
                    throw new AggregateException("替换失败，回滚尚未核实；请停止在此副本继续测试并保留日志。", error, rollback);
                }
                throw new InvalidOperationException("替换未通过，已回滚并核对原手轮和源 CEL：" + error.Message, error);
            }
            finally
            {
                if (lease == null) local.Dispose();
                // This is an in-memory host flag, not a saved actuator parameter.
                try {obj.AllowGraphicsUpdate = previousAllowGraphicsUpdate;}
                catch (Exception ex) {log.AppendLine("RestoreAllowGraphicsUpdateFailed=" + ex);}
            }
        }

        private static bool IsSourceCell(Element element)
        {
            var com = Utilities.ComApp.ActiveModelReference.GetElementByID64(checked((long)(ulong)element.ElementId));
            return com.IsCellElement() && !com.IsSharedCellElement() && !com.IsSmartSolidElement && com.AsCellElement().Name == CellName;
        }

        private static unsafe IECInstance Resolve(DgnModel model, string id)
        {
            // Query persistence by element; do not treat the mutated BMECObject's cache as readback.
            var instance = Bentley.OpenPlantModeler.SDK.Utilities.DgnUtilities.GetInstanceByInstanceId(id);
            if (instance != null && instance.InstanceId == id)
            {
                var elementRef = BMECApi.Instance.GetElementRef(instance);
                if (elementRef == null) throw new InvalidOperationException("原手轮没有持久图元。");
                using (var element = Element.GetFromElementRef((IntPtr)elementRef))
                {
                    if (element.GetNativeDgnModelRef() != ModelToken(model)) throw new InvalidOperationException("重读手轮来自其他模型。");
                    var fresh = Instance(element);
                    if (fresh != null && fresh.InstanceId == id) return fresh;
                }
            }
            throw new InvalidOperationException("无法从活动模型重读原手轮实例 " + id);
        }

        private static void ValidateSwap(DgnModel model, string id, string parentId, ulong parentElementId,
            DRange3d parentRange, DRange3d expected, StringBuilder log)
        {
            var wheel = Resolve(model, id);
            if (wheel.ClassDefinition.Name != "HAND_WHEEL" || Parent(wheel).InstanceId != parentId)
                throw new InvalidOperationException("手轮身份或父阀门关联改变。");
            string geometry = GeometrySignature(wheel);
            if (geometry == "null" || geometry == "missing" || geometry.StartsWith("0:", StringComparison.Ordinal))
                throw new InvalidOperationException("重读未发现已保存的 Geometry 二进制数据。");
            using (var read = new BMECObject(wheel))
            {
                log.AppendLine("DefaultReadback.IsParametric=" + read.IsParametric);
                if (read.IsParametric) throw new InvalidOperationException("默认方式重读后仍为参数化手轮；V2 未证明模式持久化，停止并回滚。");
            }
            var cached = BMECApi.Instance.ObjectCache.FindByInstanceId(id);
            if (cached != null)
            {
                cached.Refresh(); cached.Resync();
                log.AppendLine("DocumentCacheReadback.IsParametric=" + cached.IsParametric);
                if (cached.IsParametric) throw new InvalidOperationException("文档缓存重读仍为参数化手轮；V2 未证明后续交互可用，停止并回滚。");
            }
            ulong elementId = ElementId(wheel);
            double tolerance = Math.Max(2, model.GetModelInfo().UorPerMeter / 10000.0);
            using (var element = model.FindElementById(new ElementId(ref elementId)))
            {
                double error = RangeError(Range(element), expected);
                log.AppendLine("ReadbackElement=" + elementId + "; RangeErrorMm=" + error / (model.GetModelInfo().UorPerMeter / 1000.0));
                if (double.IsNaN(error) || double.IsInfinity(error) || error > tolerance)
                    throw new InvalidOperationException("重读几何包络与源 CEL 不一致。");
            }
            using (var parent = model.FindElementById(new ElementId(ref parentElementId)))
                if (RangeError(Range(parent), parentRange) > 2) throw new InvalidOperationException("父阀门几何范围发生改变。");
            log.AppendLine("GeometryAfter=" + geometry + "; ParentRelationCount=1; InstanceIdentityPreserved=true");
        }
    }
}
