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
        internal static IECInstance Selected()
        {
            var selected = DgnUtilities.GetSelectedInstances();
            if (selected == null || selected.Count != 1)
                throw new InvalidOperationException("请先用元素选择工具只选中一个对象：放置时选真实直管，检查时选试验A1。");
            return selected[0];
        }

        internal static Element ElementOf(IECInstance instance, bool writable)
        { return NativeSupportElements.Get(instance, writable); }

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

        internal static A1NativeTrialRecord Place(double? station, double angle, Action<string> log, bool nativeEditing = false)
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
                OriginalLengthMm = position.LengthMm, Tag = "A1TEST-" + Guid.NewGuid().ToString("N").Substring(0, 12),
                NativeEditing = nativeEditing, NativeClass = nativeEditing ? "SSP_A1_NATIVE_TEST" : "UBOLT_GUIDE" };
            double scale = Session.Instance.GetActiveDgnModel().GetModelInfo().UorPerMeter / 1000.0;
            A1NativeTrialCalculator.RequireFinite(scale);
            if (scale <= 0) throw new InvalidOperationException("模型单位无效。");
            var rotation = DMatrix3d.FromColumns(new DVector3d(position.Ux, position.Uy, 0),
                new DVector3d(-position.Uy, position.Ux, 0), new DVector3d(0, 0, 1));
            var transform = new DTransform3d(rotation) { Translation = new DPoint3d(position.X * scale, position.Y * scale, position.Z * scale) };
            var api = BMECApi.Instance;
            var instance = BMECInstanceManager.Instance.CreateECInstance(record.NativeClass, true);
            if (instance == null) throw new InvalidOperationException("当前工作集没有" + record.NativeClass + "类，请先部署对应试验Schema并重启OPM。");
            Set(instance, "NAME", record.Tag);
            Set(instance, "DESCRIPTION", nativeEditing ? "A1 NATIVE EDIT TRIAL " + plan.AssemblyTag : "A1原生关联试验 " + plan.AssemblyTag);
            if (nativeEditing)
            {
                NativeSupportData.RequireProperty(instance, "SSP_A1_DN");
                NativeSupportData.RequireProperty(instance, "SSP_A1_OPENING");
                NativeSupportData.RequireProperty(instance, "DEVICE_TYPE_CODE");
                NativeSupportData.RequireProperty(instance, "ALIAS");
                instance["SSP_A1_DN"].IntValue = dn.Value;
                instance["SSP_A1_OPENING"].DoubleValue = position.AngleDeg;
                Set(instance, "DEVICE_TYPE_CODE", NativePipeSupportDefinition.DeviceTypeCode);
                Set(instance, "ALIAS", plan.AssemblyTag);
            }
            if (nativeEditing) Set(instance, "NOMINAL_DIAMETER", dn.Value.ToString(CultureInfo.InvariantCulture));
            else instance["NOMINAL_DIAMETER"].DoubleValue = pipeInstance["NOMINAL_DIAMETER"].DoubleValue;
            Set(instance, "SPECIFICATION", pipeInstance["SPECIFICATION"].StringValue);
            Set(instance, "UBOLT_DIAMETER", plan.Row.Bolt.ToString(CultureInfo.InvariantCulture));
            Set(instance, "UBOLT_LENGTH", plan.Row.D.ToString(CultureInfo.InvariantCulture));
            Set(instance, "UBOLT_WIDTH", plan.Row.C.ToString(CultureInfo.InvariantCulture));
            log("开始：" + record.Tag + "，类型=" + record.NativeClass + "，管道=" + pipeInstance.InstanceId);
            NativePipeSupportWriter.Create(instance, pipeInstance, transform,
                new[] { position.X, position.Y, position.Z },
                () => new CellHeaderElement(Session.Instance.GetActiveDgnModel(), A1ClampCatalog.CellName,
                    DPoint3d.Zero, DMatrix3d.Identity, A1ClampBuilder.Build(plan, DPoint3d.Zero, new DVector3d(1, 0, 0))),
                (support, element) =>
                {
                    record.SupportInstanceId = support.Instance.InstanceId;
                    Statistics.AttachA1Clamp(element, plan);
                    A1NativeTrialStore.Write(element, record);
                    Check(support.Instance, record, log, true, false);
                }, () => { }, log, parametric: nativeEditing);
            log(nativeEditing ? "原生编辑试验A1已生成。请用OPM元素选择核对移动/旋转操作柄；CHECKEDIT检查编辑后的轴上位置及ISO点，CHECK检查初始站位随管移动。"
                : "写入完成；三维/EC关联、ISO支撑点和设计状态已检查。实际单线图和移动跟随仍须操作验证。");
            return record;
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

        internal static bool CheckSelected(Action<string> log, bool edited = false)
        {
            if (TransactionManager.IsUndoInProgress) throw new InvalidOperationException("请在撤销/重做完成后检查。");
            var instance = Selected();
            using (var element = ElementOf(instance, false))
                return Check(instance, A1NativeTrialStore.Read(element), log, false, edited);
        }

        private static bool Check(IECInstance support, A1NativeTrialRecord record, Action<string> log, bool requirePosition, bool edited)
        {
            if (support.ClassDefinition.Name != record.NativeClass || support.InstanceId != record.SupportInstanceId)
                throw new InvalidOperationException("试验记录与原生支吊架身份不匹配（复制件需重新建立试验）。");
            var api = BMECApi.Instance;
            var parents = api.GetRelatedInstances(support, "DEVICE_HAS_SUPPORT", false, true);
            if (parents == null || parents.Count != 1 || parents[0].InstanceId != record.PipeInstanceId)
                throw new InvalidOperationException("DEVICE_HAS_SUPPORT关系缺失或指向了其他对象。");
            var pipe = Pipe(parents[0]);
            if (edited && !record.NativeEditing) throw new InvalidOperationException("CHECKEDIT仅用于NATIVE命令生成的A1原生编辑试验件。");
            using (var acquired = PipeAlignment.OpenPlantObjectFactory.Acquire(support.InstanceId, support))
            {
                if (acquired.Object == null || !acquired.Object.IsValid) throw new InvalidOperationException("无法读取原生支吊架对象。");
                var current = acquired.Object.Instance;
                if (current == null || current.InstanceId != record.SupportInstanceId)
                    throw new InvalidOperationException("重新读取的支吊架对象与试验实例不一致。");
                double scale = Session.Instance.GetActiveDgnModel().GetModelInfo().UorPerMeter / 1000.0;
                var origin = acquired.Object.Transform3d.Translation;
                A1NativeTrialCalculator.RequireFinite(scale);
                if (scale <= 0) throw new InvalidOperationException("模型单位无效。");
                var axis = Position(pipe, null, record.AngleDeg);
                double actualStation = (origin.X / scale - pipe.StartX) * axis.Ux + (origin.Y / scale - pipe.StartY) * axis.Uy;
                A1NativeTrialCalculator.RequireFinite(actualStation);
                var position = Position(pipe, edited ? Math.Max(0, Math.Min(axis.LengthMm, actualStation)) : record.StationMm, record.AngleDeg);
                double dx = origin.X / scale - position.X, dy = origin.Y / scale - position.Y, dz = origin.Z / scale - position.Z;
                double error = Math.Sqrt(dx * dx + dy * dy + dz * dz);
                A1NativeTrialCalculator.RequireFinite(error);
                double isoX = NativeSupportData.ReadCoordinate(acquired.Object, "SUPPORT_POINT_X"),
                    isoY = NativeSupportData.ReadCoordinate(acquired.Object, "SUPPORT_POINT_Y"),
                    isoZ = NativeSupportData.ReadCoordinate(acquired.Object, "SUPPORT_POINT_Z");
                double isoError = Math.Sqrt(Math.Pow(isoX - position.X, 2) + Math.Pow(isoY - position.Y, 2) + Math.Pow(isoZ - position.Z, 2));
                A1NativeTrialCalculator.RequireFinite(isoError);
                NativeSupportData.RequireProperty(current, "STATE"); NativeSupportData.RequireProperty(current, "SHOP_FIELD");
                string state = current["STATE"].IsNull ? "" : current["STATE"].StringValue;
                string shop = current["SHOP_FIELD"].IsNull ? "" : current["SHOP_FIELD"].StringValue;
                bool design = string.Equals(state, "Design", StringComparison.OrdinalIgnoreCase),
                    shopMaterial = string.Equals(shop, "SHOP", StringComparison.OrdinalIgnoreCase);
                bool customGraphics = acquired.Object.IsParametric == record.NativeEditing;
                bool aligned = true;
                if (record.NativeEditing)
                {
                    var direction = acquired.Object.Transform3d.Matrix.ColumnX;
                    double dot = direction.X * axis.Ux + direction.Y * axis.Uy;
                    A1NativeTrialCalculator.RequireFinite(dot);
                    aligned = Math.Abs(dot - 1) <= 1e-6;
                    log("管轴/组件X轴对齐=" + (aligned ? "通过" : "不通过") + "；方向点积=" + dot.ToString("G17", CultureInfo.InvariantCulture));
                    log("组件变换=" + acquired.Object.Transform3d);
                    NativeSupportData.RequireProperty(current, "SSP_A1_DN");
                    NativeSupportData.RequireProperty(current, "SSP_A1_OPENING");
                    customGraphics &= current["SSP_A1_DN"].IntValue == record.Dn
                        && current["SSP_A1_OPENING"].DoubleValue == record.AngleDeg
                        && current["DEVICE_TYPE_CODE"].StringValue == NativePipeSupportDefinition.DeviceTypeCode
                        && current["ALIAS"].StringValue == A1ClampCalculator.Calculate(record.Dn, false, null, record.AngleDeg, "").AssemblyTag;
                    log("检查模式=" + (edited ? "编辑后轴上定位/ISO点（不判定原站位随动）" : "原站位随管移动")
                        + "；当前投影站位=" + actualStation.ToString("G17", CultureInfo.InvariantCulture) + " mm");
                }
                log("关系=通过；原生类型=" + support.ClassDefinition.Name + "；管道=" + record.PipeInstanceId);
                log("站位=" + record.StationMm.ToString("G17", CultureInfo.InvariantCulture) + " mm；三维位置误差=" + error.ToString("0.###", CultureInfo.InvariantCulture) + " mm");
                log("管长变化=" + (position.LengthMm - record.OriginalLengthMm).ToString("0.###", CultureInfo.InvariantCulture) + " mm（本轮先验证刚体平移/水平旋转）");
                log("SUPPORT_POINT原值=" + Text(current, "SUPPORT_POINT_X") + "," + Text(current, "SUPPORT_POINT_Y") + "," + Text(current, "SUPPORT_POINT_Z"));
                log("ISO支撑点(mm)=" + isoX.ToString("G17", CultureInfo.InvariantCulture) + "," + isoY.ToString("G17", CultureInfo.InvariantCulture) + "," + isoZ.ToString("G17", CultureInfo.InvariantCulture)
                    + "；位置误差=" + isoError.ToString("0.###", CultureInfo.InvariantCulture) + " mm；" + (isoError <= 1 ? "通过" : "不通过"));
                log("出图状态STATE=" + state + "；SHOP_FIELD=" + shop + "；" + (design && shopMaterial ? "通过" : "不通过：试验A1应为Design/SHOP，空状态可能被提取为既有构件。"));
                log(record.NativeEditing ? "原生A1组件类型/参数=" + (customGraphics ? "通过" : "不通过") + "；操作柄及A1螺杆/螺母完整性须目视核对。"
                    : customGraphics ? "图形类型=自定义非参数化外形（仍须目视核对A1细节）。" : "图形类型=原生参数化外形：A1自定义外形可能已被重生成，请核查。");
                log(error <= 1 ? "三维当前位置=通过（1 mm容差）；旋转姿态和三维外形需目视核对。"
                    : edited ? "三维当前位置=不通过：编辑后定位点脱离当前管轴段。"
                    : "三维当前位置=不通过：原生跟随未保持试验站位，勿据此宣称已实现跟随。");
                log("ISO检查结果见上；符号、编号标注和材料表需重新提取实测，CHECK不会修改对象或自动纠正随动。");
                if (requirePosition && error > 1) throw new InvalidOperationException("原生支吊架初始坐标与目标管轴站位不一致。");
                if (requirePosition && isoError > 1) throw new InvalidOperationException("ISO支撑点与目标管轴站位不一致。");
                if (requirePosition && (!design || !shopMaterial)) throw new InvalidOperationException("A1出图状态未能保存为Design/SHOP。");
                if (requirePosition && (!customGraphics || !aligned)) throw new InvalidOperationException("原生A1组件类型、参数或管轴方向不一致。");
                return error <= 1 && isoError <= 1 && design && shopMaterial && customGraphics && aligned;
            }
        }

        private static string Text(IECInstance instance, string name)
        { try { return instance[name].DoubleValue.ToString("G17", CultureInfo.InvariantCulture); } catch { return "不可读"; } }
    }
}
