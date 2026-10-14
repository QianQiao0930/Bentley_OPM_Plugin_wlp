using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Com = Bentley.Interop.MicroStationDGN;

namespace SteelSectionProbe
{
    /// <summary>COM暂态容器持有图形副本；临时物化/删除在同一短事务内完成，不留下模型预览。</summary>
    internal sealed class PipeClampTransientPreview
    {
        private Com.TransientElementContainer container;
        internal static PipeClampTransientPreview Create(Element cell)
        {
            if(TransactionManager.IsUndoInProgress)throw new InvalidOperationException("撤销/重做期间不能创建预览。");
            if(!TransactionManager.IsActive)TransactionManager.Activate();
            TransactionManager.CloseCurrentTransaction(true);
            var mark=TransactionManager.CurrentTransactionPosition;
            PipeClampTransientPreview result=null;
            try
            {
                if(cell.AddToModel()!=StatusInt.Success)throw new InvalidOperationException("管夹预览物化失败。");
                var app=Bentley.MstnPlatformNET.InteropServices.Utilities.ComApp;
                var com=app.ActiveModelReference.GetElementByID64(checked((long)(ulong)cell.ElementId));
                var display=app.CreateTransientElementContainer1(com,
                    Com.MsdTransientFlags.Overlay|Com.MsdTransientFlags.DontIncludeInFit,
                    Com.MsdViewMask.AllViews,Com.MsdDrawingMode.Normal);
                if(display==null)throw new InvalidOperationException("管夹暂态预览创建失败。");
                result=new PipeClampTransientPreview {container=display};
                if(cell.DeleteFromModel()!=StatusInt.Success)throw new InvalidOperationException("管夹临时物化元素清理失败。");
                TransactionManager.CloseCurrentTransaction(true);
                return result;
            }
            catch(Exception error)
            {
                Exception displayError=null;
                try { result?.Close(); } catch(Exception ex) { displayError=ex; Pending.Add(result); }
                var rollback=TransactionManager.CancelToPosition(mark,false);
                if(rollback!=StatusInt.Success)throw new InvalidOperationException("管夹预览失败且回滚未完成，请检查临时元素ID="+(ulong)cell.ElementId,error);
                if(displayError!=null)throw new AggregateException("管夹暂态预览清理失败，关闭或取消时将重试。",error,displayError);
                throw;
            }
        }

        private static readonly System.Collections.Generic.List<PipeClampTransientPreview> Pending=new System.Collections.Generic.List<PipeClampTransientPreview>();
        internal static void RetryPending()
        {
            for(int i=Pending.Count-1;i>=0;i--){Pending[i].Close();Pending.RemoveAt(i);}
        }
        internal void Close()
        {
            if(container==null)return;
            container.Reset();
            container=null;
        }
    }
}
