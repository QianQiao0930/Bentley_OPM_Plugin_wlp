using System;
using System.Globalization;

namespace PipeAlign
{
    /// <summary>长度属性换算比例的来源。</summary>
    internal enum LengthScaleSource
    {
        /// <summary>用"属性 LENGTH ↔ 几何长度"标定得到。</summary>
        Calibrated = 0,

        /// <summary>用户在界面上手动指定。</summary>
        Manual = 1,

        /// <summary>标定不成立，按"数值 &lt; 1 视为米"兜底。</summary>
        Heuristic = 2,

        /// <summary>没有可用数值，按毫米处理。</summary>
        Default = 3
    }

    /// <summary>一次标定的结果。</summary>
    internal sealed class LengthScale
    {
        internal LengthScale(double scale, LengthScaleSource source, string warning)
        {
            Scale = scale;
            Source = source;
            Warning = warning;
        }

        /// <summary>属性值 → 毫米的乘数（1.0 = 属性存毫米，1000.0 = 属性存米）。</summary>
        internal double Scale { get; private set; }

        internal LengthScaleSource Source { get; private set; }

        /// <summary>需要展示给用户的提示（中文），没有则为 <c>null</c>。</summary>
        internal string Warning { get; private set; }

        internal string SourceText
        {
            get
            {
                switch (Source)
                {
                    case LengthScaleSource.Calibrated: return "自动标定";
                    case LengthScaleSource.Manual: return "手动指定";
                    case LengthScaleSource.Heuristic: return "兜底判断";
                    default: return "默认（毫米）";
                }
            }
        }

        internal string UnitText { get { return Scale >= 1000.0 ? "米" : "毫米"; } }
    }

    /// <summary>
    /// EC 长度属性的单位标定（开发指南 §17 结尾）。
    /// <para>
    /// OpenPlant_3D 的 EC 长度类属性是**裸 double**，没有 KindOfQuantity，
    /// 不同项目可能存米也可能存毫米，因此**不得假设都是毫米**。
    /// 本类移植自仓库已验证的 Python 实现
    /// （<c>管道信息查询/模块/管道信息/管道信息_读取.py</c> 的
    /// <c>detect_length_scale</c> / <c>guess_length_scale</c> / <c>resolve_length_unit</c>）。
    /// </para>
    /// <para>纯计算，无 Bentley 依赖，可离线断言。</para>
    /// </summary>
    internal static class LengthUnitCalibrator
    {
        internal const double ScaleMillimeter = 1.0;
        internal const double ScaleMeter = 1000.0;

        /// <summary>标定允许的相对误差：属性长度与几何长度本应一致，偏差过大说明标定不可信。</summary>
        internal const double CalibrationTolerance = 0.10;

        /// <summary>
        /// 用「属性长度 ↔ 几何长度」标定属性数值的存储单位。
        /// 两种候选单位都对不上（相对误差 &gt; 10%）时返回 <c>null</c>，
        /// 调用方应改用 <see cref="Guess"/>。
        /// </summary>
        internal static LengthScale Detect(double rawLength, double geometricLengthMm)
        {
            if (double.IsNaN(rawLength) || double.IsInfinity(rawLength)) return null;
            if (rawLength == 0.0 || geometricLengthMm <= 0.0) return null;

            double bestScale = ScaleMillimeter;
            double bestError = double.MaxValue;
            double[] candidates = { ScaleMillimeter, ScaleMeter };
            foreach (double scale in candidates)
            {
                double error = Math.Abs(rawLength * scale - geometricLengthMm) / geometricLengthMm;
                if (error < bestError)
                {
                    bestError = error;
                    bestScale = scale;
                }
            }

            if (bestError > CalibrationTolerance) return null;
            return new LengthScale(bestScale, LengthScaleSource.Calibrated, null);
        }

        /// <summary>
        /// 标定不成立时的兜底规则：绝对值 ≥ 1 视为毫米，否则视为米。
        /// 该规则对管径 / 壁厚 / 保温厚度都成立（工程上这些值不会小于 1 mm），
        /// 但对"用米存储的 DN1000 以上大管"会误判，因此必须把来源标成
        /// <see cref="LengthScaleSource.Heuristic"/> 并提示用户手动确认。
        /// </summary>
        internal static LengthScale Guess(double rawLength)
        {
            if (double.IsNaN(rawLength)) return new LengthScale(ScaleMillimeter, LengthScaleSource.Default, null);
            if (rawLength != 0.0 && Math.Abs(rawLength) < 1.0)
            {
                return new LengthScale(ScaleMeter, LengthScaleSource.Heuristic,
                    "无法用几何长度标定属性单位（属性长度与几何长度对不上），"
                    + "已按「数值 < 1 视为米」兜底，请在「属性单位」里手动确认。");
            }
            return new LengthScale(ScaleMillimeter, LengthScaleSource.Default, null);
        }

        /// <summary>
        /// 确定本元素长度类属性的换算比例。
        /// </summary>
        /// <param name="rawLength">EC 上 <c>LENGTH</c> 属性的原始数值。</param>
        /// <param name="geometricLengthMm">同一段管的几何长度（mm，由曲线算出，永远可信）。</param>
        /// <param name="overrideScale">
        /// 手动指定：<c>null</c> 或 <c>0</c> 表示自动；否则直接采用该比例（1.0 / 1000.0）。
        /// </param>
        internal static LengthScale Resolve(double rawLength, double geometricLengthMm,
            double? overrideScale)
        {
            if (overrideScale.HasValue && overrideScale.Value > 0.0)
            {
                double scale = overrideScale.Value >= 1000.0 ? ScaleMeter : ScaleMillimeter;
                return new LengthScale(scale, LengthScaleSource.Manual, null);
            }

            LengthScale calibrated = Detect(rawLength, geometricLengthMm);
            if (calibrated != null) return calibrated;

            LengthScale guessed = Guess(rawLength);
            if (guessed.Source == LengthScaleSource.Heuristic) return guessed;

            if (rawLength == 0.0)
            {
                return new LengthScale(guessed.Scale, guessed.Source,
                    "该元件没有可用的长度属性值（LENGTH），无法标定属性单位。");
            }

            // 走到这里说明：有长度属性值，但**标定失败**（属性长度与几何长度相对误差超过
            // CalibrationTolerance），且数值不小于 1 因而掉进了"按毫米"的默认分支。
            // 兜底规则本身是有意的（工程上管径 / 壁厚不会小于 1 mm），但**不能一声不吭**：
            // 如果本项目其实是按米存长度属性，外径就会被放大 1000 倍。
            // 上层（PipeElementReader.ResolveScale）还会拿外径 / 公称直径再兜一次，
            // 这里只负责把"标定没成立"这件事告诉用户。
            return new LengthScale(guessed.Scale, guessed.Source,
                string.Format(System.Globalization.CultureInfo.InvariantCulture,
                    "属性长度（{0:G}）与几何长度（{1:F3} mm）对不上（相对误差超过 {2:P0}），"
                    + "已按毫米处理；若本项目用米存储长度属性，请在「属性单位」里手动指定。",
                    rawLength, geometricLengthMm, CalibrationTolerance));
        }

        /// <summary>把属性原始数值换算成毫米。</summary>
        internal static double? ToMillimeter(double? rawValue, double scale)
        {
            if (!rawValue.HasValue) return null;
            double value = rawValue.Value;
            if (double.IsNaN(value) || double.IsInfinity(value)) return null;
            return value * scale;
        }

        /// <summary>解析 <c>"1715.7mm"</c> 这类"数值 + 单位"文本里的单位比例；识别不出返回 1.0（按毫米）。</summary>
        internal static double DetectTextUnitScale(string text)
        {
            if (string.IsNullOrEmpty(text)) return ScaleMillimeter;
            // 只认**紧跟在数字后面**的单位字母，避免把单词里的字母当成单位
            // （例如把 "unknown" 里的 m 当成米）。
            System.Text.RegularExpressions.Match match =
                System.Text.RegularExpressions.Regex.Match(text,
                    @"([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*([a-zA-Z]{0,3})");
            if (!match.Success) return ScaleMillimeter;
            switch (match.Groups[2].Value.ToLowerInvariant())
            {
                case "mm": return 1.0;
                case "cm": return 10.0;
                case "m": return 1000.0;
                case "km": return 1000000.0;
                case "in": return 25.4;
                case "ft": return 304.8;
                case "yd": return 914.4;
                default: return ScaleMillimeter;
            }
        }

        internal static string DescribeScale(double scale)
        {
            return scale.ToString("G", CultureInfo.InvariantCulture) + "×";
        }
    }
}
