using System;
using Bentley.DgnPlatformNET;
using Bentley.OpenPlant.Modeler.Api;

namespace PipeAlign
{
    internal static class PipeUndoScope
    {
        internal static TransactionPosition Begin()
        {
            if (TransactionManager.IsUndoInProgress)
                throw new InvalidOperationException("正在撤销或重做，不能修改管道。");
            if (!TransactionManager.IsActive) TransactionManager.Activate();
            if (!TransactionManager.IsActive) throw new InvalidOperationException("无法启用模型撤销记录。");
            // 先结束用户之前的动作，再开始本次组；避免非模态窗体将修改留在未结束的事务中。
            TransactionManager.CloseCurrentTransaction(true);
            TransactionPosition mark = TransactionManager.CurrentTransactionPosition;
            BMECApi.Instance.StartUndoGroup();
            if (!TransactionManager.IsActive) TransactionManager.Activate();
            return mark;
        }

        internal static void End()
        {
            // 先把本次修改封成事务，再结束分组；清理接口不参与这条路径。
            TransactionManager.CloseCurrentTransaction(true);
            BMECApi.Instance.EndUndoGroup();
            // 不调用 SaveAndCleanUpUndo / ClearUndoBuffer，保留宿主的 Ctrl+Z / Redo 历史。
        }

        internal static void Cancel(TransactionPosition mark)
        {
            StatusInt status = TransactionManager.CancelToPosition(mark, false);
            if (status != StatusInt.Success) throw new InvalidOperationException("事务取消失败：" + status);
        }
    }
}
