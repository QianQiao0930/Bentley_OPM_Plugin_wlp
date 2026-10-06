using Bentley.DgnPlatformNET;

namespace PipeAlign
{
    /// <summary>
    /// 由 DGN 模型构造 <see cref="UnitService"/>（开发指南 §17）。
    /// <para>
    /// 全工程**只有这里**读 <c>ModelInfo</c>；其余代码一律通过 <see cref="IUnitService"/> 换算。
    /// </para>
    /// </summary>
    internal static class DgnUnitServiceFactory
    {
        internal static double MillimetersPerMasterUnit(DgnModel model)
        {
            ModelInfo info = model == null ? null : model.GetModelInfo();
            double uorPerMm = UorPerMillimeter(model);
            return info != null && uorPerMm > 0.0 ? info.UorPerMaster / uorPerMm : 0.0;
        }
        /// <summary>从模型引用取单位服务；取不到时返回"不可用"的实例而不是抛异常。</summary>
        internal static IUnitService ForModel(DgnModelRef modelRef)
        {
            DgnModel model = modelRef == null ? null : modelRef.GetDgnModel();
            if (model == null) model = Bentley.MstnPlatformNET.Session.Instance.GetActiveDgnModel();
            return ForModel(model);
        }

        internal static IUnitService ForModel(DgnModel model)
        {
            if (model == null) return UnitService.Unavailable();
            ModelInfo info = model.GetModelInfo();
            if (info == null) return UnitService.Unavailable();
            // UorPerMeter / 1000 = 每毫米的 UOR 数。这是本仓库 C# 侧已验证的换算路径。
            return new UnitService(info.UorPerMeter / 1000.0);
        }

        /// <summary>
        /// 取"每毫米多少 UOR"。取不到时返回 0，调用方必须自行判断并给出中文提示。
        /// </summary>
        internal static double UorPerMillimeter(DgnModel model)
        {
            IUnitService service = ForModel(model);
            return service.IsAvailable ? service.UorPerMillimeter : 0.0;
        }
    }
}
