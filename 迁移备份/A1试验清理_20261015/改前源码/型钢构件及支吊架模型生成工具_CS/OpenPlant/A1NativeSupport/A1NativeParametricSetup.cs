using System;

namespace SteelSectionProbe
{
    public sealed partial class A1NativeParametricComponent
    {
        private A1ClampPlan plan;

        // BMECObject.Init invokes Setup from its constructor, BEFORE the writer can bind RelatedInstance.
        // This phase may read intrinsic parameters, but must not require the host pipe or its ports.
        public override void Setup()
        {
            try
            {
                int dn = BMECObject.GetIntValue("SSP_A1_DN");
                double angle = BMECObject.GetUnitlessDoubleValue("SSP_A1_OPENING");
                plan = A1ClampCalculator.Calculate(dn, false, null, angle, "");
            }
            catch (Exception error)
            {
                SaveTrace(DateTimeOffset.Now.ToString("o") + " A1组件Setup失败\r\n" + error);
                throw;
            }
        }

        internal void PrepareGraphics()
        {
            Setup();
            // By Create3DElements the writer has bound the pipe; retain strict validation here.
            if (!SetPipeDiameter()) throw new InvalidOperationException("A1原生组件生成几何时无法初始化父管及端口数据。");
            SetSupportLength(plan.Row.D);
        }
    }
}
