using System;
using System.Globalization;
using Bentley.DgnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 管夹类功能共用的元素读取：轴线与管道判定复用 <see cref="E1GuideReader"/>，
    /// 这里补上公称直径、外径与保温厚度（EC 属性 <c>INSULATION_THICKNESS</c>）。
    /// 单位沿用与 E1 相同的规则：值在 (0,1) 区间时按米计，乘 1000 转毫米。
    /// </summary>
    internal static class PipeClampReader
    {
        internal static PipeClampSelection Read(ulong id,double clickXUor,double clickYUor,
            double clickZUor)
        {
            return Read(null,id,clickXUor,clickYUor,clickZUor);
        }

        /// <summary>
        /// 读取所选元素。<paramref name="modelRef"/> 为元素所属的模型引用
        /// （参考文件里的元素必须传，见 <see cref="LocatedElement"/>）；null 表示活动模型。
        /// </summary>
        internal static PipeClampSelection Read(DgnModelRef modelRef,ulong id,double clickXUor,
            double clickYUor,double clickZUor)
        {
            var axis=E1GuideReader.Read(modelRef,id,clickXUor,clickYUor,clickZUor);
            var snapshot=ComponentPropertyReader.Read(modelRef,id);
            return new PipeClampSelection {
                ElementId=axis.ElementId,
                StartX=axis.StartX,StartY=axis.StartY,StartZ=axis.StartZ,
                EndX=axis.EndX,EndY=axis.EndY,EndZ=axis.EndZ,
                ClickX=axis.ClickX,ClickY=axis.ClickY,ClickZ=axis.ClickZ,
                IsPipe=axis.IsPipe,IsAuxiliaryLine=axis.IsAuxiliaryLine,
                IsFromReference=axis.IsFromReference,
                AxisNote=axis.AxisNote??"",
                PipeNumber=axis.PipeNumber??"",
                NominalMm=Number(snapshot,"NOMINAL_DIAMETER"),
                OutsideMm=Number(snapshot,"OUTSIDE_DIAMETER"),
                InsulationMm=Number(snapshot,"INSULATION_THICKNESS")
            };
        }

        private static double? Number(ComponentSnapshot snapshot,string name)
        {
            if(snapshot==null || snapshot.Properties==null) return null;
            string raw;
            if(!snapshot.Properties.TryGetValue(name,out raw) || string.IsNullOrWhiteSpace(raw))
                return null;
            double value;
            if(!double.TryParse(raw,NumberStyles.Float,CultureInfo.InvariantCulture,out value))
                return null;
            if(double.IsNaN(value) || double.IsInfinity(value)) return null;
            if(value>0.0 && value<1.0) value*=1000.0;
            return value;
        }
    }
}
