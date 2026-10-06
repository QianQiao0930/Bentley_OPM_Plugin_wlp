// 仅模拟事务契约，不能证明真实 Bentley 的 Undo 行为。
using System;
using System.Collections.Generic;

namespace Bentley.DgnPlatformNET
{
    internal enum StatusInt { Success, Error }
    internal struct TransactionPosition { internal int Value; }
    internal static class TransactionManager
    {
        private static readonly List<int> History = new List<int>();
        private static readonly Stack<int> Redo = new Stack<int>();
        internal static int ModelValue;
        internal static bool IsActive;
        internal static bool IsUndoInProgress;
        internal static bool FailCancel;
        internal static bool HasEntries { get { return History.Count > 1; } }
        internal static TransactionPosition CurrentTransactionPosition
        {
            get { return new TransactionPosition { Value = History.Count - 1 }; }
        }
        internal static void Reset()
        {
            History.Clear(); History.Add(0); Redo.Clear();
            ModelValue = 0; IsActive = true; IsUndoInProgress = false; FailCancel = false;
        }
        internal static void Activate() { IsActive = true; }
        internal static void CloseCurrentTransaction(bool validate)
        {
            if (!IsActive) throw new InvalidOperationException("Recording inactive");
            if (History[History.Count - 1] == ModelValue) return;
            History.Add(ModelValue); Redo.Clear();
        }
        internal static StatusInt CancelToPosition(TransactionPosition position, bool restart)
        {
            if (FailCancel || position.Value < 0 || position.Value >= History.Count) return StatusInt.Error;
            ModelValue = History[position.Value];
            History.RemoveRange(position.Value + 1, History.Count - position.Value - 1);
            return StatusInt.Success;
        }
        internal static void UserUndo()
        {
            if (!HasEntries) throw new InvalidOperationException("No undo history");
            Redo.Push(ModelValue);
            History.RemoveAt(History.Count - 1); ModelValue = History[History.Count - 1];
        }
        internal static void UserRedo()
        {
            ModelValue = Redo.Pop(); History.Add(ModelValue);
        }
    }
}

namespace Bentley.OpenPlant.Modeler.Api
{
    internal sealed class BMECApi
    {
        internal static readonly BMECApi Instance = new BMECApi();
        internal bool GroupOpen;
        internal void StartUndoGroup()
        {
            if (GroupOpen) throw new InvalidOperationException("Nested group");
            GroupOpen = true;
        }
        internal void EndUndoGroup()
        {
            if (!GroupOpen) throw new InvalidOperationException("No group");
            GroupOpen = false;
        }
    }
}
