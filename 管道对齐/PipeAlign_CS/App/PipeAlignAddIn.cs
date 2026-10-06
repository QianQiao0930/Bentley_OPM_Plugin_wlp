using System;
using Bentley.MstnPlatformNET;

namespace PipeAlign
{
    /// <summary>
    /// PipeAlign 的 AddIn 宿主（开发指南 §6 的 <c>Commands/PipeAlignCommand</c> 落点）。
    /// <para>
    /// 与 SDK 示例 <c>QueryPipeWithPortsExample</c> 一致：<c>MdlTaskID</c> 必须与
    /// 程序集名 / <c>MS_ADDINPATH</c> 下的加载名一致（<c>MDL LOAD PipeAlign</c>）。
    /// </para>
    /// </summary>
    [AddInAttribute(MdlTaskID = "PipeAlign")]
    public sealed class PipeAlignAddIn : AddIn
    {
        internal static PipeAlignAddIn Instance;

        private PipeAlignAddIn(IntPtr descriptor) : base(descriptor)
        {
            Instance = this;
        }

        protected override int Run(string[] args)
        {
            return 0;
        }
    }
}
