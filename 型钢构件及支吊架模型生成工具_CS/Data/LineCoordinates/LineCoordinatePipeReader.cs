using System;
using Bentley.DgnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 把点选的管道读成 <see cref="LinePipeSurvey"/> 纯数据（毫米，活动模型坐标）。
    /// 复用管道对齐模块已验证的 <c>PipeElementReader</c> EC 读取管线：
    /// 查询、遍历、取值全部留在那一层内完成，本类只做单位与字段映射；
    /// 读不到轴线或外径就明确拒绝，不猜测。
    /// </summary>
    internal static class LineCoordinatePipeReader
    {
        internal static LinePipeSurvey Read(LocatedElement located)
        {
            if (located == null || located.ModelRef == null) throw new InvalidOperationException("没有选中的管道。");
            if (LocatedElement.IsReference(located.ModelRef))
                throw new InvalidOperationException("参考文件中的管道不能作为对齐来源，请选择活动模型中的管道。");
            var model = located.ModelRef.GetDgnModel();
            double uorPerMm = model.GetModelInfo().UorPerMeter / 1000.0;
            if (!LineCoordinateCalculator.Finite(uorPerMm) || uorPerMm <= 0)
                throw new InvalidOperationException("模型单位无效。");
            // 只读标高用途：不探测连接关系与移动能力，给空 probe 与空日志。
            var pipe = PipeAlignment.PipeElementReader.Read(located.ModelRef, located.ElementId,
                new PipeAlignment.PipeReadOptions(), null, null);
            if (pipe == null || pipe.Axis == null)
                throw new InvalidOperationException("未能读取所选管道的轴线，请选择一根 OpenPlant 管道。");
            if (!pipe.OutsideDiameterMm.HasValue || !(pipe.OutsideDiameterMm.Value > 0)
                || !LineCoordinateCalculator.Finite(pipe.OutsideDiameterMm.Value))
                throw new InvalidOperationException("未能读取所选管道的外径，无法确定管底标高。");
            var survey = new LinePipeSurvey
            {
                AxisStartX = pipe.Axis.StartXmm,
                AxisStartY = pipe.Axis.StartYmm,
                AxisStartZ = pipe.Axis.StartZmm,
                AxisEndX = pipe.Axis.EndXmm,
                AxisEndY = pipe.Axis.EndYmm,
                AxisEndZ = pipe.Axis.EndZmm,
                OutsideDiameterMm = pipe.OutsideDiameterMm.Value,
                PipeNumber = pipe.PipeNumber
            };
            // 点取位置来自按钮事件的活动模型坐标（UOR）；参考管道已在上方拒绝。
            survey.PickX = located.ClickX / uorPerMm;
            survey.PickY = located.ClickY / uorPerMm;
            survey.PickZ = located.ClickZ / uorPerMm;
            return survey;
        }
    }
}
