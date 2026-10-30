using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET.Elements;

namespace Bentley.DgnPlatformNET
{
    public enum StatusInt { Success, Error }
    public enum ComponentMode { None, Innermost }
    public enum RefLocateOption { None, TreatAsElement }
    public sealed class DgnModel { }
    public sealed class DgnModelRef
    {
        public DgnModel Model = Bentley.MstnPlatformNET.Session.Instance.GetActiveDgnModel();
        public DgnModel GetDgnModel() { return Model; }
    }
    public struct Point3d
    {
        public double X, Y, Z;
        public Point3d(double x, double y, double z) { X = x; Y = y; Z = z; }
    }
    public sealed class DgnButtonEvent { public Point3d Point; }
    public sealed class HitPath
    {
        public Element Element;
        public Element GetHeadElement() { return Element; }
    }
    public sealed class TestAgenda
    {
        public uint Count;
        public bool FailEmpty;
        public bool IsEmpty { get { return Count == 0; } }
        public uint GetCount() { return Count; }
        public void Empty(bool release) { if (FailEmpty) throw new InvalidOperationException("agenda empty failure"); Count = 0; }
    }
    public static class SelectionSetManager
    {
        public static readonly List<Element> Selection = new List<Element>();
        public static int EmptyCalls;
        public static bool FailEmpty, KeepSelection;
        public static bool IsActive() { return Selection.Count != 0; }
        public static uint NumSelected() { return (uint)Selection.Count; }
        public static void EmptyAll()
        {
            EmptyCalls++;
            if (FailEmpty) throw new InvalidOperationException("selection empty failure");
            if (!KeepSelection) Selection.Clear();
        }
        public static void Reset() { Selection.Clear(); EmptyCalls = 0; FailEmpty = false; KeepSelection = false; }
    }
    public abstract class DgnElementSetTool
    {
        public enum UsesSelection { None, Required }
        public enum UsesFence { None, Required }
        public enum ElementSource { Pick, SelectionSet, Fence }
        public static DgnElementSetTool Current;
        public static int InstallCalls, BaseInstallCalls, DoLocateCalls, ModifyCalls;
        public static bool DelayExitCleanup;
        public static Action BeforeInstall, AfterBaseInstall;
        public static HitPath NextHit;
        public static readonly List<uint> SelectionAtBaseInstall = new List<uint>();
        public TestAgenda ElementAgenda = new TestAgenda();
        private ElementSource source;
        protected DgnElementSetTool(int toolId, int promptId) { }
        protected virtual UsesSelection AllowSelection() { return UsesSelection.Required; }
        protected virtual UsesFence AllowFence() { return UsesFence.Required; }
        protected virtual ElementSource GetPreferredElementSource() { return ElementSource.SelectionSet; }
        protected virtual bool OnInstall()
        {
            BaseInstallCalls++;
            SelectionAtBaseInstall.Add(SelectionSetManager.NumSelected());
            // Reproduce the host hazard even when AllowSelection=None: existing
            // selection is copied into the agenda and changes left-click dispatch.
            ElementAgenda.Count = SelectionSetManager.NumSelected();
            source = ElementAgenda.IsEmpty ? GetPreferredElementSource() : ElementSource.SelectionSet;
            if (AfterBaseInstall != null) AfterBaseInstall();
            return true;
        }
        protected virtual void OnPostInstall() { }
        protected virtual void OnCleanup() { }
        protected virtual bool OnDataButton(DgnButtonEvent ev) { return false; }
        protected virtual bool OnResetButton(DgnButtonEvent ev) { return false; }
        protected virtual void OnRestartTool() { }
        protected virtual RefLocateOption GetReferenceLocateOptions() { return RefLocateOption.None; }
        protected virtual bool OnPostLocate(HitPath path, out string reason) { reason = ""; return true; }
        public abstract StatusInt OnElementModify(Element element);
        protected HitPath DoLocate(DgnButtonEvent ev, bool newSearch, int componentMode) { DoLocateCalls++; return NextHit; }
        protected void SetElementSource(ElementSource value) { source = value; }
        protected ElementSource GetElementSource() { return source; }
        public void InstallTool()
        {
            InstallCalls++;
            if (BeforeInstall != null) BeforeInstall();
            if (!OnInstall()) return;
            Current = this;
            OnPostInstall();
        }
        public void ExitTool() { if (ReferenceEquals(Current, this)) Current = null; if (!DelayExitCleanup) OnCleanup(); }
        public void CleanupForTest() { OnCleanup(); }
        public bool ClickForTest(DgnButtonEvent ev)
        {
            if (!ElementAgenda.IsEmpty || source != ElementSource.Pick)
            {
                ModifyCalls++;
                OnElementModify(NextHit == null ? null : NextHit.Element);
                OnRestartTool();
                return false;
            }
            return OnDataButton(ev);
        }
        public void SetSourceForTest(ElementSource value) { source = value; }
        public UsesSelection SelectionPolicyForTest { get { return AllowSelection(); } }
        public UsesFence FencePolicyForTest { get { return AllowFence(); } }
        public static void Reset()
        {
            Current = null; InstallCalls = 0; BaseInstallCalls = 0; DoLocateCalls = 0; ModifyCalls = 0;
            DelayExitCleanup = false; BeforeInstall = null; AfterBaseInstall = null; NextHit = null;
            SelectionAtBaseInstall.Clear(); SelectionSetManager.Reset();
        }
    }
}
namespace Bentley.DgnPlatformNET.Elements
{
    public sealed class Element
    {
        public ulong ElementId;
        public bool IsValid = true;
        public Bentley.DgnPlatformNET.DgnModelRef DgnModelRef = new Bentley.DgnPlatformNET.DgnModelRef();
    }
}
namespace Bentley.MstnPlatformNET
{
    public static class AccuSnap { public static bool SnapEnabled, LocateEnabled; }
    public static class NotificationManager { public static string LastPrompt; public static void OutputPrompt(string prompt) { LastPrompt = prompt; } }
    public sealed class Session
    {
        public static readonly Session Instance = new Session();
        private readonly Bentley.DgnPlatformNET.DgnModel active = new Bentley.DgnPlatformNET.DgnModel();
        public Bentley.DgnPlatformNET.DgnModel GetActiveDgnModel() { return active; }
    }
}
