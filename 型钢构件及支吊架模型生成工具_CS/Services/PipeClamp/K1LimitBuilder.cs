using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// K1 不保温管限位架建模：两组一前一后的限位块（子项 A 为半片 T 形竖直放置，
    /// 子项 B/C 为完整 H 型钢沿管轴水平放置）+ 底板。与 Python
    /// <c>K1-[不保温管的限位架].py</c> 的 <c>_build_k1_cell</c> 逐项对齐。
    /// 尺寸为毫米，只有建元素时转 UOR。
    /// </summary>
    internal static class K1LimitBuilder
    {
        internal static List<Element> Build(K1LimitPlan plan,DPoint3d center,DVector3d axis)
        {
            if(plan==null) throw new ArgumentNullException("plan");
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null || !model.Is3d)
                throw new InvalidOperationException("K1 限位架需要在三维 DGN 模型中放置。");
            double scale=model.GetModelInfo().UorPerMeter/1000.0;
            double[] pipeDir,perp;
            K1LimitCalculator.HorizontalFrame(axis.X,axis.Y,axis.Z,out pipeDir,out perp);
            var centerMm=new[]{center.X/scale,center.Y/scale,center.Z/scale};
            var item=K1LimitCatalog.Require(plan.SubitemKey);
            var result=new List<Element>();
            var mode=item.IsHalfT?HalfTMode(item):ProfileMode(item);

            foreach(int side in new[]{1,-1})
            {
                double[] originMm,axisX,axisY,axisZ;
                double length;
                K1LimitCalculator.MemberFrame(item,side,centerMm,plan.ExistingWidthMm,
                    plan.OutsideMm,pipeDir,out originMm,out axisX,out axisY,out axisZ,out length);
                var origin=new DPoint3d(originMm[0]*scale,originMm[1]*scale,originMm[2]*scale);
                result.Add(SteelMemberFactory.AlongAxis(mode,origin,scale,
                    new DVector3d(axisX[0],axisX[1],axisX[2]),
                    new DVector3d(axisY[0],axisY[1],axisY[2]),
                    new DVector3d(axisZ[0],axisZ[1],axisZ[2]),
                    length,K1LimitCatalog.BlockColor));

                var box=K1LimitCalculator.PlateBox(item,side,centerMm,plan.ExistingWidthMm,
                    plan.OutsideMm,pipeDir);
                if(box!=null) result.Add(Plate(center,scale,pipeDir,box));
            }
            return result;
        }

        /// <summary>底板：矩形截面在水平面内，沿竖直方向拉伸。</summary>
        private static Element Plate(DPoint3d center,double scale,double[] pipeDir,double[] box)
        {
            var frame=new PipeClampFrame(center,scale,pipeDir[0],pipeDir[1],pipeDir[2]);
            var points=new[]{ frame.Point(box[0],box[2],box[4]),frame.Point(box[1],box[2],box[4]),
                frame.Point(box[1],box[3],box[4]),frame.Point(box[0],box[3],box[4]) };
            return SolidPrimitiveFactory.Element(SolidPrimitiveFactory.PolygonPrism(points,
                frame.Direction(0.0,0.0,box[5]-box[4])),K1LimitCatalog.PlateColor);
        }

        /// <summary>子项 A 的半片 T 形截面：取自 H100×100×6×8 沿腹板高度中点剖开的一半，
        /// 翼缘 100×8 + 腹板 6×42，总深 50。局部原点 = 翼缘外侧面中点，腹板沿 +x。</summary>
        private static ModeData HalfTMode(K1LimitSubitem item)
        {
            double ft=item.TFlangeThicknessMm;
            double fw=item.TFlangeWidthMm;
            double wt=item.TWebThicknessMm;
            double wl=item.TWebLengthMm;
            double halfFlange=fw/2.0;
            double halfWeb=wt/2.0;
            var corners=new[]{
                new[]{0.0,-halfFlange},new[]{0.0,halfFlange},
                new[]{ft,halfFlange},new[]{ft,halfWeb},
                new[]{ft+wl,halfWeb},new[]{ft+wl,-halfWeb},
                new[]{ft,-halfWeb},new[]{ft,-halfFlange}};
            var segments=new SegmentData[corners.Length];
            for(int index=0;index<corners.Length;index++)
            {
                var a=corners[index];
                var b=corners[(index+1)%corners.Length];
                segments[index]=new SegmentData {IsArc=false,X0=a[0],Y0=a[1],X1=b[0],Y1=b[1]};
            }
            return new ModeData {Id="k1_half_t",Label="半片T形",Segments=segments};
        }

        private static ModeData ProfileMode(K1LimitSubitem item)
        {
            return ProfileLookup.Mode(RuntimeData.Families,item.FamilyId,item.ProfileName,
                item.ModeId);
        }
    }
}
