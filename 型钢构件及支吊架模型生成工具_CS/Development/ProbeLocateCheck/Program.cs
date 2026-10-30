using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.MstnPlatformNET;
using SteelSectionProbe;

internal static class Program
{
    private static int assertions, scenarios;
    private static int picked, ended;
    private static LocatedElement lastPick;

    private static void Main()
    {
        TFrameLocateTool.Picked += OnPicked; TFrameLocateTool.Ended += OnEnded;
        PipeClampLocateTool.Picked += OnPicked; PipeClampLocateTool.Ended += OnEnded;
        Run("TFrame existing line is discarded before installation; one click is delivered", delegate { FirstClick(TFrameLocateTool.Begin, TFrameLocateTool.End); });
        Run("PipeClamp existing line is discarded before installation; one click is delivered", delegate { FirstClick(PipeClampLocateTool.Begin, PipeClampLocateTool.End); });
        Run("TFrame repeated Begin empties new selection and agenda without reinstall", delegate { RepeatedBegin(TFrameLocateTool.Begin, TFrameLocateTool.End); });
        Run("PipeClamp repeated Begin empties new selection and agenda without reinstall", delegate { RepeatedBegin(PipeClampLocateTool.Begin, PipeClampLocateTool.End); });
        Run("selection appearing after construction is cleared before base installation", DuringInstallSelection);
        Run("selection appearing during base installation is cleared after installation", AfterInstallSelection);
        Run("End does not restore old selection or clear a later user selection", EndDoesNotTouchSelection);
        Run("old delayed Cleanup cannot change a replacement tool or new user selection", DelayedCleanup);
        Run("constructor selection-clear exception rejects installation", ConstructorFailure);
        Run("silent selection-clear failure rejects installation", RetainedSelectionFailure);
        Run("selection-clear exception during installation rejects before base install", InstallationFailure);
        Run("repeated Begin clear failure does not reinstall, end or report a pick", RepeatedBeginFailure);
        Run("repeated Begin agenda-clear failure is explicit", AgendaFailure);
        Run("empty and invalid hits keep the tool alive and allow the next single click", MissThenHit);
        Run("handoff cleanup does not restore or clear selection", HandoffCleanup);
        Console.WriteLine("ProbeLocateCheck passed: " + scenarios + " scenarios, " + assertions + " assertions.");
    }
    private static void OnPicked(LocatedElement element) { picked++; lastPick = element; }
    private static void OnEnded() { ended++; }
    private static Element Line(ulong id) { return new Element { ElementId = id }; }
    private static void Select(ulong id) { SelectionSetManager.Selection.Add(Line(id)); }
    private static DgnButtonEvent Click() { return new DgnButtonEvent { Point = new Point3d(11, 22, 33) }; }
    private static void Hit(ulong id) { DgnElementSetTool.NextHit = new HitPath { Element = Line(id) }; }
    private static void Assert(bool condition, string message) { assertions++; if (!condition) throw new Exception(message); }
    private static void Throws(Action action, string message)
    {
        bool thrown = false;
        try { action(); } catch (InvalidOperationException ex) { thrown = ex.Message.Contains(message); }
        Assert(thrown, "Expected an explicit error containing: " + message);
    }
    private static void Run(string name, Action body)
    {
        TFrameLocateTool.End(); PipeClampLocateTool.End(); DgnElementSetTool.Reset();
        picked = 0; ended = 0; lastPick = null; AccuSnap.SnapEnabled = false; AccuSnap.LocateEnabled = false;
        try { body(); scenarios++; Console.WriteLine("PASS " + name); }
        finally
        {
            SelectionSetManager.FailEmpty = false; SelectionSetManager.KeepSelection = false;
            DgnElementSetTool.BeforeInstall = null; DgnElementSetTool.AfterBaseInstall = null;
            TFrameLocateTool.End(); PipeClampLocateTool.End();
        }
    }
    private static void FirstClick(Action begin, Action end)
    {
        Select(101); begin();
        Assert(DgnElementSetTool.SelectionAtBaseInstall.Count == 1 && DgnElementSetTool.SelectionAtBaseInstall[0] == 0, "Base install saw the original selected line.");
        Assert(SelectionSetManager.NumSelected() == 0, "Selection was not discarded.");
        var tool = DgnElementSetTool.Current;
        Assert(tool.SelectionPolicyForTest == DgnElementSetTool.UsesSelection.None && tool.FencePolicyForTest == DgnElementSetTool.UsesFence.None, "Tool accepted a set or fence.");
        Hit(102); Assert(tool.ClickForTest(Click()), "Single click was not consumed by the locate path.");
        Assert(DgnElementSetTool.DoLocateCalls == 1 && DgnElementSetTool.ModifyCalls == 0, "Single click entered the wrong host dispatch path.");
        Assert(picked == 1 && ended == 0, "Single click did not generate exactly one preview callback while retaining the tool.");
        Assert(lastPick.ElementId == 102 && lastPick.ClickX == 11 && lastPick.ClickY == 22 && lastPick.ClickZ == 33, "Pick identity or click coordinates changed.");
        Assert(AccuSnap.SnapEnabled && AccuSnap.LocateEnabled, "Picking did not enable snapping and locating.");
        end(); Assert(ended == 1 && SelectionSetManager.NumSelected() == 0, "End restored the abandoned selected line or notified twice.");
        Assert(!AccuSnap.SnapEnabled && !AccuSnap.LocateEnabled, "Original snap/locate state was not restored.");
    }
    private static void RepeatedBegin(Action begin, Action end)
    {
        begin(); var original = DgnElementSetTool.Current;
        Select(201); original.ElementAgenda.Count = 1; original.SetSourceForTest(DgnElementSetTool.ElementSource.SelectionSet);
        begin();
        Assert(ReferenceEquals(original, DgnElementSetTool.Current) && DgnElementSetTool.InstallCalls == 1, "Repeated Begin replaced the tool.");
        Assert(SelectionSetManager.NumSelected() == 0 && original.ElementAgenda.IsEmpty, "Repeated Begin retained selection or agenda.");
        Assert(ended == 0, "Repeated Begin notified Ended.");
        Hit(202); original.ClickForTest(Click());
        Assert(picked == 1 && DgnElementSetTool.DoLocateCalls == 1 && DgnElementSetTool.ModifyCalls == 0, "Next click did not immediately report the new line.");
        end(); Assert(!AccuSnap.SnapEnabled && !AccuSnap.LocateEnabled, "Repeated Begin overwrote the saved snap state.");
    }
    private static void DuringInstallSelection()
    {
        Select(301); DgnElementSetTool.BeforeInstall = delegate { Select(302); };
        TFrameLocateTool.Begin();
        Assert(DgnElementSetTool.SelectionAtBaseInstall[0] == 0, "Selection added after construction reached base install.");
        Hit(303); DgnElementSetTool.Current.ClickForTest(Click());
        Assert(picked == 1 && ended == 0 && DgnElementSetTool.ModifyCalls == 0, "Installation selection injection broke the first click.");
    }
    private static void AfterInstallSelection()
    {
        DgnElementSetTool.AfterBaseInstall = delegate { Select(311); };
        TFrameLocateTool.Begin();
        Assert(SelectionSetManager.NumSelected() == 0, "OnPostInstall left selection behind.");
        Hit(312); DgnElementSetTool.Current.ClickForTest(Click()); Assert(picked == 1 && ended == 0, "Postinstall selection broke the first click.");
    }
    private static void EndDoesNotTouchSelection()
    {
        Select(401); TFrameLocateTool.Begin(); Select(402); TFrameLocateTool.End();
        Assert(SelectionSetManager.NumSelected() == 1 && SelectionSetManager.Selection[0].ElementId == 402, "End restored original selection or discarded a later selection.");
        Assert(ended == 1, "End did not notify exactly once.");
    }
    private static void DelayedCleanup()
    {
        Select(501); TFrameLocateTool.Begin(); var old = DgnElementSetTool.Current;
        DgnElementSetTool.DelayExitCleanup = true; TFrameLocateTool.End();
        Select(502); TFrameLocateTool.Begin(); var replacement = DgnElementSetTool.Current;
        Select(503); old.CleanupForTest();
        Assert(SelectionSetManager.NumSelected() == 1 && SelectionSetManager.Selection[0].ElementId == 503, "Old Cleanup touched a new user selection.");
        Assert(ended == 1 && ReferenceEquals(replacement, DgnElementSetTool.Current), "Old Cleanup ended a replacement tool.");
        TFrameLocateTool.Begin(); Hit(504); replacement.ClickForTest(Click());
        Assert(picked == 1 && ended == 1, "Replacement did not accept one click after stale Cleanup.");
    }
    private static void ConstructorFailure()
    {
        Select(601); SelectionSetManager.FailEmpty = true;
        Throws(TFrameLocateTool.Begin, "无法清空当前选择集");
        Assert(DgnElementSetTool.InstallCalls == 0 && DgnElementSetTool.BaseInstallCalls == 0 && DgnElementSetTool.Current == null, "Failed clear continued installation.");
        Assert(picked == 0 && ended == 0 && !AccuSnap.SnapEnabled && !AccuSnap.LocateEnabled, "Rejected construction changed active state.");
    }
    private static void RetainedSelectionFailure()
    {
        Select(611); SelectionSetManager.KeepSelection = true;
        Throws(TFrameLocateTool.Begin, "无法清空当前选择集"); Assert(DgnElementSetTool.InstallCalls == 0, "Nonempty selection after EmptyAll was accepted.");
    }
    private static void InstallationFailure()
    {
        DgnElementSetTool.BeforeInstall = delegate { SelectionSetManager.FailEmpty = true; };
        Throws(TFrameLocateTool.Begin, "无法清空当前选择集");
        Assert(DgnElementSetTool.InstallCalls == 1 && DgnElementSetTool.BaseInstallCalls == 0 && DgnElementSetTool.Current == null, "OnInstall clear failure reached base install.");
        Assert(!AccuSnap.SnapEnabled && !AccuSnap.LocateEnabled && ended == 0, "Installation clear failure changed snap or notified Ended.");
    }
    private static void RepeatedBeginFailure()
    {
        TFrameLocateTool.Begin(); var original = DgnElementSetTool.Current; Select(621); SelectionSetManager.FailEmpty = true;
        Throws(TFrameLocateTool.Begin, "无法清空当前选择集");
        Assert(ReferenceEquals(original, DgnElementSetTool.Current) && DgnElementSetTool.InstallCalls == 1 && picked == 0 && ended == 0, "Failed repeat replaced, ended or picked.");
    }
    private static void AgendaFailure()
    {
        TFrameLocateTool.Begin(); var tool = DgnElementSetTool.Current; tool.ElementAgenda.Count = 1; tool.ElementAgenda.FailEmpty = true;
        Throws(TFrameLocateTool.Begin, "无法清空点取议程");
        Assert(DgnElementSetTool.InstallCalls == 1 && ended == 0 && picked == 0, "Agenda clear failure continued or ended picking.");
    }
    private static void MissThenHit()
    {
        TFrameLocateTool.Begin(); var tool = DgnElementSetTool.Current;
        tool.ClickForTest(Click()); Hit(701); DgnElementSetTool.NextHit.Element.IsValid = false; tool.ClickForTest(Click());
        Assert(picked == 0 && ended == 0 && ReferenceEquals(tool, DgnElementSetTool.Current), "Miss ended picking or reported an invalid element.");
        Hit(702); tool.ClickForTest(Click()); Assert(picked == 1 && ended == 0 && DgnElementSetTool.InstallCalls == 1, "First valid click after a miss required reinstall.");
    }
    private static void HandoffCleanup()
    {
        Select(801); PipeClampLocateTool.Begin(); var old = DgnElementSetTool.Current; PipeClampLocateTool.RetireForHandoff();
        Select(802); old.CleanupForTest();
        Assert(ended == 0 && !PipeClampLocateTool.IsActive, "Handoff cleanup notified Ended or retained active instance.");
        Assert(SelectionSetManager.NumSelected() == 1 && SelectionSetManager.Selection[0].ElementId == 802, "Handoff cleanup touched a later selection.");
    }
}
