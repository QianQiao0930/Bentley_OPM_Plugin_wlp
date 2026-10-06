using System;

namespace PipeAlign
{
    /// <summary>
    /// 用元素几何 + EC 变换复核移动结果（开发指南 §19）。
    /// <para>
    /// 复核走的是与移动完全不同的通道：<see cref="PipeElementReader"/> 重新读该元素，
    /// 一路从曲线 / 显示几何算中心线标高，一路从**已经枚举出来的** EC 属性里取
    /// <c>TRANSFORMATION_MATRIX.M11</c>。两条通道都指向新标高，才能说"数据与图形一致"。
    /// </para>
    /// <para>
    /// 元素身份（含模型引用）从 <see cref="PipeInfo.Source"/> 取，不能只按 ID 去活动模型查 ——
    /// 参考文件与活动模型各自编号，同号不是同一根管。
    /// </para>
    /// </summary>
    internal sealed class PipeGeometryVerifier : IPipeGeometryVerifier
    {
        private readonly PipeAlignLog _log;

        internal PipeGeometryVerifier(PipeAlignLog log)
        {
            _log = log;
        }

        public bool IsAvailable
        {
            get { return Bentley.MstnPlatformNET.Session.Instance.GetActiveDgnModel() != null; }
        }

        public PipeMoveVerification Verify(PipeInfo pipe)
        {
            PipeMoveVerification verification = new PipeMoveVerification();
            if (pipe == null)
            {
                verification.Warning = "管道数据为空。";
                return verification;
            }

            try
            {
                LocatedElement located = pipe.Source as LocatedElement;
                located = located ?? new LocatedElement { ElementId = pipe.ElementId };

                PipeReadOptions options = PipeReadOptions.ForVerification();
                options.ReadTopology = true;
                PipeInfo reread = PipeElementReader.Read(located.ModelRef, located.ElementId,
                    options, new OpenPlant2024ObjectProbe(), _log);
                verification.Topology = reread.Topology;
                verification.GeometryAxis = reread.Axis;
                verification.EcLengthRaw = reread.EcLengthRaw;

                verification.GeometryCenterElevationMm = reread.Axis == null
                    ? (double?)null
                    : reread.Axis.CenterElevationMm;
                verification.EcTranslationZRaw = reread.EcTranslationZRaw;
                verification.EcChanged = reread.EcTranslationZRaw.HasValue
                    && pipe.EcTranslationZRaw.HasValue
                    && Math.Abs(reread.EcTranslationZRaw.Value - pipe.EcTranslationZRaw.Value) > 1.0e-9;

                if (reread.EcTranslationZRaw.HasValue && reread.EcUorPerSub > 0.0)
                    verification.EcTranslationZmm =
                        reread.EcTranslationZRaw.Value / reread.EcUorPerSub;

                if (!string.IsNullOrEmpty(reread.ReadWarning))
                    verification.Warning = reread.ReadWarning;
            }
            catch (Exception ex)
            {
                verification.Warning = "复核读取失败：" + ex.Message;
            }

            return verification;
        }
    }
}
