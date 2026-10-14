using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
namespace SteelSectionProbe
{
    internal static class MagneticGaugeBuilder
    {
        internal static Element Build(MagneticGaugePlan plan,DPoint3d origin)
        {
            if(plan==null)throw new ArgumentNullException("plan");
            if(!Finite(origin.X)||!Finite(origin.Y)||!Finite(origin.Z))throw new InvalidOperationException("液位计放置点无效。");
            var model=Session.Instance.GetActiveDgnModel();if(model==null||!model.Is3d)throw new InvalidOperationException("磁翻板液位计需要三维活动模型。");
            double scale=model.GetModelInfo().UorPerMeter/1000;if(!Finite(scale)||scale<=0)throw new InvalidOperationException("模型长度单位无效。");
            var colors=new Dictionary<MagneticGaugeColor,uint>();
            foreach(MagneticGaugeColor color in Enum.GetValues(typeof(MagneticGaugeColor)))
            {var rgb=MagneticGaugeCatalog.Rgb(color);colors[color]=DgnColorMap.CreateElementColor(new RgbColorDef((byte)rgb[0],(byte)rgb[1],(byte)rgb[2]),null,null,Session.Instance.GetActiveDgnFile());}
            var children=new List<Element>();
            for(int index=0;index<plan.Parts.Length;index++)
            {
                var p=plan.Parts[index];
                try
                {
                    Element element;
                    if(p.Kind==MagneticGaugeKind.Cylinder)element=SolidPrimitiveFactory.Element(SolidPrimitiveFactory.Cylinder(P(p.Start),P(p.End),p.RadiusMm*scale),colors[p.Color]);
                    else if(p.Kind==MagneticGaugeKind.Box)
                    {
                        var a=p.Start;var s=p.Size;
                        var body=SolidPrimitiveFactory.PolygonPrism(new[]{P(a),P(new MagneticGaugePoint(a.X+s.X,a.Y,a.Z)),P(new MagneticGaugePoint(a.X+s.X,a.Y+s.Y,a.Z)),P(new MagneticGaugePoint(a.X,a.Y+s.Y,a.Z))},new DVector3d(0,0,s.Z*scale));
                        element=SolidPrimitiveFactory.Element(body,colors[p.Color]);
                    }
                    else
                    {
                        // Native analytic torus: circular cross-section swept around a true full circle, no tessellated path.
                        var torus=SolidPrimitive.CreateDgnTorusPipe(new DgnTorusPipeDetail(P(p.Start),new DVector3d(1,0,0),new DVector3d(0,1,0),p.RadiusMm*scale,p.TubeRadiusMm*scale,2*Math.PI,true));
                        element=DraftingElementSchema.ToElement(model,torus,null);if(element==null)throw new InvalidOperationException("环形手轮生成失败。");
                        var setter=new ElementPropertiesSetter();setter.SetColor(colors[p.Color]);if(!setter.Apply(element))throw new InvalidOperationException("手轮颜色设置失败。");
                    }
                    children.Add(element);
                }
                catch(Exception ex){throw new InvalidOperationException("液位计第"+(index+1)+"个"+p.Kind+"构件生成失败："+ex.Message,ex);}
            }
            var cell=new CellHeaderElement(model,plan.CellName,DPoint3d.Zero,DMatrix3d.Identity,children);
            var rotation=DTransform3d.Rotation(2,Angle.FromRadians(plan.Parameters.HeadingDegrees*Math.PI/180));
            cell.ApplyTransform(new TransformInfo(DTransform3d.Multiply(DTransform3d.FromTranslation(origin),rotation)));
            return cell;
            DPoint3d P(MagneticGaugePoint p){return new DPoint3d(p.X*scale,p.Y*scale,p.Z*scale);}
        }
        private static bool Finite(double v){return !double.IsNaN(v)&&!double.IsInfinity(v);}
    }
}
