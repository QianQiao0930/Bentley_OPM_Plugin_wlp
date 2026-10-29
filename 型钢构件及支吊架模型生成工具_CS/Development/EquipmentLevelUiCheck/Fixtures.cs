using System;
using System.Collections.Generic;
using System.Linq;
using Bentley.DgnPlatformNET;
namespace Bentley.DgnPlatformNET
{
    internal sealed class DgnModel { }
    internal static class TransactionManager
    {
        internal static event EventHandler OnUndoRedoFinished;
        internal static void Undo() { if (OnUndoRedoFinished != null) OnUndoRedoFinished(null, EventArgs.Empty); }
    }
}
namespace SteelSectionProbe
{
    internal sealed class MainWindow : System.Windows.Forms.Form
    {
        internal static MainWindow Current;
        internal void SetStatus(string text, bool error) { Fixture.Status = text; }
        internal void ShowHome() { }
        internal void BeginTitleDrag() { }
        internal void MinimizeFromHome() { }
    }
    internal static class LicenseService { internal static bool IsActivated = true; }
    internal static class Fixture
    {
        internal static DgnModel Model = new DgnModel();
        internal static bool HasSelection = true, FailApply;
        internal static string Status;
        internal static EquipmentAppearanceOptions Applied;
        internal static int ApplyCalls;
        internal static Action DuringApply;
    }
    internal static class EquipmentLevelReader
    {
        internal static DgnModel ActiveModel() { if (Fixture.Model == null) throw new InvalidOperationException("没有活动文档"); return Fixture.Model; }
    }
    internal sealed class EquipmentLevelDocument
    {
        internal DgnModel Model;
        internal string FileName = "C:/fixtures/equipment.dgn", ModelName = "Default";
        internal uint ActiveLevelId = 1;
        internal List<EquipmentLevelChoice> Levels = new List<EquipmentLevelChoice>();
    }
    internal sealed class EquipmentLevelSelection
    {
        internal DgnModel Model;
        internal readonly List<EquipmentLevelEntry> Equipment = new List<EquipmentLevelEntry>();
        internal readonly List<EquipmentLevelEntry> Rejected = new List<EquipmentLevelEntry>();
    }
    internal static class EquipmentLevelUiReader
    {
        internal static EquipmentLevelDocument ReadDocument()
        {
            return new EquipmentLevelDocument { Model = EquipmentLevelReader.ActiveModel(), Levels = new List<EquipmentLevelChoice> {
                new EquipmentLevelChoice { Id = 1, Name = "Default", IsWritable = true, Availability = "可用", ColorHex = "#A0A0A0" },
                new EquipmentLevelChoice { Id = 2, Name = "E-TNK", IsWritable = true, Availability = "可用", ColorHex = "#7FA37C" },
                new EquipmentLevelChoice { Id = 3, Name = "只读图层", IsWritable = false, Availability = "只读", ColorHex = "#667788" } } };
        }
        internal static EquipmentLevelSelection ReadSelection()
        {
            var result = new EquipmentLevelSelection { Model = EquipmentLevelReader.ActiveModel() };
            if (Fixture.HasSelection)
            {
                result.Equipment.Add(new EquipmentLevelEntry { ElementId = 678312, Name = "4006-CPT-MP-0002" });
                result.Equipment.Add(new EquipmentLevelEntry { ElementId = 678313, Name = "4006-CPT-MP-0003" });
                result.Rejected.Add(new EquipmentLevelEntry { ElementId = 40, Reason = "不是设备" });
            }
            return result;
        }
        internal static void ValidateDocument(EquipmentLevelDocument document)
        { if (!ReferenceEquals(document.Model, Fixture.Model)) throw new InvalidOperationException("活动文档已切换"); }
        internal static void Validate(EquipmentLevelDocument document, EquipmentLevelSelection selection)
        { ValidateDocument(document); if (selection == null || !ReferenceEquals(selection.Model, Fixture.Model)) throw new InvalidOperationException("请重新读取设备"); }
    }
    internal static class EquipmentLevelApplier
    {
        internal static EquipmentLevelReport Apply(DgnModel model, IList<ulong> ids, EquipmentAppearanceOptions options,
            Action<EquipmentLevelProgress> progress, Action validateContext)
        {
            Fixture.ApplyCalls++; Fixture.Applied = options;
            progress(new EquipmentLevelProgress { Stage = "读取设备内部图元", Total = 0, Detail = "已读取 120 个内部件" });
            if (Fixture.DuringApply != null) Fixture.DuringApply();
            validateContext();
            progress(new EquipmentLevelProgress { Stage = "修改图层与颜色", Completed = 80, Total = 120 });
            return new EquipmentLevelReport { Succeeded = !Fixture.FailApply, ChangedElementCount = 120, VerifiedElementCount = 120,
                Summary = Fixture.FailApply ? "校验失败，已整批回滚" : "2 台设备，修改 120 个图形，" + options.ColorDescription };
        }
    }
}
