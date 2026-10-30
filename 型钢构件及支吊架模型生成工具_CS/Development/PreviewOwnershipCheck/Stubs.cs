using System;
using System.Collections.Generic;
using System.Linq;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;

internal static class Host
{
    internal static readonly List<Element> Created = new List<Element>();
    internal static Element[] Active { get { return Created.Where(element => element.InModel).ToArray(); } }
    internal static bool FailNextBuild, FailNextAdd, ThrowNextAdd, FailNextStatistics;
    internal static int NextDeleteFailures, NextDeleteExceptions, StatisticsWrites, Writes;
    internal static object LastPlan;
    internal static void Reset()
    {
        Created.Clear();FailNextBuild = FailNextAdd = ThrowNextAdd = FailNextStatistics = false;
        NextDeleteFailures = NextDeleteExceptions = StatisticsWrites = Writes = 0;LastPlan = null;
    }
    internal static Element[] Build()
    {
        if (FailNextBuild) { FailNextBuild = false;throw new InvalidOperationException("模拟几何构建失败"); }
        return new Element[0];
    }
    internal static void Attach(Element element, object plan)
    {
        if (FailNextStatistics) { FailNextStatistics = false;throw new InvalidOperationException("模拟统计写入失败"); }
        if (!element.InModel || !element.IsValid) throw new InvalidOperationException("错误地确认失效元素");
        StatisticsWrites++;element.Confirmed = true;LastPlan = plan;
    }
}

namespace Bentley.DgnPlatformNET
{
    public enum StatusInt { Success, Error }
}
namespace Bentley.GeometryNET
{
    public struct DPoint3d { public static DPoint3d Zero { get { return new DPoint3d(); } } }
    public struct DMatrix3d { public static DMatrix3d Identity { get { return new DMatrix3d(); } } }
}
namespace Bentley.MstnPlatformNET
{
    public sealed class Session
    {
        public static readonly Session Instance = new Session();
        public object GetActiveDgnModel() { return new object(); }
    }
}
namespace Bentley.DgnPlatformNET.Elements
{
    public class Element
    {
        public bool IsValid { get; private set; } = true;
        internal bool InModel, Confirmed;
        internal int DeleteFailures, DeleteExceptions, DeleteAttempts, ActiveCountAtDelete;
        public StatusInt AddToModel()
        {
            Host.Writes++;
            if (Host.ThrowNextAdd) { Host.ThrowNextAdd = false;throw new InvalidOperationException("模拟写入异常"); }
            if (Host.FailNextAdd) { Host.FailNextAdd = false;return StatusInt.Error; }
            InModel = true;return StatusInt.Success;
        }
        public StatusInt DeleteFromModel()
        {
            DeleteAttempts++;ActiveCountAtDelete = Host.Active.Length;
            if (DeleteExceptions > 0) { DeleteExceptions--;throw new InvalidOperationException("模拟删除异常"); }
            if (DeleteFailures > 0) { DeleteFailures--;return StatusInt.Error; }
            InModel = false;IsValid = false;return StatusInt.Success;
        }
    }
    public sealed class CellHeaderElement : Element
    {
        public CellHeaderElement(object model, string name, Bentley.GeometryNET.DPoint3d origin,
            Bentley.GeometryNET.DMatrix3d matrix, Element[] parts)
        {
            DeleteFailures = Host.NextDeleteFailures;DeleteExceptions = Host.NextDeleteExceptions;
            Host.NextDeleteFailures = Host.NextDeleteExceptions = 0;Host.Created.Add(this);
        }
    }
}
namespace SteelSectionProbe
{
    internal sealed class PipeClampSelection { }
    internal sealed class BracketPlan { internal bool Double; }
    internal sealed class PadPlatePlan { internal string CellName = "PAD"; }
    internal sealed class PortalFramePlan { internal string CellName = "PORTAL"; }
    internal sealed class LBracketPlan { }
    internal sealed class HandrailPlan { }
    internal sealed class SquareManholePlan { }
    internal sealed class TriangleBracketPlan { internal string CellName = "TRIANGLE"; }
    internal sealed class TFrameParameters { internal string Kind = "D15", Stiffener; }
    internal sealed class TFramePlan
    {
        internal string CellName = "TFRAME", Number;
        internal readonly TFrameParameters Parameters = new TFrameParameters();
        internal double HeightMm, L1Mm;
    }
    internal static class LBracketCatalog { internal const string CellName = "LBRACKET"; }
    internal static class HandrailCatalog { internal const string CellName = "HANDRAIL"; }
    internal static class SupportModelLevel { internal static void Use(Element element) { } }
    internal static class TFrameCalculator
    {
        internal static string Number(TFrameParameters parameters, double height, double length) { return parameters.Kind + "-" + parameters.Stiffener; }
    }
    internal static class BracketBuilder { internal static Element[] Build(BracketPlan plan, PipeClampSelection line) { return Host.Build(); } }
    internal static class PadPlateBuilder { internal static Element[] Build(PadPlatePlan plan) { return Host.Build(); } }
    internal static class PortalFrameBuilder { internal static Element[] Build(PortalFramePlan plan, PipeClampSelection line) { return Host.Build(); } }
    internal static class LBracketBuilder { internal static Element[] Build(LBracketPlan plan) { return Host.Build(); } }
    internal static class HandrailBuilder { internal static Element[] Build(HandrailPlan plan) { return Host.Build(); } }
    internal static class TFrameBuilder { internal static Element[] Build(TFramePlan plan, PipeClampSelection line) { return Host.Build(); } }
    internal static class TriangleBracketBuilder { internal static Element[] Build(TriangleBracketPlan plan, PipeClampSelection line) { return Host.Build(); } }
    internal static class SquareManholeBuilder
    {
        internal static Element Build(SquareManholePlan plan, Bentley.GeometryNET.DPoint3d origin)
        { return new CellHeaderElement(null, "SQUARE_MANHOLE", origin, Bentley.GeometryNET.DMatrix3d.Identity, Host.Build()); }
    }
    internal static class Statistics
    {
        internal static void AttachBracket(Element element, BracketPlan plan) { Host.Attach(element, plan); }
        internal static void AttachPadPlate(Element element, PadPlatePlan plan) { Host.Attach(element, plan); }
        internal static void AttachPortalFrame(Element element, PortalFramePlan plan) { Host.Attach(element, plan); }
        internal static void AttachLBracket(Element element, LBracketPlan plan) { Host.Attach(element, plan); }
        internal static void AttachHandrail(Element element, HandrailPlan plan) { Host.Attach(element, plan); }
        internal static void AttachTFrame(Element element, TFramePlan plan) { Host.Attach(element, plan); }
        internal static void AttachTriangleBracket(Element element, TriangleBracketPlan plan) { Host.Attach(element, plan); }
    }
    internal static class WriteDuration
    {
        internal static StatusInt Measure(Func<StatusInt> action, out string elapsed)
        { var result = action();elapsed = Host.Writes + " ms";return result; }
    }
}
