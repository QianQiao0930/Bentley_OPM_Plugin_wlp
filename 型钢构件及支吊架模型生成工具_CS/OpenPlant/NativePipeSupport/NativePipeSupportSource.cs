using System;
using Bentley.ECObjects.Instance;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
using Bentley.OpenPlantModeler.SDK.Utilities;

namespace SteelSectionProbe
{
    internal static class NativePipeSupportSource
    {
        internal static bool Eligible(PipeClampSelection source)
        { return source != null && source.IsPipe && !source.IsFromReference; }

        internal static IECInstance Resolve(PipeClampSelection source, double[] pointMm, int dn)
        {
            if (!Eligible(source) || string.IsNullOrEmpty(source.NativePipeInstanceId))
                throw new InvalidOperationException("无法确定活动模型原生管道身份，请重新点取。");
            if (source.NativeModelToken != NativeSupportElements.ActiveModelToken())
                throw new InvalidOperationException("活动模型已改变，请重新点取管道。");
            double scale = Session.Instance.GetActiveDgnModel().GetModelInfo().UorPerMeter / 1000.0;
            NativeSupportData.Finite(scale);
            NativeSupportData.Finite(source.SourceUorPerMm);
            if (scale <= 0 || Math.Abs(scale - source.SourceUorPerMm) > Math.Max(1e-9, scale * 1e-12))
                throw new InvalidOperationException("模型单位已改变，请重新点取管道。");
            var pipe = DgnUtilities.GetInstanceByInstanceId(source.NativePipeInstanceId);
            if (pipe == null || pipe.ClassDefinition.Name != "PIPE") throw new InvalidOperationException("源直管已删除或类型改变，请重新点取。");
            using (var element = NativeSupportElements.Get(pipe, true))
                if ((ulong)element.ElementId != source.ElementId) throw new InvalidOperationException("源管道身份已改变，请重新点取。");
            var current = PipeClampReader.Read(source.ElementId, 0, 0, 0);
            var before = new[] { source.StartX, source.StartY, source.StartZ, source.EndX, source.EndY, source.EndZ };
            var after = new[] { current.StartX, current.StartY, current.StartZ, current.EndX, current.EndY, current.EndZ };
            for (int i = 0; i < before.Length; i++)
            {
                NativeSupportData.Finite(before[i]); NativeSupportData.Finite(after[i]);
                if (Math.Abs(before[i] - after[i]) > .01) throw new InvalidOperationException("预览后管轴已改变，请重新点取并生成预览。");
            }
            if (!current.NominalMm.HasValue || Math.Abs(current.NominalMm.Value - dn) > .5)
                throw new InvalidOperationException("构件DN与当前真实管道不一致，不能建立出图关系。");
            NativeSupportData.Finite(current.NominalMm.Value);
            if (source.OutsideMm != current.OutsideMm || source.InsulationMm != current.InsulationMm)
                throw new InvalidOperationException("预览后管道外径或保温已改变，请重新点取。");
            double dx = current.AxisX, dy = current.AxisY, dz = current.AxisZ;
            double length2 = dx * dx + dy * dy + dz * dz;
            if (length2 < 1e-12) throw new InvalidOperationException("管轴长度无效。");
            double t = ((pointMm[0] - current.StartX) * dx + (pointMm[1] - current.StartY) * dy + (pointMm[2] - current.StartZ) * dz) / length2;
            double error2 = Math.Pow(pointMm[0] - current.StartX - t * dx, 2) + Math.Pow(pointMm[1] - current.StartY - t * dy, 2) + Math.Pow(pointMm[2] - current.StartZ - t * dz, 2);
            NativeSupportData.Finite(t); NativeSupportData.Finite(error2);
            if (t < -1e-9 || t > 1 + 1e-9 || error2 > .01)
                throw new InvalidOperationException("构件定位点不在当前直管轴段上，请调整沿轴偏移。");
            return pipe;
        }

        internal static void Frame(DPoint3d origin, DVector3d axis, out DTransform3d placement, out DTransform3d inverse)
        {
            double[] x, y, z;
            foreach (double value in new[] { origin.X, origin.Y, origin.Z, axis.X, axis.Y, axis.Z }) NativeSupportData.Finite(value);
            PipeClampFrame.Axes(axis.X, axis.Y, axis.Z, out x, out y, out z);
            FromAxes(origin, x, y, z, out placement, out inverse);
        }

        /// <summary>
        /// 按配方选择坐标架。立管耳轴用自带 SinglePipeTrunnion 的轴：X=管轴，−Z=耳轴伸出。
        /// 操作长度和旋转柄沿局部 Z；若把 Z 设成管轴，旋转柄就会落到立管上。
        /// </summary>
        internal static void PlacementFrame(NativePipeSupportRecipe recipe, double scale,
            out DTransform3d placement, out DTransform3d inverse)
        {
            if (recipe == null) throw new InvalidOperationException("原生耳轴配方为空。");
            NativeSupportData.Finite(scale);
            if (scale <= 0) throw new InvalidOperationException("模型单位无效。");
            var origin = new DPoint3d(recipe.CenterMm[0] * scale, recipe.CenterMm[1] * scale, recipe.CenterMm[2] * scale);
            var axis = new DVector3d(recipe.Axis[0], recipe.Axis[1], recipe.Axis[2]);
            if (recipe.Vertical != null)
                TrunnionFrame(origin, axis, recipe.Vertical.AzimuthDegrees,
                    recipe.Vertical.Kind == VerticalPipeSupportKind.F10, out placement, out inverse);
            else
                Frame(origin, axis, out placement, out inverse);
        }

        /// <summary>
        /// 与自带 SinglePipeTrunnion 相同：圆柱与 LENGTH 落在局部 −Z（耳轴端），
        /// 点串 direction=−X 沿管轴（滑动）。F6/F7 的 0°=+Y；F10 的 0°=+X。
        /// </summary>
        internal static void TrunnionFrame(DPoint3d origin, DVector3d pipeAxis, double azimuthDegrees, bool f10,
            out DTransform3d placement, out DTransform3d inverse)
        {
            foreach (double value in new[] { origin.X, origin.Y, origin.Z, pipeAxis.X, pipeAxis.Y, pipeAxis.Z, azimuthDegrees })
                NativeSupportData.Finite(value);
            double length = Math.Sqrt(pipeAxis.X * pipeAxis.X + pipeAxis.Y * pipeAxis.Y + pipeAxis.Z * pipeAxis.Z);
            if (length <= 1e-12) throw new InvalidOperationException("立管轴线长度无效。");
            double[] pipe = { pipeAxis.X / length, pipeAxis.Y / length, pipeAxis.Z / length };
            double radians = azimuthDegrees * Math.PI / 180.0;
            double refX = f10 ? Math.Cos(radians) : Math.Sin(radians);
            double refY = f10 ? Math.Sin(radians) : Math.Cos(radians);
            double dotOut = refX * pipe[0] + refY * pipe[1];
            double ox = refX - dotOut * pipe[0], oy = refY - dotOut * pipe[1], oz = 0.0 - dotOut * pipe[2];
            double outLength = Math.Sqrt(ox * ox + oy * oy + oz * oz);
            if (outLength <= 1e-12) throw new InvalidOperationException("耳轴方位角与管轴平行，无法定位。");
            // Stock cylinder runs along local -Z and LENGTH reaches that tip.
            double[] z = { -ox / outLength, -oy / outLength, -oz / outLength };
            double dot = pipe[0] * z[0] + pipe[1] * z[1] + pipe[2] * z[2];
            double xx = pipe[0] - dot * z[0], xy = pipe[1] - dot * z[1], xz = pipe[2] - dot * z[2];
            double xLength = Math.Sqrt(xx * xx + xy * xy + xz * xz);
            if (xLength <= 1e-12) throw new InvalidOperationException("耳轴坐标架叉积失败。");
            double[] x = { xx / xLength, xy / xLength, xz / xLength };
            double[] y = {
                z[1] * x[2] - z[2] * x[1],
                z[2] * x[0] - z[0] * x[2],
                z[0] * x[1] - z[1] * x[0] };
            double yLength = Math.Sqrt(y[0] * y[0] + y[1] * y[1] + y[2] * y[2]);
            if (yLength <= 1e-12) throw new InvalidOperationException("耳轴坐标架叉积失败。");
            y[0] /= yLength; y[1] /= yLength; y[2] /= yLength;
            FromAxes(origin, x, y, z, out placement, out inverse);
        }

        private static void FromAxes(DPoint3d origin, double[] x, double[] y, double[] z,
            out DTransform3d placement, out DTransform3d inverse)
        {
            placement = new DTransform3d(DMatrix3d.FromColumns(
                new DVector3d(x[0], x[1], x[2]), new DVector3d(y[0], y[1], y[2]), new DVector3d(z[0], z[1], z[2])))
            { Translation = origin };
            inverse = new DTransform3d(DMatrix3d.FromColumns(
                new DVector3d(x[0], y[0], z[0]), new DVector3d(x[1], y[1], z[1]), new DVector3d(x[2], y[2], z[2])))
            {
                Translation = new DPoint3d(
                    -x[0] * origin.X - x[1] * origin.Y - x[2] * origin.Z,
                    -y[0] * origin.X - y[1] * origin.Y - y[2] * origin.Z,
                    -z[0] * origin.X - z[1] * origin.Y - z[2] * origin.Z)
            };
        }
    }
}
