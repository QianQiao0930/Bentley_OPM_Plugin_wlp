using System;
using System.Collections.Generic;
using System.Linq;
using Bentley.DgnPlatformNET;
using Bentley.ECObjects.Instance;
using Bentley.GeometryNET;
using Bentley.OpenPlant.Modeler.Api;

namespace SteelSectionProbe
{
    internal static class Program
    {
        private static int checks;
        private static void Check(bool pass, string label) { checks++; if (!pass) throw new Exception(label); }
        private static void Reject(Action action, string label)
        { bool failed = false; try { action(); } catch (InvalidOperationException) { failed = true; } Check(failed, label); }
        private static void Log(string text) { }
        private static A1NativeTrialRecord Place(double? station = null, double angle = 0) { return A1NativeTrialAdapter.Place(station, angle, Log); }
        private static void SelectTrial(A1NativeTrialRecord record) { World.Selected = new List<IECInstance> { World.Instances[record.SupportInstanceId] }; }
        private static int Main()
        {
            try
            {
                var setupValues = new ParametricSetupValues { Source = new IECInstance("SSP_A1_NATIVE_TEST", "mechanical") };
                setupValues.Source["SSP_A1_DN"].IntValue = 100;
                setupValues.Source["SSP_A1_OPENING"].DoubleValue = 90;
                var script = new A1NativeParametricComponent { BMECObject = setupValues };
                script.Setup();
                Check(script.HostCalls == 0 && script.LengthCalls == 0, "真实Setup在构造期不访问尚未绑定的父管或写长度");
                Check(script.PlanForCheck.Row.Dn == 100 && script.PlanForCheck.AngleDeg == 90, "构造期仍验证自身A1参数");
                script.Setup(); Check(script.HostCalls == 0, "重复Setup不提前初始化父管");
                Reject(() => script.PrepareGraphics(), "真正生成几何时仍拒绝缺失父管");
                Check(script.HostCalls == 1 && script.LengthCalls == 0, "缺父管不写支架长度");
                setupValues.ParentReady = true; script.PrepareGraphics();
                Check(script.HostCalls == 2 && script.LengthCalls == 1 && script.SupportLength == 115, "绑定后保留原生父管端口初始化及支架长度");
                setupValues.Source["SSP_A1_DN"].IntValue = 200; script.PrepareGraphics();
                Check(script.PlanForCheck.Row.Dn == 200 && script.SupportLength == 180, "后续原生重生成仍重读参数");
                int hostCalls = script.HostCalls;
                setupValues.Source["SSP_A1_DN"].IntValue = 999;
                Reject(() => script.Setup(), "无效DN不被构造期延迟策略吞掉");
                Check(script.HostCalls == hostCalls && A1NativeParametricComponent.SetupFailures.Count > 0, "参数失败记录日志且不访问父管");
                setupValues.Source["SSP_A1_DN"].IntValue = 100; setupValues.Source["SSP_A1_OPENING"].DoubleValue = double.NaN;
                Reject(() => script.Setup(), "非法开口角仍明确拒绝");
                foreach (double scale in new[] { 1d, 1000d, 10000d })
                foreach (double isoUnitMm in new[] { 1d, 25.4d, 1000d })
                foreach (int heading in new[] { 0, 90, 180, 270 })
                foreach (double angle in new[] { 0d, 90d, 359d })
                {
                    World.Reset(); Bentley.MstnPlatformNET.Session.Instance.Model.Scale = scale;
                    World.SupportPointMmPerUnit = isoUnitMm;
                    double theta = heading * Math.PI / 180;
                    World.Pipe.EndX = World.Pipe.StartX + 1000 * Math.Cos(theta);
                    World.Pipe.EndY = World.Pipe.StartY + 1000 * Math.Sin(theta);
                    var record = Place(300, angle);
                    Check(World.Elements.Count == 2 && !World.Created.Disposed, "创建一个原生A1并交给缓存");
                    Check(record.Dn == 100 && record.StationMm == 300 && record.AngleDeg == angle, "记录真实参数");
                    Check(Math.Abs(World.Created.Transform3d.Translation.X / scale - (1000 + 300 * Math.Cos(theta))) < 1e-7, "UOR定位X");
                    Check(Math.Abs(World.Created.Transform3d.Translation.Y / scale - (2000 + 300 * Math.Sin(theta))) < 1e-7, "UOR定位Y");
                    Check(Math.Abs(World.Created.Transform3d.Matrix.X.X - Math.Cos(theta)) < 1e-8, "管轴坐标框架");
                    Check(World.Created.Instance["STATE"].StringValue == "Design" && World.Created.Instance["SHOP_FIELD"].StringValue == "SHOP", "新设计件进入Shop材料规则");
                    Check(Math.Abs(World.Created.Instance["SUPPORT_POINT_X"].DoubleValue * isoUnitMm - (1000 + 300 * Math.Cos(theta))) < 1e-7, "ISO X用Schema单位保存而不是UOR");
                    Check(Math.Abs(World.Created.Instance["SUPPORT_POINT_Y"].DoubleValue * isoUnitMm - (2000 + 300 * Math.Sin(theta))) < 1e-7, "ISO Y单位独立");
                    Check(Math.Abs(World.Created.GetDoubleValueInMM("SUPPORT_POINT_Z") - 3000) < 1e-7, "ISO Z保留非零标高");
                    var element = World.Find(World.Created.Instance);
                    Check(A1NativeTrialStore.Read(element).SupportInstanceId == record.SupportInstanceId && element.MaterialTag.StartsWith("A1-"), "模型内参数和原材料清单共存");
                    SelectTrial(record); Check(A1NativeTrialAdapter.CheckSelected(Log), "初始关联和位置可读");
                    World.Pipe.StartX += 200; World.Pipe.EndX += 200;
                    Check(!A1NativeTrialAdapter.CheckSelected(Log), "管动夹不动必须报告不通过");
                    var transform = World.Created.Transform3d; transform.Translation.X += 200 * scale; World.Created.Transform3d = transform;
                    double oldIsoX = World.Created.Instance["SUPPORT_POINT_X"].DoubleValue;
                    Check(!A1NativeTrialAdapter.CheckSelected(Log), "三维跟随但ISO支点未跟随必须报告不通过");
                    Check(World.Created.Instance["SUPPORT_POINT_X"].DoubleValue == oldIsoX, "CHECK只读不暗中补偿ISO支点");
                    World.Created.SetDoubleValueFromMM("SUPPORT_POINT_X", (1000 + 300 * Math.Cos(theta)) + 200);
                    Check(A1NativeTrialAdapter.CheckSelected(Log), "三维和ISO同时跟随时位置通过");
                    World.Created.Instance.Parametric = true;
                    Check(!A1NativeTrialAdapter.CheckSelected(Log), "外形被原生参数化替换时报告不通过");
                }
                foreach (string stage in new[] { "Create", "Serialize", "Cache", "Statistics", "Metadata", "Relationship", "WrongOrigin", "Parametric", "IsoPointWrite", "IsoPointDropped", "StateDropped", "MissingIsoProperty" })
                {
                    World.Reset(); World.Fault = stage; BMECApi.Instance.DeferCommits = true;
                    Reject(() => Place(), "故障明确失败 " + stage);
                    Check(World.Elements.Count == 1 && World.Elements.ContainsKey(1), "失败回收新元素且保留原管 " + stage);
                    Check(World.Created == null || World.Created.Disposed, "失败释放本次对象 " + stage);
                    Check(BMECApi.Instance.DeferCommits, "失败恢复宿主延迟提交开关 " + stage);
                }
                World.Reset(); BMECApi.Instance.DeferCommits = true;
                var deferred = Place();
                Check(World.Elements.Count == 2 && BMECApi.Instance.IsPersistentId(deferred.SupportInstanceId), "宿主延迟提交开启时仍创建真实模型实例");
                Check(BMECApi.Instance.DeferCommits, "成功恢复宿主延迟提交开关");
                World.Reset(); var stale = Place(); SelectTrial(stale);
                foreach (string state in new[] { "", "EXISTING", "FOR_DEMOLITION" })
                { World.Created.Instance["STATE"].StringValue = state; Check(!A1NativeTrialAdapter.CheckSelected(Log), "空白/既有/拆除状态不能通过新设计件检查"); }
                World.Created.Instance["STATE"].StringValue = "Design";
                World.Created.Instance["SUPPORT_POINT_X"].DoubleValue = 0;
                Check(!A1NativeTrialAdapter.CheckSelected(Log), "旧试验零支撑点不能因三维位置正确而通过");
                World.Created.Instance["SUPPORT_POINT_X"].Clear();
                Reject(() => A1NativeTrialAdapter.CheckSelected(Log), "缺失坐标明确失败");
                World.Created.Instance["SUPPORT_POINT_X"].DoubleValue = double.NaN;
                Reject(() => A1NativeTrialAdapter.CheckSelected(Log), "非有限ISO坐标明确失败");
                World.Reset(); World.Pipe.StartX = -500; World.Pipe.EndX = 500;
                World.Pipe.StartY = World.Pipe.EndY = World.Pipe.StartZ = World.Pipe.EndZ = 0;
                var originTrial = Place(); SelectTrial(originTrial);
                Check(A1NativeTrialAdapter.CheckSelected(Log) && World.Created.GetDoubleValueInMM("SUPPORT_POINT_X") == 0, "真实站位在原点时允许零支撑点");
                World.Reset(); World.Fault = "Metadata"; World.FailRollback = true;
                try { Place(); throw new Exception("回滚错误未暴露"); }
                catch (InvalidOperationException e) { Check(e.Message.Contains("回滚未完成"), "回滚失败不能谎称已恢复"); }
                Check(World.Elements.Count == 2 && !World.Created.Disposed, "回滚失败保留模型及缓存对象所有权");
                World.Reset(); LicenseService.IsActivated = false; Reject(() => Place(), "未激活不写入"); Check(World.Elements.Count == 1, "未激活保留模型");
                World.Reset(); World.Selected.Clear(); Reject(() => Place(), "无选择拒绝");
                World.Reset(); World.Selected.Add(World.Source); Reject(() => Place(), "多选拒绝");
                World.Reset(); World.Source.ClassDefinition.Name = "ELBOW"; Reject(() => Place(), "弯头拒绝");
                World.Reset(); World.Elements[1].Model = new DgnModel { Handle = 2 }; Reject(() => Place(), "参考模型拒绝");
                World.Reset(); World.Elements[1].Locked = true; Reject(() => Place(), "锁定管道拒绝");
                World.Reset(); World.Pipe.EndZ += 1; Reject(() => Place(), "斜管拒绝");
                World.Reset(); World.Pipe.InsulationMm = 20; Reject(() => Place(), "保温管拒绝");
                World.Reset(); World.Pipe.OutsideMm = 100; Reject(() => Place(), "外径不匹配拒绝");
                World.Reset(); World.Pipe.OutsideMm = double.NaN; Reject(() => Place(), "外径非有限拒绝");
                World.Reset(); World.Pipe.InsulationMm = double.NaN; Reject(() => Place(), "保温非有限拒绝");
                World.Reset(); Reject(() => Place(-1), "站位负数拒绝"); Reject(() => Place(1001), "超管长拒绝");
                foreach (double value in new[] { double.NaN, double.PositiveInfinity, double.NegativeInfinity })
                { World.Reset(); Reject(() => Place(null, value), "非法角度"); Reject(() => Place(value), "非法站位"); }
                World.Reset(); var middle = Place(); Check(middle.StationMm == 500, "缺省中点");
                SelectTrial(middle); World.Created.Instance.Parent = new IECInstance("PIPE", "wrong"); Reject(() => A1NativeTrialAdapter.CheckSelected(Log), "错误父管道不可通过");
                World.Reset(); var copied = Place(); SelectTrial(copied); World.Created.Instance.InstanceId = "copied"; Reject(() => A1NativeTrialAdapter.CheckSelected(Log), "复制件标识冲突不可通过");
                World.Reset(); var undo = Place(); SelectTrial(undo); World.Elements.Remove(World.Find(World.Created.Instance).ElementId); Reject(() => A1NativeTrialAdapter.CheckSelected(Log), "撤销删除后不能使用旧对象");
                foreach (string text in new[] { "NaN", "Infinity", "a", "1,2", "" }) Reject(() => A1NativeTrialCalculator.Parse(text), "非法命令参数 " + text);
                foreach (double scale in new[] { 1d, 1000d, 10000d })
                foreach (double isoUnit in new[] { 1d, 25.4d, 1000d })
                {
                    World.Reset(); Bentley.MstnPlatformNET.Session.Instance.Model.Scale = scale; World.SupportPointMmPerUnit = isoUnit;
                    BMECApi.Instance.DeferCommits = true;
                    var native = A1NativeTrialAdapter.Place(300, 90, Log, true); SelectTrial(native);
                    Check(native.NativeEditing && native.NativeClass == "SSP_A1_NATIVE_TEST", "新试验使用隔离的原生组件类");
                    Check(World.Created.IsParametric && BMECApi.Instance.DeferCommits, "原生试验保留参数化入口并恢复宿主提交开关");
                    Check(A1NativeTrialAdapter.CheckSelected(Log), "新组件初始位置/类型/参数及ISO检查");
                    Check(A1NativeTrialAdapter.CheckSelected(Log, true), "编辑模式初始轴上定位及ISO检查");
                    Check(A1NativeTrialStore.Read(World.Find(World.Created.Instance)).NativeEditing, "新JSON记录模式往返");
                    var transform = World.Created.Transform3d; transform.Translation.X += 50 * scale; World.Created.Transform3d = transform;
                    Check(!A1NativeTrialAdapter.CheckSelected(Log, true), "操作柄移动后ISO点未更新不能通过");
                    double staleIso = World.Created.GetDoubleValueInMM("SUPPORT_POINT_X");
                    Check(staleIso == 1300, "CHECKEDIT不修补ISO点");
                    World.Created.SetDoubleValueFromMM("SUPPORT_POINT_X", 1350);
                    Check(A1NativeTrialAdapter.CheckSelected(Log, true), "沿轴移动后用当前轴上位置校验");
                    Check(!A1NativeTrialAdapter.CheckSelected(Log), "编辑检查通过不等于原站位随动通过");
                    transform.Translation.Y += 2 * scale; World.Created.Transform3d = transform;
                    World.Created.SetDoubleValueFromMM("SUPPORT_POINT_Y", 2002);
                    Check(!A1NativeTrialAdapter.CheckSelected(Log, true), "脱离管轴即使三维ISO同步也拒绝");
                    transform.Translation.Y -= 2 * scale; transform.Matrix = DMatrix3d.FromColumns(new DVector3d(0, 1, 0),new DVector3d(-1,0,0),new DVector3d(0,0,1));
                    World.Created.Transform3d = transform; World.Created.SetDoubleValueFromMM("SUPPORT_POINT_Y", 2000);
                    Check(!A1NativeTrialAdapter.CheckSelected(Log, true), "组件管轴方向错误不能通过");
                }
                foreach (string fault in new[] { "Create", "Serialize", "Cache", "Statistics", "Metadata", "Relationship", "Parametric", "IsoPointWrite", "IsoPointDropped", "StateDropped", "MissingIsoProperty", "AliasDropped", "MarkerDropped" })
                {
                    World.Reset(); World.Fault = fault; BMECApi.Instance.DeferCommits = true;
                    Reject(() => A1NativeTrialAdapter.Place(null, 0, Log, true), "新组件故障拒绝 " + fault);
                    Check(World.Elements.Count == 1 && BMECApi.Instance.DeferCommits, "新组件失败回滚并恢复提交开关 " + fault);
                }
                World.Reset(); var legacy = Place(); SelectTrial(legacy);
                Reject(() => A1NativeTrialAdapter.CheckSelected(Log, true), "不对旧试验件使用CHECKEDIT");
                Console.WriteLine("PASS: " + checks + " A1站位/单位/真实试验适配器/API替身/失败回滚检查；不证明OPM原生Create、单线图和跟随已实测。");
                return 0;
            }
            catch (Exception ex) { Console.Error.WriteLine(ex); return 1; }
        }
    }
}
