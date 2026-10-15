using System;

namespace SteelSectionProbe
{
    /// <summary>Versioned, immutable placement recipe. Coordinates are mm, independent of model UOR.</summary>
    internal sealed class NativePipeSupportRecipe
    {
        internal int Version = 1;
        internal string Code, CellName;
        internal double[] CenterMm, Axis;
        internal A1ClampPlan A1;
        internal U3ClampPlan U3;
        internal A2ClampPlan A2;
        internal A22ClampPlan A22;
        internal E1GuidePlan E1;
        internal K1LimitPlan K1;
        internal T4ShoeLayout Shoe;
        internal T4ShoeBooleanLayout Boolean;
        internal bool BuildPipe, BuildInsulation;
        internal VerticalPipeSupportPlan Vertical;
        internal ElbowTrunnionPlan Elbow;

        internal int Dn
        {
            get
            {
                switch (Code)
                {
                    case "A1": return A1.Row.Dn;
                    case "U3": return U3.Clamp.Row.Dn;
                    case "A2": return A2.Dn;
                    case "A22": case "A24": return A22.Dn;
                    case "E1": return E1.Dn;
                    case "K1": return K1.Dn;
                    case "T4": case "L2": return Shoe.Dn;
                    case "F6": case "F7": case "F10": return Vertical.PipeDn;
                    case "F2": case "F2-HE": case "F4": case "F5": return Elbow.Selection.MainDn;
                    default: throw new InvalidOperationException("未登记的原生管夹配方类别。");
                }
            }
        }

        internal double HandleLengthMm
        {
            get
            {
                switch (Code)
                {
                    case "A1": return Math.Max(1, A1.Row.D);
                    case "U3": return Math.Max(1, U3.Clamp.Row.D + U3.BlockHeightMm);
                    case "A2": return Math.Max(1, A2.CylinderRadiusMm);
                    case "A22": case "A24": return Math.Max(1, A22.OuterRadiusMm);
                    case "E1": return Math.Max(1, E1.HeightMm);
                    case "K1": return Math.Max(1, Math.Abs(K1.ContactOffsetMm));
                    case "F6": case "F7": case "F10": return Math.Max(1, Math.Max(Vertical.LengthMm, Vertical.EarWidthMm));
                    case "F2": case "F2-HE": case "F4": case "F5": return Math.Max(1, Elbow.Parameters.ExtentMm);
                    default: return Math.Max(1, Shoe.HeightMm);
                }
            }
        }

        /// <summary>
        /// 弯头耳轴位置由选型与弯头几何固定，不提供原生移动/旋转操作柄；仍通过父弯头关联随动。
        /// 管夹与立管耳轴保留操作长度与方向标记以启用操作柄。
        /// </summary>
        internal bool AllowManualEditHandles
        {
            get
            {
                switch (Code)
                {
                    case "F2": case "F2-HE": case "F4": case "F5": return false;
                    default: return true;
                }
            }
        }

        internal void Validate()
        {
            if (Version != 1 || string.IsNullOrWhiteSpace(CellName) || CenterMm == null || CenterMm.Length != 3 || Axis == null || Axis.Length != 3)
                throw new InvalidOperationException("原生管夹配方版本、名称或坐标不完整。");
            double axisLength2 = 0;
            for (int i = 0; i < 3; i++)
            {
                Finite(CenterMm[i]); Finite(Axis[i]);
                axisLength2 += Axis[i] * Axis[i];
            }
            Finite(axisLength2);
            if (axisLength2 < 1e-18) throw new InvalidOperationException("原生管夹配方管轴无效。");
            int plans = (A1 == null ? 0 : 1) + (U3 == null ? 0 : 1) + (A2 == null ? 0 : 1)
                + (A22 == null ? 0 : 1) + (E1 == null ? 0 : 1) + (K1 == null ? 0 : 1) + (Shoe == null ? 0 : 1)
                + (Vertical == null ? 0 : 1) + (Elbow == null ? 0 : 1);
            bool valid;
            switch (Code)
            {
                case "A1": valid = A1?.Row != null; break;
                case "U3": valid = U3?.Clamp?.Row != null; break;
                case "A2": valid = A2 != null; break;
                case "A22": case "A24": valid = A22 != null; break;
                case "E1": valid = E1?.Item != null; break;
                case "K1": valid = K1 != null; break;
                case "T4": case "L2": valid = Shoe != null && Boolean != null; break;
                case "F6": case "F7": case "F10": valid = Vertical != null && Code == Vertical.Kind.ToString(); break;
                case "F2": case "F2-HE": case "F4": case "F5":
                    valid = Elbow?.Selection?.Frame != null && Elbow.Parameters != null
                        && Code == TrunnionCode(Elbow.Parameters); break;
                default: valid = false; break;
            }
            if (!valid || plans != 1 || (Shoe == null && Boolean != null) || Dn <= 0)
                throw new InvalidOperationException("原生管夹类别与保存的建模计划不一致。");
        }
        internal static string TrunnionCode(ElbowTrunnionParameters p)
        {
            if (!Enum.IsDefined(typeof(ElbowOrientation), p.Elbow) || !Enum.IsDefined(typeof(TrunnionOrientation), p.Trunnion))
                throw new InvalidOperationException("耳轴方向无效。");
            return p.Trunnion == TrunnionOrientation.Vertical
                ? (p.Elbow == ElbowOrientation.Vertical ? "F2" : "F2-HE")
                : (p.Elbow == ElbowOrientation.Vertical ? "F4" : "F5");
        }
        private static void Finite(double value)
        { if (double.IsNaN(value) || double.IsInfinity(value)) throw new InvalidOperationException("管夹配方坐标无效。"); }
    }
}
