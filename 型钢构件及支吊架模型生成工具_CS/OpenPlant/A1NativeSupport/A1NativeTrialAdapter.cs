using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.ECObjects.Instance;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
using Bentley.OpenPlant.Modeler.Api;
using Bentley.OpenPlantModeler.SDK.Utilities;

namespace SteelSectionProbe
{
    internal static class A1NativeTrialAdapter
    {
        // A failed native rollback may leave a model object without cache ownership.
        // Keep its wrapper alive until the host closes rather than finalizing it early.
        private static readonly List<BMECObject> unrecovered = new List<BMECObject>();

        internal static IECInstance Selected()
        {
            var selected = DgnUtilities.GetSelectedInstances();
            if (selected == null || selected.Count != 1)
                throw new InvalidOperationException("请先用元素选择工具只选中一个对象：放置时选真实直管，检查时选试验A1。");
            return selected[0];
        }

        internal static unsafe Element ElementOf(IECInstance instance, bool writable)
        {
            var api = BMECApi.Instance;
            var elementRef = api.GetElementRef(instance);
            if (elementRef == null) throw new InvalidOperationException("业务对象没有有效的图形元素。");
            var element = Element.GetFromElementRef((IntPtr)elementRef);
            var active = Session.Instance.GetActiveDgnModel();
            if (element == null || !element.IsValid || active == null || !active.Is3d
                || element.GetNativeDgnModelRef() != (IntPtr)DgnModelRef.GetNativeDgnModelRefP(active, false))
            {
                element?.Dispose();
                throw new InvalidOperationException("本次试验仅支持活动三维模型，不支持参考文件。");
            }
            if (writable && (element.IsEffectivelyLocked(true, true) || !api.IsInstanceModifiable(instance)))
            {
                element.Dispose();
                throw new InvalidOperationException("所选对象被锁定或不可写。");
            }
            return element;
        }

        private static PipeClampSelection Pipe(IECInstance instance)
        {
            if (instance == null || instance.ClassDefinition.Name != "PIPE")
                throw new InvalidOperationException("请选择OpenPlant真实直管，本次不接受普通辅助线或弯头。");
            using (var element = ElementOf(instance, true))
            {
                var selected = PipeClampReader.Read((ulong)element.ElementId, 0, 0, 0);
                if (!selected.IsPipe || selected.IsFromReference || (selected.AxisNote ?? "").Contains("近似"))
                    throw new InvalidOperationException("无法可靠读取活动模型中的真实管轴。");
                if (!selected.NominalMm.HasValue || !selected.OutsideMm.HasValue)
                    throw new InvalidOperationException("管道公称直径或外径缺失。");
                A1NativeTrialCalculator.RequireFinite(selected.NominalMm.Value);
                A1NativeTrialCalculator.RequireFinite(selected.OutsideMm.Value);
                A1NativeTrialCalculator.RequireFinite(selected.InsulationMm ?? 0);
                if (selected.NominalMm <= 0 || selected.OutsideMm <= 0 || selected.InsulationMm < 0)
                    throw new InvalidOperationException("管道直径或保温厚度无效。");
                return selected;
            }
        }

        private static A1NativeTrialPosition Position(PipeClampSelection pipe, double? station, double angle)
        { return A1NativeTrialCalculator.Calculate(new[] { pipe.StartX, pipe.StartY, pipe.StartZ },
            new[] { pipe.EndX, pipe.EndY, pipe.EndZ }, station, angle); }

        internal static A1NativeTrialRecord Place(double? station, double angle, Action<string> log)
        {
            if (!LicenseService.IsActivated) throw new InvalidOperationException("请先激活软件。");
            if (TransactionManager.IsUndoInProgress) throw new InvalidOperationException("正在撤销/重做，请稍后再试。");
            var pipeInstance = Selected();
            var pipe = Pipe(pipeInstance);
            var position = Position(pipe, station, angle);
            int? dn = A1ClampCatalog.MatchDn(pipe.NominalMm);
            if (!dn.HasValue || Math.Abs(dn.Value - pipe.NominalMm.Value) > .5)
                throw new InvalidOperationException("A1目录没有与管道公称直径准确匹配的规格。");
            var plan = A1ClampCalculator.Calculate(dn.Value, true, pipe.NominalMm, position.AngleDeg, pipe.PipeNumber);
            if (Math.Abs(plan.Row.OutsideMm - pipe.OutsideMm.Value) > 1 || (pipe.InsulationMm ?? 0) > .01)
                throw new InvalidOperationException("本次请使用外径与A1标准表匹配的无保温直管。");
            var record = new A1NativeTrialRecord { PipeInstanceId = pipeInstance.InstanceId,
                StationMm = position.StationMm, AngleDeg = position.AngleDeg, Dn = dn.Value,
                OriginalLengthMm = position.LengthMm, Tag = "A1TEST-" + Guid.NewGuid().ToString("N").Substring(0, 12) };
            double scale = Session.Instance.GetActiveDgnModel().GetModelInfo().UorPerMeter / 1000.0;
            A1NativeTrialCalculator.RequireFinite(scale);
            if (scale <= 0) throw new InvalidOperationException("模型单位无效。");
            var rotation = DMatrix3d.FromColumns(new DVector3d(position.Ux, position.Uy, 0),
                new DVector3d(-position.Uy, position.Ux, 0), new DVector3d(0, 0, 1));
            var transform = new DTransform3d(rotation) { Translation = new DPoint3d(position.X * scale, position.Y * scale, position.Z * scale) };
            var api = BMECApi.Instance;
            var instance = BMECInstanceManager.Instance.CreateECInstance(record.NativeClass, true);
            if (instance == null) throw new InvalidOperationException("当前工作集没有UBOLT_GUIDE类。");
            Set(instance, "NAME", record.Tag); Set(instance, "DESCRIPTION", "A1原生关联试验 " + plan.AssemblyTag);
            instance["NOMINAL_DIAMETER"].DoubleValue = pipeInstance["NOMINAL_DIAMETER"].DoubleValue;
            Set(instance, "SPECIFICATION", pipeInstance["SPECIFICATION"].StringValue);
            Set(instance, "UBOLT_DIAMETER", plan.Row.Bolt.ToString(CultureInfo.InvariantCulture));
            Set(instance, "UBOLT_LENGTH", plan.Row.D.ToString(CultureInfo.InvariantCulture));
            Set(instance, "UBOLT_WIDTH", plan.Row.C.ToString(CultureInfo.InvariantCulture));
            BMECObject support = null;
            int cacheKey = -1;
            if (!TransactionManager.IsActive) TransactionManager.Activate();
            if (!TransactionManager.IsActive) throw new InvalidOperationException("无法启用模型撤销事务。");
            TransactionManager.CloseCurrentTransaction(true);
            var mark = TransactionManager.CurrentTransactionPosition;
            bool deferred = api.DeferCommits;
            log("写入前DeferCommits=" + deferred + "；本次创建临时使用立即提交，不提交全局待处理集合。");
            try
            {
                // Like pipe editing, native Create/Serialize otherwise only enqueue the object.
                // In that state a successful return can still leave InstanceId="mechanical".
                api.DeferCommits = false;
                support = new BMECObject(instance, true);
                log("开始：" + record.Tag + "，类型=" + record.NativeClass + "，管道=" + pipeInstance.InstanceId);
                support.RelatedInstance = pipeInstance;
                using (var graphics = new CellHeaderElement(Session.Instance.GetActiveDgnModel(), A1ClampCatalog.CellName,
                    DPoint3d.Zero, DMatrix3d.Identity, A1ClampBuilder.Build(plan, DPoint3d.Zero, new DVector3d(1, 0, 0))))
                {
                    A1NativeGraphics.Create(support, graphics, transform, log, () =>
                    {
                        record.SupportInstanceId = support.Instance.InstanceId;
                        log("原生实例=" + record.SupportInstanceId);
                        if (!api.IsPersistentId(record.SupportInstanceId))
                            throw new InvalidOperationException("原生创建返回成功，但实例仍未持久化：" + record.SupportInstanceId);
                        log("阶段=读取支吊架业务信息");
                        api.FindAllInformationOnInstance(support.Instance);
                        api.GetSectionalDataForSupport(support.Instance);
                        WriteIsoData(support, position);
                        if (!new BMECObjectWriter(support).Serialize()) throw new InvalidOperationException("原生支吊架业务数据写入失败。");
                        log("阶段=业务信息已保存；实例=" + support.Instance.InstanceId);
                        cacheKey = api.ObjectCache.Add(support);
                        if (cacheKey < 0) throw new InvalidOperationException("原生支吊架未能加入文档对象缓存。");
                        using (var element = ElementOf(support.Instance, true))
                        {
                            log("新元素=" + (ulong)element.ElementId);
                            Statistics.AttachA1Clamp(element, plan);
                            A1NativeTrialStore.Write(element, record);
                        }
                        Check(support.Instance, record, log, true);
                    });
                }
                TransactionManager.CloseCurrentTransaction(true);
                // Cache now owns the successfully created document object.
                log("写入完成；三维/EC关联、ISO支撑点和设计状态已检查。实际单线图和移动跟随仍须操作验证。");
                return record;
            }
            catch (Exception error)
            {
                StatusInt rollback;
                try { rollback = TransactionManager.CancelToPosition(mark, false); }
                catch (Exception rollbackError)
                {
                    RetainForRecovery(support, cacheKey, log);
                    throw new AggregateException("A1试验失败且回滚未完成，请立即检查模型。", error, rollbackError);
                }
                if (rollback != StatusInt.Success)
                {
                    RetainForRecovery(support, cacheKey, log);
                    throw new InvalidOperationException("A1试验失败且回滚未完成，请立即检查模型：" + rollback, error);
                }
                if (cacheKey >= 0) api.ObjectCache.Remove(cacheKey);
                if (support != null) support.Dispose();
                throw new InvalidOperationException("A1试验失败，已回滚本次写入：" + error.Message, error);
            }
            finally
            {
                api.DeferCommits = deferred;
                log("已恢复DeferCommits=" + deferred);
            }
        }

        private static void RetainForRecovery(BMECObject support, int cacheKey, Action<string> log)
        {
            if (support != null && cacheKey < 0) unrecovered.Add(support);
            log("回滚失败；保留对象所有权，请按上方试验标签/实例/元素ID检查残留对象。");
        }

        private static void Set(IECInstance instance, string name, string value)
        {
            var definition = instance.ClassDefinition.Properties(true).FirstOrDefault(item => item.Name == name);
            if (definition == null) return;
            var property = instance[name];
            if (string.Equals(definition.Type.Name, "double", StringComparison.OrdinalIgnoreCase))
                property.DoubleValue = A1NativeTrialCalculator.Parse(value);
            else property.StringValue = value ?? "";
        }

        private static void RequireProperty(IECInstance instance, string name)
        {
            if (!instance.ClassDefinition.Properties(true).Any(item => item.Name == name))
                throw new InvalidOperationException("当前工作集缺少A1出图必需属性：" + name);
        }

        private static void WriteIsoData(BMECObject support, A1NativeTrialPosition position)
        {
            foreach (string name in new[] { "STATE", "SHOP_FIELD", "SUPPORT_POINT_X", "SUPPORT_POINT_Y", "SUPPORT_POINT_Z" })
                RequireProperty(support.Instance, name);
            // Empty STATE maps to IE_EXISTING=1 in the project's ISO schema.
            support.Instance["STATE"].StringValue = "Design";
            support.Instance["SHOP_FIELD"].StringValue = "SHOP";
            // Schema storage units can differ from both millimetres and model UORs.
            if (!support.SetDoubleValueFromMM("SUPPORT_POINT_X", position.X)
                || !support.SetDoubleValueFromMM("SUPPORT_POINT_Y", position.Y)
                || !support.SetDoubleValueFromMM("SUPPORT_POINT_Z", position.Z))
                throw new InvalidOperationException("A1的ISO支撑点坐标写入失败。");
        }

        private static double ReadIsoCoordinate(BMECObject support, string name)
        {
            RequireProperty(support.Instance, name);
            if (support.Instance[name].IsNull) throw new InvalidOperationException("A1的ISO支撑点坐标为空：" + name);
            double value = support.GetDoubleValueInMM(name);
            A1NativeTrialCalculator.RequireFinite(value);
            return value;
        }

        internal static bool CheckSelected(Action<string> log)
        {
            if (TransactionManager.IsUndoInProgress) throw new InvalidOperationException("请在撤销/重做完成后检查。");
            var instance = Selected();
            using (var element = ElementOf(instance, false))
                return Check(instance, A1NativeTrialStore.Read(element), log, false);
        }

        private static bool Check(IECInstance support, A1NativeTrialRecord record, Action<string> log, bool requirePosition)
        {
            if (support.ClassDefinition.Name != record.NativeClass || support.InstanceId != record.SupportInstanceId)
                throw new InvalidOperationException("试验记录与原生支吊架身份不匹配（复制件需重新建立试验）。");
            var api = BMECApi.Instance;
            var parents = api.GetRelatedInstances(support, "DEVICE_HAS_SUPPORT", false, true);
            if (parents == null || parents.Count != 1 || parents[0].InstanceId != record.PipeInstanceId)
                throw new InvalidOperationException("DEVICE_HAS_SUPPORT关系缺失或指向了其他对象。");
            var pipe = Pipe(parents[0]);
            var position = Position(pipe, record.StationMm, record.AngleDeg);
            using (var acquired = PipeAlignment.OpenPlantObjectFactory.Acquire(support.InstanceId, support))
            {
                if (acquired.Object == null || !acquired.Object.IsValid) throw new InvalidOperationException("无法读取原生支吊架对象。");
                var current = acquired.Object.Instance;
                if (current == null || current.InstanceId != record.SupportInstanceId)
                    throw new InvalidOperationException("重新读取的支吊架对象与试验实例不一致。");
                double scale = Session.Instance.GetActiveDgnModel().GetModelInfo().UorPerMeter / 1000.0;
                var origin = acquired.Object.Transform3d.Translation;
                double dx = origin.X / scale - position.X, dy = origin.Y / scale - position.Y, dz = origin.Z / scale - position.Z;
                double error = Math.Sqrt(dx * dx + dy * dy + dz * dz);
                A1NativeTrialCalculator.RequireFinite(error);
                double isoX = ReadIsoCoordinate(acquired.Object, "SUPPORT_POINT_X"),
                    isoY = ReadIsoCoordinate(acquired.Object, "SUPPORT_POINT_Y"),
                    isoZ = ReadIsoCoordinate(acquired.Object, "SUPPORT_POINT_Z");
                double isoError = Math.Sqrt(Math.Pow(isoX - position.X, 2) + Math.Pow(isoY - position.Y, 2) + Math.Pow(isoZ - position.Z, 2));
                A1NativeTrialCalculator.RequireFinite(isoError);
                RequireProperty(current, "STATE"); RequireProperty(current, "SHOP_FIELD");
                string state = current["STATE"].IsNull ? "" : current["STATE"].StringValue;
                string shop = current["SHOP_FIELD"].IsNull ? "" : current["SHOP_FIELD"].StringValue;
                bool design = string.Equals(state, "Design", StringComparison.OrdinalIgnoreCase),
                    shopMaterial = string.Equals(shop, "SHOP", StringComparison.OrdinalIgnoreCase);
                bool customGraphics = !acquired.Object.IsParametric;
                log("关系=通过；原生类型=" + support.ClassDefinition.Name + "；管道=" + record.PipeInstanceId);
                log("站位=" + record.StationMm.ToString("G17", CultureInfo.InvariantCulture) + " mm；三维位置误差=" + error.ToString("0.###", CultureInfo.InvariantCulture) + " mm");
                log("管长变化=" + (position.LengthMm - record.OriginalLengthMm).ToString("0.###", CultureInfo.InvariantCulture) + " mm（本轮先验证刚体平移/水平旋转）");
                log("SUPPORT_POINT原值=" + Text(current, "SUPPORT_POINT_X") + "," + Text(current, "SUPPORT_POINT_Y") + "," + Text(current, "SUPPORT_POINT_Z"));
                log("ISO支撑点(mm)=" + isoX.ToString("G17", CultureInfo.InvariantCulture) + "," + isoY.ToString("G17", CultureInfo.InvariantCulture) + "," + isoZ.ToString("G17", CultureInfo.InvariantCulture)
                    + "；位置误差=" + isoError.ToString("0.###", CultureInfo.InvariantCulture) + " mm；" + (isoError <= 1 ? "通过" : "不通过"));
                log("出图状态STATE=" + state + "；SHOP_FIELD=" + shop + "；" + (design && shopMaterial ? "通过" : "不通过：试验A1应为Design/SHOP，空状态可能被提取为既有构件。"));
                log(customGraphics ? "图形类型=自定义非参数化外形（仍须目视核对A1细节）。" : "图形类型=原生参数化外形：A1自定义外形可能已被重生成，请核查。");
                log(error <= 1 ? "三维当前位置=通过（1 mm容差）；旋转姿态和三维外形需目视核对。" : "三维当前位置=不通过：原生跟随未保持试验站位，勿据此宣称已实现跟随。");
                log("ISO检查结果见上；符号、编号标注和材料表需重新提取实测，CHECK不会修改对象或自动纠正随动。");
                if (requirePosition && error > 1) throw new InvalidOperationException("原生支吊架初始坐标与目标管轴站位不一致。");
                if (requirePosition && isoError > 1) throw new InvalidOperationException("ISO支撑点与目标管轴站位不一致。");
                if (requirePosition && (!design || !shopMaterial)) throw new InvalidOperationException("A1出图状态未能保存为Design/SHOP。");
                if (requirePosition && !customGraphics) throw new InvalidOperationException("原生组件没有保留自定义A1外形类型。");
                return error <= 1 && isoError <= 1 && design && shopMaterial && customGraphics;
            }
        }

        private static string Text(IECInstance instance, string name)
        { try { return instance[name].DoubleValue.ToString("G17", CultureInfo.InvariantCulture); } catch { return "不可读"; } }
    }
}
