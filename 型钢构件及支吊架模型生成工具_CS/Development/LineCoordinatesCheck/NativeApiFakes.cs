using System;
using System.Collections.Generic;

// 仅用于离线回归；模拟持久模型与独立编辑句柄，不执行 Bentley 原生代码。
namespace Bentley.GeometryNET
{
    internal struct DPoint3d
    {
        internal double X, Y, Z;
        internal static DPoint3d FromXYZ(double x, double y, double z) { return new DPoint3d { X = x, Y = y, Z = z }; }
    }
    internal struct DSegment3d
    {
        internal DPoint3d Start, End;
        internal DSegment3d(DPoint3d start, DPoint3d end) { Start = start; End = end; }
    }
    internal sealed class CurvePrimitive
    {
        internal DSegment3d Segment;
        internal bool IsLine = true;
        internal static CurvePrimitive CreateLine(DSegment3d segment) { return new CurvePrimitive { Segment = segment }; }
        internal bool TryGetLine(out DSegment3d segment) { segment = Segment; return IsLine; }
        internal bool GetStartEnd(out DPoint3d start, out DPoint3d end) { start = Segment.Start; end = Segment.End; return true; }
    }
    internal sealed class CurveVector : List<CurvePrimitive>
    {
        internal enum BoundaryType { Open, Closed }
        private readonly BoundaryType boundary;
        internal CurveVector(BoundaryType boundary) { this.boundary = boundary; }
        internal BoundaryType GetBoundaryType() { return boundary; }
        internal CurvePrimitive GetPrimitive(int index) { return this[index]; }
    }
}
namespace Bentley.DgnPlatformNET
{
    internal enum StatusInt { Success, Error }
    internal enum BentleyStatus { Success, Error }
    internal enum MSElementType { Line, LineString, ComplexString }
    internal struct ElementId
    {
        internal ulong Value;
        internal ElementId(ref ulong value) { Value = value; }
        public static explicit operator ulong(ElementId id) { return id.Value; }
    }
    internal sealed class ModelInfo { internal double UorPerMeter = 1000000; }
    internal sealed class DgnFile { internal bool IsReadOnly = false; }
    internal class DgnModelRef
    {
        internal DgnModel Model = null;
        internal bool IsDgnAttachment = false;
        internal DgnModel GetDgnModel() { return this as DgnModel ?? Model; }
    }
    internal sealed class DgnModel : DgnModelRef
    {
        internal readonly Dictionary<ulong, Elements.LineElement> Lines = new Dictionary<ulong, Elements.LineElement>();
        internal readonly ModelInfo Info = new ModelInfo();
        internal readonly DgnFile File = new DgnFile();
        internal bool Is3d = true, IsReadOnly = false, EditFails = false, ReplaceFails = false, ReplaceThrows = false, BadReadback = false;
        internal int WriteCount;
        internal ModelInfo GetModelInfo() { return Info; }
        internal DgnFile GetDgnFile() { return File; }
        internal Elements.Element FindElementById(ElementId id)
        {
            Elements.LineElement stored;
            return Lines.TryGetValue(id.Value, out stored) ? stored.Copy() : null;
        }
    }
    internal sealed class OnUndoRedoFinishedEventArgs : EventArgs { }
    internal sealed class TransactionPosition { internal Dictionary<ulong, Elements.LineElement> Before; }
    internal static class TransactionManager
    {
        internal static bool IsActive = true, IsUndoInProgress = false, CancelFails = false;
        internal static int Closes, Cancels;
        internal static event EventHandler<OnUndoRedoFinishedEventArgs> OnUndoRedoFinished;
        internal static void RaiseUndo() { var handler = OnUndoRedoFinished; if (handler != null) handler(null, new OnUndoRedoFinishedEventArgs()); }
        internal static void Activate() { IsActive = true; }
        internal static void CloseCurrentTransaction(bool validate) { Closes++; }
        internal static TransactionPosition CurrentTransactionPosition
        {
            get
            {
                var before = new Dictionary<ulong, Elements.LineElement>();
                foreach (var line in Bentley.MstnPlatformNET.Session.Instance.Active.Lines) before.Add(line.Key, line.Value.Copy());
                return new TransactionPosition { Before = before };
            }
        }
        internal static StatusInt CancelToPosition(TransactionPosition mark, bool restart)
        {
            Cancels++;
            if (CancelFails) return StatusInt.Error;
            var model = Bentley.MstnPlatformNET.Session.Instance.Active; model.Lines.Clear();
            foreach (var line in mark.Before) model.Lines.Add(line.Key, line.Value.Copy());
            return StatusInt.Success;
        }
    }
}
namespace Bentley.DgnPlatformNET.Elements
{
    using Bentley.GeometryNET;
    internal class Element : IDisposable
    {
        internal DgnModel Model;
        internal ElementId ElementId;
        internal bool IsValid = true, IsDeleted, IsComplexComponent, Locked;
        internal Element ParentElement;
        internal MSElementType ElementType = MSElementType.Line;
        internal DgnModelRef DgnModelRef { get { return Model; } }
        internal bool IsEffectivelyLocked(bool parents, bool children) { return Locked; }
        public void Dispose() { }
    }
    internal sealed class LineElement : Element
    {
        internal CurveVector Path;
        internal string Metadata = "图层/颜色/线型/EC附加属性";
        internal LineElement Copy()
        {
            return new LineElement { Model = Model, ElementId = ElementId, IsValid = IsValid, IsDeleted = IsDeleted,
                IsComplexComponent = IsComplexComponent, Locked = Locked, ParentElement = ParentElement,
                ElementType = ElementType, Path = Path, Metadata = Metadata };
        }
    }
    internal static class CurvePathQuery
    {
        internal static CurveVector ElementToCurveVector(Element element) { return ((LineElement)element).Path; }
    }
    internal sealed class CurvePathEdit : IDisposable
    {
        private readonly LineElement draft;
        private CurvePathEdit(LineElement original) { draft = original.Copy(); }
        internal static CurvePathEdit GetAsCurvePathEdit(Element element) { return new CurvePathEdit((LineElement)element); }
        internal BentleyStatus SetCurveVector(CurveVector path)
        {
            if (draft.Model.EditFails) return BentleyStatus.Error;
            draft.Path = path; return BentleyStatus.Success;
        }
        internal StatusInt ReplaceInModel(Element original)
        {
            if (draft.Model.ReplaceFails) return StatusInt.Error;
            draft.Model.Lines[original.ElementId.Value] = draft.Copy(); draft.Model.WriteCount++;
            if (draft.Model.ReplaceThrows) throw new InvalidOperationException("模拟部分写入后异常");
            if (draft.Model.BadReadback) draft.Model.Lines[original.ElementId.Value].Path = ((LineElement)original).Path;
            return StatusInt.Success;
        }
        public void Dispose() { }
    }
}
namespace Bentley.MstnPlatformNET
{
    internal sealed class Session
    {
        internal static readonly Session Instance = new Session();
        internal Bentley.DgnPlatformNET.DgnModel Active;
        internal Bentley.DgnPlatformNET.DgnModel GetActiveDgnModel() { return Active; }
    }
}
