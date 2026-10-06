using System;

namespace PipeAlign
{
    /// <summary>
    /// 毫米 ↔ UOR 换算（开发指南 §17）。
    /// <para>
    /// 构造时只接收一个"每毫米多少 UOR"的数值，**自己不碰 Bentley API** ——
    /// 读模型信息由 <c>Data/DgnUnitServiceFactory</c> 负责。这样本类可以在离线自检
    /// 工程里直接断言，也保证全工程只有这一处 UOR 换算。
    /// </para>
    /// </summary>
    internal sealed class UnitService : IUnitService
    {
        private readonly double _uorPerMillimeter;

        /// <param name="uorPerMillimeter">
        /// 每毫米对应的 UOR 数。必须为正的有限数，否则视为不可用。
        /// 注意：本仓库其它插件用 <c>GetModelInfo().UorPerMeter / 1000.0</c> 得到它，
        /// 而 Python 版用 <c>GetUorPerStorage()</c>；两者在公制模型下一致，
        /// 但 C# 侧统一走 <c>UorPerMeter</c> 这条已验证路径。
        /// </param>
        internal UnitService(double uorPerMillimeter)
        {
            _uorPerMillimeter = uorPerMillimeter;
        }

        internal static UnitService Unavailable()
        {
            return new UnitService(0.0);
        }

        public bool IsAvailable
        {
            get
            {
                return _uorPerMillimeter > 0.0
                    && !double.IsNaN(_uorPerMillimeter)
                    && !double.IsInfinity(_uorPerMillimeter);
            }
        }

        public double UorPerMillimeter { get { return _uorPerMillimeter; } }

        public double UorToMillimeter(double value)
        {
            if (!IsAvailable) throw new InvalidOperationException("单位服务不可用：取不到当前模型的主单位换算系数。");
            return value / _uorPerMillimeter;
        }

        public double MillimeterToUor(double value)
        {
            if (!IsAvailable) throw new InvalidOperationException("单位服务不可用：取不到当前模型的主单位换算系数。");
            return value * _uorPerMillimeter;
        }
    }
}
