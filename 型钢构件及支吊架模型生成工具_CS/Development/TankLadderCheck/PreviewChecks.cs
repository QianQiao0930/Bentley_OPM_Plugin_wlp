using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;

// API substitutes test the real preview ownership logic, not native Bentley geometry.
namespace Bentley.DgnPlatformNET { internal enum StatusInt { Success, Failure } }
namespace Bentley.DgnPlatformNET.Elements
{
    internal sealed class Element
    {
        internal bool IsValid = true, Written;
        internal StatusInt AddStatus = StatusInt.Success, DeleteStatus = StatusInt.Success;
        internal StatusInt AddToModel() { if (AddStatus == StatusInt.Success) Written = true; return AddStatus; }
        internal StatusInt DeleteFromModel() { if (DeleteStatus == StatusInt.Success) { Written = false; IsValid = false; } return DeleteStatus; }
    }
}
namespace SteelSectionProbe
{
    internal static class PreviewChecks
    {
        internal static void Run(Action<bool, string> check)
        {
            var session = new TankLadderPreviewSession();
            var first = new Element(); session.Show(first); check(first.Written && session.HasPreview, "preview written");
            session.Confirm(); session.Cancel(); check(first.Written && !session.HasPreview, "confirmed model retained");
            var old = new Element(); session.Show(old); session.Invalidate(); Reject(session.Confirm);
            Reject(() => session.Show(new Element { AddStatus = StatusInt.Failure }));
            check(old.Written && session.HasPreview, "failed replacement retains old model");
            Reject(session.Confirm); session.Cancel(); check(!old.Written, "invalid preview can be cancelled");
            old = new Element { DeleteStatus = StatusInt.Failure }; session.Show(old);
            var replacement = new Element(); Reject(() => session.Show(replacement));
            check(old.Written && !replacement.Written && session.HasPreview, "old deletion failure rolls back new model");
            Reject(session.Confirm); old.DeleteStatus = StatusInt.Success; session.Cancel();
            check(!session.HasPreview, "deletion failure can be retried");
            old = new Element { DeleteStatus = StatusInt.Failure }; session.Show(old);
            replacement = new Element { DeleteStatus = StatusInt.Failure }; Reject(() => session.Show(replacement));
            check(old.Written && replacement.Written && session.HasPreview, "both cleanup failures retain ownership");
            Reject(session.Cancel); old.DeleteStatus = replacement.DeleteStatus = StatusInt.Success;
            session.Cancel(); check(!old.Written && !replacement.Written && !session.HasPreview, "all retained elements cleaned on retry");
            var stale = new Element(); session.Show(stale); stale.IsValid = false; Reject(session.Confirm);
            session.Cancel(); session.Cancel(); check(!session.HasPreview, "externally deleted preview and repeat cleanup");
            var current = new Element(); session.Show(current); var next = new Element(); session.Show(next);
            check(!current.Written && next.Written, "successful replacement deletes old preview");
            session.Cancel(); check(!next.Written, "unconfirmed preview cancelled");
        }
        private static void Reject(Action action)
        {
            try { action(); } catch (InvalidOperationException) { return; }
            throw new Exception("Expected preview failure was not rejected.");
        }
    }
}
