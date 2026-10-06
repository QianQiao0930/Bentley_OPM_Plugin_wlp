using System;
using Bentley.DgnPlatformNET;
using Bentley.MstnPlatformNET;

namespace PipeAlign
{
    /// <summary>
    /// Key-in 处理器（开发指南 §32）。
    /// <para>命令表见 <c>Registration/commands.xml</c>；逻辑资源名固定为 <c>CommandTable.xml</c>。</para>
    /// </summary>
    public static class Keyins
    {
        public static void OpenZMove(string unparsed)
        {
            PipeAlignSession session = CurrentSession();
            session.Scope = MoveScope.ZStretch;
            session.Plan = null;
            Start(null, "");
        }
        /// <summary><c>PIPEALIGN</c>：打开窗口，模式取配置文件里的默认值。</summary>
        public static void OpenWindow(string unparsed)
        {
            Start(null, unparsed);
        }

        /// <summary><c>PIPEALIGN BOTTOM</c>。</summary>
        public static void OpenWindowBottom(string unparsed)
        {
            Start(AlignmentMode.Bottom, unparsed);
        }

        /// <summary><c>PIPEALIGN CENTER</c>。</summary>
        public static void OpenWindowCenter(string unparsed)
        {
            Start(AlignmentMode.Center, unparsed);
        }

        /// <summary><c>PIPEALIGN TOP</c>。</summary>
        public static void OpenWindowTop(string unparsed)
        {
            Start(AlignmentMode.Top, unparsed);
        }

        /// <summary>
        /// <c>PIPEALIGN DEBUG</c>：只读打印选中管道的调试数据，不修改模型（指南 §31）。
        /// </summary>
        public static void DebugDump(string unparsed)
        {
            RunDebug(false);
        }

        /// <summary><c>PIPEALIGN DEBUG DUMP</c>：在上面的基础上追加全部 EC 属性。</summary>
        public static void DebugDumpAll(string unparsed)
        {
            RunDebug(true);
        }

        /// <summary><c>PIPEALIGN OPTIONS</c>：把当前运行参数写回配置文件，便于现场修改。</summary>
        public static void WriteOptionsFile(string unparsed)
        {
            try
            {
                PipeAlignSession session = CurrentSession();
                string path = session.SaveOptions();
                NotificationManager.OutputPrompt("PipeAlign 运行参数已写入：" + path);
                session.Log.Info("运行参数已写入：" + path);
                session.Log.Flush();
            }
            catch (Exception ex)
            {
                NotificationManager.OutputPrompt("写入运行参数失败：" + ex.Message);
            }
        }

        private static void Start(AlignmentMode? mode, string unparsed)
        {
            try
            {
                PipeAlignSession session = CurrentSession();
                if (mode.HasValue)
                {
                    session.Mode = mode.Value;
                }
                else if (!TryReadModeFromUnparsed(unparsed, session))
                {
                    session.Mode = session.Options.DefaultAlignmentMode;
                }
                session.SurfaceMode = session.Options.DefaultSurfaceMode;

                session.Log.Info(string.Format("PipeAlign started. Alignment mode: {0}.",
                    AlignmentModes.Code(session.Mode)));
                session.Log.Flush();

                PipeAlignDialog.ShowDialog(session, session.Mode);
            }
            catch (Exception ex)
            {
                NotificationManager.OutputPrompt("PipeAlign 启动失败：" + ex.Message);
            }
        }

        /// <summary>
        /// <c>PIPEALIGN BOTTOM</c> 这类带参数的写法，Key-in 表把它们绑到了各自的处理器；
        /// 但用户也可能直接键入 <c>PIPEALIGN TOP</c> 而命中不带参数的处理器，
        /// 因此这里再解析一次未匹配的尾串，避免"模式被静默忽略"。
        /// </summary>
        private static bool TryReadModeFromUnparsed(string unparsed, PipeAlignSession session)
        {
            if (string.IsNullOrWhiteSpace(unparsed)) return false;
            string text = unparsed.Trim();
            int space = text.IndexOf(' ');
            if (space > 0) text = text.Substring(0, space);
            AlignmentMode mode;
            if (!AlignmentModes.TryParse(text, out mode)) return false;
            session.Mode = mode;
            return true;
        }

        private static void RunDebug(bool dumpAllProperties)
        {
            try
            {
                PipeAlignSession session = CurrentSession();
                session.Log.Info("PipeAlign DEBUG：只读检查开始。");
                PipeAlignDialog.ShowDebugReport(session, dumpAllProperties);
                session.Log.Flush();
            }
            catch (Exception ex)
            {
                NotificationManager.OutputPrompt("PipeAlign DEBUG 失败：" + ex.Message);
            }
        }

        private static PipeAlignSession _session;

        /// <summary>
        /// 会话单例。窗口关闭时不销毁它 —— 用户常常"关掉窗口改个模式再打开"，
        /// 保留已选好的基准管与目标管更符合现场习惯；<c>重置</c> 按钮负责真正清空。
        /// </summary>
        private static PipeAlignSession CurrentSession()
        {
            if (_session == null) _session = new PipeAlignSession();
            return _session;
        }
    }
}
