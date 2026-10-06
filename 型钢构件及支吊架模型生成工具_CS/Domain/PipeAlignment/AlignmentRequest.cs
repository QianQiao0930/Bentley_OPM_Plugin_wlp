using System.Collections.Generic;

namespace SteelSectionProbe.PipeAlignment
{
    /// <summary>
    /// 一次对齐请求（开发指南 §2.2）。
    /// <para>
    /// 基准管是**独立对象**，目标管是**集合** —— 程序不得通过
    /// <c>Selection Set</c> 的返回顺序推断基准管。
    /// </para>
    /// </summary>
    internal sealed class AlignmentRequest
    {
        internal AlignmentRequest(PipeInfo referencePipe, IList<PipeInfo> targetPipes,
            AlignmentMode mode, SurfaceMode surfaceMode, PipeAlignOptions options)
            : this(referencePipe, targetPipes, mode, surfaceMode, options, null)
        {
        }

        /// <param name="seedInstanceIds">
        /// 用户**直接选中**的实例 ID 集合（Move Group 展开前的种子）。
        /// 用来在计划里标出哪些管是"自动带进来一起移动的"，null 表示不区分。
        /// </param>
        internal AlignmentRequest(PipeInfo referencePipe, IList<PipeInfo> targetPipes,
            AlignmentMode mode, SurfaceMode surfaceMode, PipeAlignOptions options,
            IList<string> seedInstanceIds)
        {
            ReferencePipe = referencePipe;
            TargetPipes = targetPipes ?? new List<PipeInfo>();
            Mode = mode;
            SurfaceMode = surfaceMode;
            Options = options ?? new PipeAlignOptions();
            SeedInstanceIds = seedInstanceIds;
        }

        /// <summary>用户直接选中的实例 ID 集合；null 表示"全部都是直接选中的"。</summary>
        internal IList<string> SeedInstanceIds { get; private set; }

        /// <summary>基准管。插件从它取得目标标高。</summary>
        internal PipeInfo ReferencePipe { get; private set; }

        /// <summary>目标管集合。顺序与业务无关。</summary>
        internal IList<PipeInfo> TargetPipes { get; private set; }

        /// <summary>对齐基准。</summary>
        internal AlignmentMode Mode { get; private set; }

        /// <summary>表面模式。</summary>
        internal SurfaceMode SurfaceMode { get; private set; }

        /// <summary>运行参数（水平容差等）。</summary>
        internal PipeAlignOptions Options { get; private set; }
    }
}
