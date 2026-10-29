using System;
using System.Diagnostics;

namespace SteelSectionProbe
{
    /// <summary>同步回调保持 Bentley 操作在原宿主线程；限制刷新频率，避免每个图元都重绘。</summary>
    internal sealed class EquipmentLevelProgressReporter
    {
        private readonly Action<EquipmentLevelProgress> callback;
        private Action validateContext;
        private readonly Stopwatch watch = Stopwatch.StartNew();
        private long last = -1000;
        private string stage = "准备处理";
        private int completed, total;

        internal EquipmentLevelProgressReporter(Action<EquipmentLevelProgress> callback, Action validateContext)
        { this.callback = callback; this.validateContext = validateContext; }
        internal void SuspendContextValidation() { validateContext = null; }
        internal void Step(string stage, int completed, int total, string detail = "", bool force = false)
        {
            bool changed = this.stage != stage;
            this.stage = stage; this.completed = completed; this.total = total;
            Send(detail, force || changed);
        }
        internal void Scanned(int count) { Send("已读取 " + count + " 个内部件", false); }
        private void Send(string detail, bool force)
        {
            if (callback == null || (!force && watch.ElapsedMilliseconds - last < 100)) return;
            last = watch.ElapsedMilliseconds;
            try
            {
                callback(new EquipmentLevelProgress { Stage = stage, Detail = detail, Completed = completed,
                    Total = total, ElapsedMilliseconds = last });
            }
            catch (Exception ex) { EquipmentLevelLog.Write("进度显示异常：" + ex); }
            // 显示刷新可能处理宿主消息；返回模型操作前必须确认仍为原文档。
            if (validateContext != null) validateContext();
        }
    }
}
