namespace SteelSectionProbe
{
    /// <summary>管夹类功能共用的所选元素快照：轴线、点击点、公称直径、保温厚度与管道号。</summary>
    internal sealed class PipeClampSelection
    {
        internal ulong ElementId;
        internal double StartX,StartY,StartZ,EndX,EndY,EndZ,ClickX,ClickY,ClickZ;
        /// <summary>是否识别为 OpenPlant 管道（否则按普通直线 / 多段线处理）。</summary>
        internal bool IsPipe;
        internal bool IsAuxiliaryLine;
        /// <summary>所选元素是否来自参考文件（reference）。</summary>
        internal bool IsFromReference;
        /// <summary>轴线相关的提示（如"已按元素范围最长边近似管轴"）；无提示时为空。</summary>
        internal string AxisNote="";
        internal double? NominalMm,OutsideMm,InsulationMm;
        internal string PipeNumber="";
        // Native identity and model units captured when picking; never derive these from a reference's temporary line.
        internal string NativePipeInstanceId;
        internal long NativeModelToken;
        internal double SourceUorPerMm;

        internal double AxisX { get { return EndX-StartX; } }
        internal double AxisY { get { return EndY-StartY; } }
        internal double AxisZ { get { return EndZ-StartZ; } }

        /// <summary>点击点在轴线上的三维投影（毫米），截断至两端点。</summary>
        internal double[] ProjectedCenter()
        {
            double dx=AxisX,dy=AxisY,dz=AxisZ;
            double lengthSquared=dx*dx+dy*dy+dz*dz;
            if(lengthSquared<=1.0e-12) return new[]{StartX,StartY,StartZ};
            double t=((ClickX-StartX)*dx+(ClickY-StartY)*dy+(ClickZ-StartZ)*dz)/lengthSquared;
            if(t<0.0) t=0.0; else if(t>1.0) t=1.0;
            return new[]{StartX+t*dx,StartY+t*dy,StartZ+t*dz};
        }
    }

}
