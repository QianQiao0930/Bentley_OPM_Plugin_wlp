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
                foreach (double scale in new[] { 1d, 1000d, 10000d })
                foreach (int heading in new[] { 0, 90, 180, 270 })
                foreach (double angle in new[] { 0d, 90d, 359d })
                {
                    World.Reset(); Bentley.MstnPlatformNET.Session.Instance.Model.Scale = scale;
                    double theta = heading * Math.PI / 180;
                    World.Pipe.EndX = World.Pipe.StartX + 1000 * Math.Cos(theta);
                    World.Pipe.EndY = World.Pipe.StartY + 1000 * Math.Sin(theta);
                    var record = Place(300, angle);
                    Check(World.Elements.Count == 2 && !World.Created.Disposed, "创建一个原生A1并交给缓存");
                    Check(record.Dn == 100 && record.StationMm == 300 && record.AngleDeg == angle, "记录真实参数");
                    Check(Math.Abs(World.Created.Transform3d.Translation.X / scale - (1000 + 300 * Math.Cos(theta))) < 1e-7, "UOR定位X");
                    Check(Math.Abs(World.Created.Transform3d.Translation.Y / scale - (2000 + 300 * Math.Sin(theta))) < 1e-7, "UOR定位Y");
                    Check(Math.Abs(World.Created.Transform3d.Matrix.X.X - Math.Cos(theta)) < 1e-8, "管轴坐标框架");
                    var element = World.Find(World.Created.Instance);
                    Check(A1NativeTrialStore.Read(element).SupportInstanceId == record.SupportInstanceId && element.MaterialTag.StartsWith("A1-"), "模型内参数和原材料清单共存");
                    SelectTrial(record); Check(A1NativeTrialAdapter.CheckSelected(Log), "初始关联和位置可读");
                    World.Pipe.StartX += 200; World.Pipe.EndX += 200;
                    Check(!A1NativeTrialAdapter.CheckSelected(Log), "管动夹不动必须报告不通过");
                    var transform = World.Created.Transform3d; transform.Translation.X += 200 * scale; World.Created.Transform3d = transform;
                    Check(A1NativeTrialAdapter.CheckSelected(Log), "原生已跟随时位置通过");
                    World.Created.Instance.Parametric = true;
                    Check(!A1NativeTrialAdapter.CheckSelected(Log), "外形被原生参数化替换时报告不通过");
                }
                foreach (string stage in new[] { "Create", "Serialize", "Cache", "Statistics", "Metadata", "Relationship", "WrongOrigin", "Parametric" })
                {
                    World.Reset(); World.Fault = stage;
                    Reject(() => Place(), "故障明确失败 " + stage);
                    Check(World.Elements.Count == 1 && World.Elements.ContainsKey(1), "失败回收新元素且保留原管 " + stage);
                    Check(World.Created == null || World.Created.Disposed, "失败释放本次对象 " + stage);
                }
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
                Console.WriteLine("PASS: " + checks + " A1站位/单位/真实试验适配器/API替身/失败回滚检查；不证明OPM原生Create、单线图和跟随已实测。");
                return 0;
            }
            catch (Exception ex) { Console.Error.WriteLine(ex); return 1; }
        }
    }
}
