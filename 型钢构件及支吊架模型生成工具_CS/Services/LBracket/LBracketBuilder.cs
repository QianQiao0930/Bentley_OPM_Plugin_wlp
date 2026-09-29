using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal static class LBracketBuilder
    {
        internal static IList<Element> Build(LBracketPlan plan)
        {
            if(plan==null)throw new InvalidOperationException("D7 计划为空。");
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null||!model.Is3d)throw new InvalidOperationException("D7 需要三维活动模型。");
            var s=plan.Selection;var v=plan.Variant;
            double scale=model.GetModelInfo().UorPerMeter/1000.0;
            var u=new DVector3d(s.RunX,s.RunY,0);
            var side=new DVector3d(-s.RunY,s.RunX,0);
            var up=new DVector3d(0,0,1);
            var minusU=new DVector3d(-s.RunX,-s.RunY,0);
            var minusSide=new DVector3d(s.RunY,-s.RunX,0);
            var down=new DVector3d(0,0,-1);
            Func<double,double,double,DPoint3d> point=(x,y,z)=>new DPoint3d(
                (s.Corner.X+x*s.RunX-y*s.RunY)*scale,
                (s.Corner.Y+x*s.RunY+y*s.RunX)*scale,(s.Corner.Z+z)*scale);
            bool hanger=plan.Parameters.Type>=3;
            string postMode=v.Family=="equal_angle"?"outer_corner":
                v.Family=="parallel_channel"?"lower_left":"geometric_center";
            string armMode=postMode;
            var post=ProfileLookup.Mode(RuntimeData.Families,v.Family,v.Profile,postMode);
            var arm=ProfileLookup.Mode(RuntimeData.Families,v.Family,v.Profile,armMode);
            double h=s.HeightMm,l=s.LengthMm;
            DPoint3d postOrigin,armOrigin;
            DVector3d px,py,pz,ax,ay,az;
            if(v.Family=="equal_angle")
            {
                double z0=v.CentroidMm;
                postOrigin=hanger?point(-z0,-z0,h):point(-z0,-z0,-h);
                px=u;py=hanger?minusSide:side;pz=hanger?down:up;
                armOrigin=point(l,-z0-v.ThicknessMm,0);
                ax=side;ay=down;az=minusU;
            }
            else if(v.Family=="parallel_channel")
            {
                postOrigin=point(-v.HeightMm/2,0,hanger?-v.HeightMm:-h);
                px=minusSide;py=u;pz=up;
                armOrigin=point(l,0,0);ax=side;ay=down;az=minusU;
            }
            else
            {
                postOrigin=point(0,0,hanger?0:-h);
                px=minusSide;py=u;pz=up;
                armOrigin=point(-v.HeightMm/2-15,0,-v.HeightMm/2);
                ax=side;ay=up;az=u;
            }
            return new[]{
                SteelMemberFactory.AlongAxis(post,postOrigin,scale,px,py,pz,
                    plan.PostCutLengthMm,7),
                SteelMemberFactory.AlongAxis(arm,armOrigin,scale,ax,ay,az,
                    plan.ArmCutLengthMm,7)};
        }
    }
}
