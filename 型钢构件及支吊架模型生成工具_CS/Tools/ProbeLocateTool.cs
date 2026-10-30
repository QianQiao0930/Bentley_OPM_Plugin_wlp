using System;
using System.Globalization;
using System.IO;
using System.Text;
using Bentley.DgnPlatformNET;

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
    /// 因此本基类在<b>构造工具（安装之前）</b>就清空活动选择集，让用户重新按光标点取。
    /// 旧选择直接放弃，不保存、不恢复；旧工具的延迟清理也不能把选择重新放回来。
    /// 除此之外还固定了 <c>AllowSelection=None</c>、
    /// <c>AllowFence=None</c>、元素来源=直接点取，并在安装时清一次议程，作为多层兜底。
    /// </para>
    /// </summary>
    internal abstract class ProbeLocateTool : DgnElementSetTool
    {
        private bool ignoredSelectionSet;

        protected ProbeLocateTool() : base(0, 0) { ClearSelectionSet("无参构造"); }

        protected ProbeLocateTool(int toolId, int promptId) : base(toolId, promptId) { ClearSelectionSet("带参构造"); }

        /// <summary>本工具是否曾清空非空选择集（供派生工具的提示使用）。</summary>
        protected bool IgnoredSelectionSet { get { return ignoredSelectionSet; } }

        /// <summary>只读点取工具不接受选择集作为元素来源。</summary>
        protected override UsesSelection AllowSelection() { return UsesSelection.None; }

        /// <summary>只读点取工具同样不使用围栅（fence）作为元素来源。</summary>
        protected override UsesFence AllowFence() { return UsesFence.None; }

        /// <summary>元素来源固定为直接点取（Pick），不使用选择集或围栅。</summary>
        protected override ElementSource GetPreferredElementSource() { return ElementSource.Pick; }

        protected override bool OnInstall()
        {
            // 宿主可能在构造之后、安装之前处理旧工具的清理；进入基类安装前再次保证为空。
            ClearSelectionSet("OnInstall前");
            ProbeLocateLog.Write("OnInstall 安装前选择集数=" + SafeSelectionCount());
            bool installed = base.OnInstall();
            ResetElementSource("OnInstall");
            ProbeLocateLog.Write("OnInstall 结束：返回值=" + installed + "；议程=" + SafeAgendaCount() +
                "；来源=" + SafeElementSource());
            return installed;
        }

        protected override void OnPostInstall()
        {
            base.OnPostInstall();
            PrepareForPicking("OnPostInstall");
            ProbeLocateLog.Write("OnPostInstall：议程=" + SafeAgendaCount() +
                "；来源=" + SafeElementSource() + "；选择集数=" + SafeSelectionCount());
        }

        protected override void OnCleanup()
        {
            ProbeLocateLog.Write("OnCleanup：工具清理，不恢复已放弃的选择集");
            base.OnCleanup();
        }

        /// <summary>重复点击开始点取时复用当前工具，清空新选择和议程，不结束或重装工具。</summary>
        protected void PrepareForPicking(string stage)
        {
            ClearSelectionSet(stage);
            ResetElementSource(stage);
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
                throw new InvalidOperationException("无法清空点取议程，请结束点取后重试。", ex);
            }
            try { SetElementSource(ElementSource.Pick); }
            catch (Exception ex)
            {
                ProbeLocateLog.Write(stage + "：复位元素来源失败：" + ex.Message);
                throw new InvalidOperationException("无法切换到光标点取，请结束点取后重试。", ex);
            }
        }

        /// <summary>
        /// 直接放弃当前全部选择，不读取、缓存或恢复元素。清空失败时停止安装，避免带着旧议程继续。
        /// </summary>
        private void ClearSelectionSet(string stage)
        {
            try
            {
                uint count = SelectionSetManager.IsActive() ? SelectionSetManager.NumSelected() : 0;
                SelectionSetManager.EmptyAll();
                uint remaining = SelectionSetManager.IsActive() ? SelectionSetManager.NumSelected() : 0;
                if (remaining != 0) throw new InvalidOperationException("清空后仍有 " + remaining + " 个选中元素。");
                ignoredSelectionSet |= count > 0;
                ProbeLocateLog.Write("放弃选择集（" + stage + "）：原有 " + count + " 个，清空后 " + remaining + " 个；不恢复旧选择。");
            }
            catch (Exception ex)
            {
                ProbeLocateLog.Write("清空选择集失败（" + stage + "）：" + ex.Message);
                throw new InvalidOperationException("无法清空当前选择集，请先取消选择后再点取。", ex);
            }
        }

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
    /// 点取工具的诊断日志：只记工具安装/清理与选择集清空，固定写到
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
