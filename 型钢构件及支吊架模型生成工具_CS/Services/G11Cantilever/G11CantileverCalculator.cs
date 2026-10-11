using System;
using System.Globalization;

namespace SteelSectionProbe
{
    /// <summary>按 G11 类型和表格计算截面、连接段及两根锚栓的位置。</summary>
    internal static class G11CantileverCalculator
    {
        internal static D2CantileverPlan Calculate(D2CantileverParameters parameters,
            double lengthMm, double headingDegrees)
        {
            if (parameters == null)
            {
                throw new ArgumentNullException(nameof(parameters));
            }

            if (parameters.Kind != "G11" || parameters.Type < 1 || parameters.Type > 5)
            {
                throw new InvalidOperationException("G11 只支持类型 1～5。");
            }

            if (parameters.AddPlate)
            {
                throw new InvalidOperationException("G11 直接以型钢锚固，不附加 G2 端板。");
            }

            if (!IsFinite(lengthMm) || lengthMm <= 0 || !IsFinite(headingDegrees))
            {
                throw new InvalidOperationException("辅助线长度及方向无效。");
            }

            if (!IsFinite(parameters.LoadDistanceMm) || parameters.LoadDistanceMm <= 0 ||
                parameters.LoadDistanceMm > 1000 || parameters.LoadDistanceMm > lengthMm)
            {
                throw new InvalidOperationException("荷载距离 B 必须大于零、不超过 1000 mm，且不超过 L。");
            }

            G11CantileverVariant variant = G11CantileverCatalog.Require(parameters.Subtype);
            ProfileData profile = D2CantileverCatalog.Profile(variant.Section);
            bool isAngle = variant.Section.Family == "equal_angle";
            double widthMm = profile.Dimensions["B"];
            double heightMm = isAngle ? widthMm : profile.Dimensions["H"];
            bool hasConnection = parameters.Type == 2 || parameters.Type == 3;
            double secondBoltMm = G11CantileverCatalog.FirstBoltDistanceMm + variant.BoltSpacingMm;
            if (!hasConnection && lengthMm <= secondBoltMm + G2AnchorCatalog.Require(parameters.Subtype.ToString()).WasherOutsideMm / 2)
            {
                throw new InvalidOperationException("辅助线过短，第二根锚栓及垫圈必须位于悬臂范围内。");
            }

            double thicknessMm = isAngle ? profile.Dimensions["t"] :
                profile.Dimensions[hasConnection || parameters.Type == 4 || parameters.Type == 5 ? "tf" : "tw"];
            G2AnchorPlan bolt = CreateBolt(parameters.Subtype, thicknessMm, headingDegrees);
            double connectionLengthMm = hasConnection ? variant.BoltSpacingMm + 150 : 0;
            // 下置角钢贴合横担的两个内表面，不能按横担全高定位。
            double angleThicknessMm = isAngle ? profile.Dimensions["t"] : 0;
            double connectionStartZMm = parameters.Type == 3 ?
                -(isAngle ? angleThicknessMm : heightMm) : 0;
            double connectionStartYMm = -widthMm / 2 +
                (isAngle && parameters.Type == 3 ? angleThicknessMm : 0);
            double connectionBoltYMm = connectionStartYMm + widthMm / 2;
            var anchors = new G11AnchorLocation[2];
            for (int index = 0; index < anchors.Length; index++)
            {
                double stationMm = G11CantileverCatalog.FirstBoltDistanceMm + index * variant.BoltSpacingMm;
                anchors[index] = new G11AnchorLocation
                {
                    XMm = hasConnection ? 0 : stationMm,
                    YMm = hasConnection ? connectionBoltYMm : parameters.Type == 1 ? -widthMm / 2 : 0,
                    ZMm = hasConnection ? connectionStartZMm + (parameters.Type == 2 ? stationMm : -stationMm) :
                        parameters.Type == 1 ? -heightMm / 2 : parameters.Type == 4 ? -heightMm : 0
                };
            }

            double? verticalLoadKn = null;
            for (int index = 0; index < G11CantileverCatalog.LoadColumnsMm.Length; index++)
            {
                if (parameters.LoadDistanceMm <= G11CantileverCatalog.LoadColumnsMm[index])
                {
                    verticalLoadKn = variant.Section.Loads[index];
                    break;
                }
            }

            string name = string.IsNullOrWhiteSpace(parameters.Name) ? "G11" : parameters.Name.Trim();
            return new D2CantileverPlan
            {
                Parameters = parameters,
                Variant = variant.Section,
                Number = name + "-" + parameters.Type + "-" + parameters.Subtype + "-" +
                    Math.Floor(lengthMm + 0.5).ToString("0", CultureInfo.InvariantCulture),
                Specification = variant.Section.Section + "；L=" + Format(lengthMm) + " mm；B=" +
                    Format(parameters.LoadDistanceMm) + " mm；2×" + bolt.BoltSpecification +
                    "；S=" + Format(variant.BoltSpacingMm) + " mm；C=" + Format(variant.ConcreteEdgeDistanceMm) + " mm",
                LengthMm = lengthMm,
                BeamLengthMm = lengthMm,
                SectionHeightMm = heightMm,
                SectionWidthMm = widthMm,
                SectionAnchorYmm = -widthMm / 2,
                SectionAnchorZmm = parameters.Type == 4 ? -heightMm : 0,
                VerticalLoadKn = verticalLoadKn,
                // G11 表中没有规定水平荷载系数。
                HorizontalLoadKn = null,
                ConcreteAnchor = new G11CantileverPlan
                {
                    Variant = variant,
                    Bolt = bolt,
                    Anchors = anchors,
                    ConnectionLengthMm = connectionLengthMm,
                    ConnectionStartXMm = isAngle ? 0 : heightMm,
                    ConnectionStartZMm = connectionStartZMm,
                    ConnectionStartYMm = connectionStartYMm,
                    ConnectionWidthAlongSide = !isAngle,
                    BoltNormalX = hasConnection ? 1 : 0,
                    BoltNormalY = parameters.Type == 1 ? 1 : 0,
                    BoltNormalZ = parameters.Type == 4 ? 1 : parameters.Type == 5 ? -1 : 0,
                    BeamVerticalSign = parameters.Type == 4 ? 1 : -1
                }
            };
        }

        private static G2AnchorPlan CreateBolt(char subtype, double thicknessMm, double headingDegrees)
        {
            G2AnchorPlan bolt = G2AnchorCalculator.Calculate(new G2AnchorParameters
            {
                SubtypeKey = subtype.ToString(),
                HeadingDegrees = headingDegrees
            });
            // 复用 G12 的锚栓规则，以实际腹板或翼缘厚度替代锚板厚度。
            bolt.PlateThicknessMm = thicknessMm;
            bolt.BoltCount = 2;
            bolt.BoltOutLengthMm = thicknessMm + bolt.WasherThicknessMm + bolt.NutHeightMm +
                G2AnchorCatalog.BoltProtrusionMm;
            bolt.ActualEmbedmentMm = bolt.BoltLengthMm - bolt.BoltOutLengthMm;
            if (bolt.ActualEmbedmentMm < bolt.RequiredEmbedmentMm)
            {
                throw new InvalidOperationException("G11 锚栓有效埋深不足。");
            }

            bolt.SleeveLengthMm = bolt.ActualEmbedmentMm * G2AnchorCatalog.SleeveEmbedFraction;
            return bolt;
        }

        private static bool IsFinite(double value)
        {
            return !double.IsNaN(value) && !double.IsInfinity(value);
        }

        private static string Format(double value)
        {
            return value.ToString("0.###", CultureInfo.InvariantCulture);
        }
    }
}
