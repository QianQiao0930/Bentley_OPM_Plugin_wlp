using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;

namespace SteelSectionProbe
{
    /// <summary>
    /// 只读点取工具的共同基类：只按光标位置定位元素，<b>不使用宿主当前的元素选择集</b>。
    /// <para>
    /// 背景：<see cref="DgnElementSetTool"/> 在安装时若发现已有选择集，会把它当作自己的"元素议程"。
    /// 议程非空后，一次左键不再走本工具的 <c>OnDataButton</c> → <c>DoLocate</c>，而是去"修改议程"，
    /// 于是 <c>OnElementModify</c> 返回错误、宿主重启/退出工具。用户看到的现象就是
    /// "先在视图中选中一条直线，再点【开始点取】，左键点线没有生成预览，点取还自己结束了"；
    /// 选择集为空时同一段代码完全正常。
    /// </para>
    /// <para>
    /// 因此本基类在<b>构造工具（安装之前）</b>就把活动选择集"挂起"：记住其中的元素并清空，
    /// 让宿主看到的就是它已经验证可用的"空选择集"路径；工具清理时再把这些元素放回选择集，
    /// 用户的选择不会被永久丢掉。除此之外还固定了 <c>AllowSelection=None</c>、
    /// <c>AllowFence=None</c>、元素来源=直接点取，并在安装时清一次议程，作为多层兜底。
    /// </para>
    /// </summary>
    internal abstract class ProbeLocateTool : DgnElementSetTool
    {
        private struct SuspendedElement
        {
            public DgnModelRef Model;
            public ElementId Id;
        }

        private static List<SuspendedElement> suspendedElements;
        private static bool ignoredSelectionSet;

        protected ProbeLocateTool() : base(0, 0) { SuspendSelectionSet("无参构造"); }

        protected ProbeLocateTool(int toolId, int promptId) : base(toolId, promptId) { SuspendSelectionSet("带参构造"); }

        /// <summary>本次安装前是否真的挂起了非空选择集（供派生工具的提示使用）。</summary>
        protected bool IgnoredSelectionSet { get { return ignoredSelectionSet; } }

        /// <summary>只读点取工具不接受选择集作为元素来源。</summary>
        protected override UsesSelection AllowSelection() { return UsesSelection.None; }

        /// <summary>只读点取工具同样不使用围栅（fence）作为元素来源。</summary>
        protected override UsesFence AllowFence() { return UsesFence.None; }

        /// <summary>元素来源固定为直接点取（Pick），不使用选择集或围栅。</summary>
        protected override ElementSource GetPreferredElementSource() { return ElementSource.Pick; }

        protected override bool OnInstall()
        {
            ProbeLocateLog.Write("OnInstall 安装前选择集数=" + SafeSelectionCount() +
                "；挂起数=" + SuspendedCount);
            bool installed = base.OnInstall();
            ResetElementSource("OnInstall");
            ProbeLocateLog.Write("OnInstall 结束：返回值=" + installed + "；议程=" + SafeAgendaCount() +
                "；来源=" + SafeElementSource());
            return installed;
        }

        protected override void OnPostInstall()
        {
            base.OnPostInstall();
            ResetElementSource("OnPostInstall");
            ProbeLocateLog.Write("OnPostInstall：议程=" + SafeAgendaCount() +
                "；来源=" + SafeElementSource() + "；选择集数=" + SafeSelectionCount());
        }

        protected override void OnCleanup()
        {
            ProbeLocateLog.Write("OnCleanup：工具清理，准备归还选择集");
            RestoreSelectionSet();
            base.OnCleanup();
        }

        /// <summary>清掉宿主编进议程的条目，并把元素来源复位为直接点取（多层兜底）。</summary>
        protected void ResetElementSource(string stage)
        {
            try
            {
                var agenda = ElementAgenda;
                if (agenda != null && !agenda.IsEmpty)
                {
                    ProbeLocateLog.Write(stage + "：议程非空，清空 " + agenda.GetCount() + " 条");
                    agenda.Empty(true);
                }
            }
            catch (Exception ex)
            {
                ProbeLocateLog.Write(stage + "：清空议程失败：" + ex.Message);
            }
            try { SetElementSource(ElementSource.Pick); }
            catch (Exception ex) { ProbeLocateLog.Write(stage + "：复位元素来源失败：" + ex.Message); }
        }

        /// <summary>
        /// 把活动选择集里的元素记下来并清空，让工具安装时宿主拿不到议程来源。
        /// 上一次（可能因工具异常退出）没归还的会先归还，再重新挂起，避免元素被吞掉。
        /// </summary>
        private static void SuspendSelectionSet(string stage)
        {
            RestoreSelectionSet();
            ignoredSelectionSet = false;
            try
            {
                uint count = SafeSelectionCount();
                if (count == 0) { ProbeLocateLog.Write("挂起选择集（" + stage + "）：原本为空"); return; }
                var list = new List<SuspendedElement>((int)count);
                for (uint i = 0; i < count; i++)
                {
                    Element element = null;
                    DgnModelRef model = null;
                    if (SelectionSetManager.GetElement(i, ref element, ref model) != StatusInt.Success || element == null)
                        continue;
                    list.Add(new SuspendedElement { Model = model, Id = element.ElementId });
                }
                suspendedElements = list;
                ignoredSelectionSet = list.Count > 0;
                SelectionSetManager.EmptyAll();
                ProbeLocateLog.Write("挂起选择集（" + stage + "）：清空 " + list.Count + " 个元素，工具安装前选择集数=" +
                    SafeSelectionCount());
            }
            catch (Exception ex)
            {
                suspendedElements = null;
                ignoredSelectionSet = false;
                ProbeLocateLog.Write("挂起选择集失败（" + stage + "）：" + ex.Message);
            }
        }

        /// <summary>把挂起的元素放回选择集；任何单个元素失效都只跳过，不影响其它元素。</summary>
        private static void RestoreSelectionSet()
        {
            var list = suspendedElements;
            suspendedElements = null;
            ignoredSelectionSet = false;
            if (list == null || list.Count == 0) return;
            int restored = 0;
            foreach (var entry in list)
            {
                try
                {
                    var model = entry.Model == null ? null : entry.Model.GetDgnModel();
                    var element = model == null ? null : model.FindElementById(entry.Id);
                    if (element == null || !element.IsValid) continue;
                    if (SelectionSetManager.AddElement(element, entry.Model) == BentleyStatus.Success) restored++;
                }
                catch (Exception ex)
                {
                    ProbeLocateLog.Write("归还选择集元素失败：" + ex.Message);
                }
            }
            ProbeLocateLog.Write("归还选择集：计划 " + list.Count + "，成功 " + restored);
        }

        private static int SuspendedCount { get { return suspendedElements == null ? 0 : suspendedElements.Count; } }

        private static uint SafeSelectionCount()
        {
            try { return SelectionSetManager.IsActive() ? SelectionSetManager.NumSelected() : 0; }
            catch { return 0; }
        }

        private uint SafeAgendaCount()
        {
            try
            {
                var agenda = ElementAgenda;
                return agenda == null ? 0 : agenda.GetCount();
            }
            catch { return 0; }
        }

        private ElementSource SafeElementSource()
        {
            try { return GetElementSource(); }
            catch { return ElementSource.Pick; }
        }
    }

    /// <summary>
    /// 点取工具的诊断日志：只记工具安装/清理与选择集挂起/归还，固定写到
    /// <c>%LOCALAPPDATA%\SteelSectionProbe\logs\Locate\latest.log</c>，每次进程启动覆盖，
    /// 超过 256 KB 自动截断。任何写入异常都被吞掉，绝不影响点取。
    /// </summary>
    internal static class ProbeLocateLog
    {
        private static readonly object Gate = new object();
        private static bool started;

        internal static void Write(string message)
        {
            try
            {
                lock (Gate)
                {
                    string directory = Path.Combine(
                        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                        "SteelSectionProbe", "logs", "Locate");
                    Directory.CreateDirectory(directory);
                    string file = Path.Combine(directory, "latest.log");
                    var info = new FileInfo(file);
                    if (!started || (info.Exists && info.Length > 256 * 1024))
                    {
                        started = true;
                        File.WriteAllText(file, "", new UTF8Encoding(false));
                    }
                    File.AppendAllText(file,
                        DateTime.Now.ToString("HH:mm:ss.fff", CultureInfo.InvariantCulture) + "  " + message +
                        Environment.NewLine, new UTF8Encoding(false));
                }
            }
            catch
            {
                // 日志是可选诊断，失败不得影响点取。
            }
        }
    }
}
