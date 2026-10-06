using System;
using Bentley.DgnPlatformNET;
using Bentley.OpenPlant.Modeler.Api;
using SteelSectionProbe.PipeAlignment;

internal static class Program
{
    private static void Equal(int expected, int actual)
    {
        if (expected != actual) throw new InvalidOperationException("Expected " + expected + ", actual " + actual);
    }
    private static int Main()
    {
        try
        {
            TransactionManager.Reset();
            // 用户之前的未结束修改必须与插件批次分开保留。
            TransactionManager.ModelValue = 10;
            PipeUndoScope.Begin();
            TransactionManager.ModelValue = 11;
            TransactionManager.ModelValue = 12;
            PipeUndoScope.End();
            TransactionManager.UserUndo(); Equal(10, TransactionManager.ModelValue);
            TransactionManager.UserRedo(); Equal(12, TransactionManager.ModelValue);
            TransactionManager.UserUndo(); TransactionManager.UserUndo(); Equal(0, TransactionManager.ModelValue);
            Console.WriteLine("PASS 一次撤销整批、Redo、保留之前用户操作（模拟事务）");

            TransactionManager.Reset();
            TransactionManager.ModelValue = 10;
            TransactionPosition mark = PipeUndoScope.Begin();
            TransactionManager.ModelValue = 20;
            PipeUndoScope.End();
            PipeUndoScope.Cancel(mark); Equal(10, TransactionManager.ModelValue);
            TransactionManager.UserUndo(); Equal(0, TransactionManager.ModelValue);
            Console.WriteLine("PASS 失败批次取消后，之前用户操作仍可撤销（模拟事务）");

            TransactionManager.Reset();
            TransactionManager.IsActive = false;
            mark = PipeUndoScope.Begin();
            if (!TransactionManager.IsActive) throw new InvalidOperationException("Undo not activated");
            PipeUndoScope.End();
            TransactionManager.FailCancel = true;
            bool failed = false;
            try { PipeUndoScope.Cancel(mark); } catch (InvalidOperationException) { failed = true; }
            if (!failed) throw new InvalidOperationException("Cancel failure hidden");
            Console.WriteLine("PASS 启用记录、回退失败必须可见（模拟事务）");

            TransactionManager.Reset();
            TransactionManager.IsUndoInProgress = true;
            failed = false;
            try { PipeUndoScope.Begin(); } catch (InvalidOperationException) { failed = true; }
            if (!failed || BMECApi.Instance.GroupOpen) throw new InvalidOperationException("Write during undo");
            Console.WriteLine("PASS 撤销过程中拒绝新修改（模拟事务）");
            return 0;
        }
        catch (Exception ex) { Console.WriteLine("FAIL " + ex.Message); return 1; }
    }
}
