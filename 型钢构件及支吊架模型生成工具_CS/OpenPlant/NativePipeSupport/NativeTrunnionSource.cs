using System;
using Bentley.ECObjects.Instance;
using Bentley.MstnPlatformNET;
using Bentley.OpenPlantModeler.SDK.Utilities;

namespace SteelSectionProbe
{
    internal static class NativeTrunnionSource
    {
        internal static bool Eligible(ElbowTrunnionSelection source)
        { return source != null && source.IsNativePipingElbow && !source.IsFromReference; }

        internal static IECInstance Resolve(ElbowTrunnionSelection source, ElbowTrunnionParameters options)
        {
            if (!Eligible(source) || string.IsNullOrEmpty(source.NativeParentInstanceId))
                throw new InvalidOperationException("无法确定活动模型原生弯头身份，请重新点取。");
            double scale = Session.Instance.GetActiveDgnModel().GetModelInfo().UorPerMeter / 1000.0;
            NativeSupportData.Finite(scale); NativeSupportData.Finite(source.SourceUorPerMm);
            if (source.NativeModelToken != NativeSupportElements.ActiveModelToken() || scale <= 0
                || Math.Abs(scale - source.SourceUorPerMm) > Math.Max(1e-9, scale * 1e-12))
                throw new InvalidOperationException("活动模型或单位已改变，请重新点取弯头。");
            var parent = DgnUtilities.GetInstanceByInstanceId(source.NativeParentInstanceId);
            if (parent == null || string.IsNullOrEmpty(source.ClassName)
                || !source.ClassName.EndsWith("." + parent.ClassDefinition.Name, StringComparison.Ordinal)
                || parent.ClassDefinition.Name.IndexOf("ELBOW", StringComparison.OrdinalIgnoreCase) < 0)
                throw new InvalidOperationException("源弯头已删除或身份改变，请重新点取。");
            using (var element = NativeSupportElements.Get(parent, true))
                if ((ulong)element.ElementId != source.ElementId) throw new InvalidOperationException("源弯头元素身份不一致。");
            var current = ElbowTrunnionReader.Read(source.ElementId, options.Elbow, options.Trunnion);
            if (!Eligible(current) || current.NativeParentInstanceId != source.NativeParentInstanceId
                || current.ClassName != source.ClassName || current.MainDn != source.MainDn
                || Math.Abs(current.OutsideDiameterMm - source.OutsideDiameterMm) > .001)
                throw new InvalidOperationException("预览后弯头类型或管径已改变，请重新点取。");
            var before = Coordinates(source.Frame); var after = Coordinates(current.Frame);
            for (int i = 0; i < before.Length; i++)
            {
                NativeSupportData.Finite(before[i]); NativeSupportData.Finite(after[i]);
                if (Math.Abs(before[i] - after[i]) > 1e-6)
                    throw new InvalidOperationException("预览后弯头位置、方向或尺寸已改变，请重新点取。");
            }
            return parent;
        }

        private static double[] Coordinates(ElbowFrame f)
        {
            if (f == null) throw new InvalidOperationException("弯头定位架缺失。");
            return new[] { f.Origin.X, f.Origin.Y, f.Origin.Z, f.AxisX.X, f.AxisX.Y, f.AxisX.Z,
                f.AxisZ.X, f.AxisZ.Y, f.AxisZ.Z, f.RunLengthMm, f.OutletLengthMm,
                f.RunPort.X, f.RunPort.Y, f.RunPort.Z, f.OutletPort.X, f.OutletPort.Y, f.OutletPort.Z,
                f.ArcCenter.X, f.ArcCenter.Y, f.ArcCenter.Z, f.HorizontalPort.X, f.HorizontalPort.Y, f.HorizontalPort.Z,
                f.VerticalPort.X, f.VerticalPort.Y, f.VerticalPort.Z, f.HorizontalDirection.X, f.HorizontalDirection.Y,
                f.HorizontalDirection.Z, f.SupportAxis.X, f.SupportAxis.Y, f.SupportAxis.Z, f.VerticalEndUp ? 1.0 : 0.0 };
        }
    }
}
