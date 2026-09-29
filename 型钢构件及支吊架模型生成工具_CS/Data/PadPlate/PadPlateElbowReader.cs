using System;
using System.Collections.Generic;
using System.Globalization;
using Bentley.DgnPlatformNET;

namespace SteelSectionProbe
{
    internal static class PadPlateElbowReader
    {
        internal static PadPlateElbow Read(DgnModelRef modelRef,ulong id)
        {
            var snapshot=ComponentPropertyReader.Read(modelRef,id);
            var groups=new Dictionary<string,Dictionary<string,string>>(StringComparer.OrdinalIgnoreCase);
            foreach(var pair in snapshot.AllProperties)
            {
                int first=pair.Key.IndexOf('.');if(first<0)continue;
                int second=pair.Key.IndexOf('.',first+1);if(second<0)continue;
                string key=pair.Key.Substring(0,second);
                Dictionary<string,string> props;
                if(!groups.TryGetValue(key,out props))
                {props=new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase);groups.Add(key,props);}
                props[pair.Key.Substring(second+1)]=pair.Value;
            }
            string keyName=ElbowTrunnionCatalog.SelectElbowClass(groups);
            if(keyName==null)throw new InvalidOperationException("所选元素不是 OpenPlant 弯头。");
            var values=groups[keyName];double angle;
            if(Try(values,"ANGLE",out angle))
            {if(Math.Abs(angle-90)>0.5)throw new InvalidOperationException("只支持 90° 弯头。");}
            else if(keyName.IndexOf("90_DEGREE",StringComparison.OrdinalIgnoreCase)<0)
                throw new InvalidOperationException("无法确认所选弯头为 90°。");
            bool duct=keyName.IndexOf("HVAC",StringComparison.OrdinalIgnoreCase)>=0;
            if(duct&&(keyName.IndexOf("RECT",StringComparison.OrdinalIgnoreCase)>=0))
                throw new InvalidOperationException("只支持圆形风管弯头。");
            double nominal=duct?Required(values,"OUTSIDE_DIAMETER","MAIN_DIAMETER","RUN_DIAMETER","EQUIVALENT_DIAMETER"):
                Required(values,"NOMINAL_DIAMETER","NOMINAL_DIAMETER_RUN_END");
            double factor=ElbowTrunnionCalculator.UnitScale(Text(values,"UNIT_OF_MEASURE"),nominal);
            double od=(duct?nominal:Required(values,"OUTSIDE_DIAMETER"))*factor;
            if(od<=0)throw new InvalidOperationException("弯头外径无效。");
            double run,outlet,length,radius;
            bool hasLength=Try(values,"LENGTH",out length);
            if(duct&&Try(values,"RADIUS",out radius)&&radius>0)
            {run=radius;outlet=radius;}
            else
            {
                if(!Try(values,"DESIGN_LENGTH_CENTER_TO_RUN_END",out run)&&
                    !Try(values,"DESIGN_LENGTH_CENTER_TO_RUN_END_EFFECTIVE",out run))
                {if(hasLength)run=length/2;else throw new InvalidOperationException("弯头缺少中心至端面长度。");}
                if(!Try(values,"DESIGN_LENGTH_CENTER_TO_OUTLET_END",out outlet)&&
                    !Try(values,"DESIGN_LENGTH_CENTER_TO_OUTLET_END_EFFECTIVE",out outlet))
                {if(hasLength)outlet=length/2;else throw new InvalidOperationException("弯头缺少中心至端面长度。");}
            }
            run*=factor;outlet*=factor;
            if(run<=0||outlet<=0||Math.Abs(run-outlet)>Math.Max(run,outlet)*0.02)
                throw new InvalidOperationException("只支持两端中心距一致的标准 90° 弯头。");
            var m=new double[12];for(int i=0;i<12;i++)m[i]=Required(values,
                "TRANSFORMATION_MATRIX.M"+i.ToString("00",CultureInfo.InvariantCulture),
                "M"+i.ToString("00",CultureInfo.InvariantCulture));
            var model=ComponentPropertyReader.ResolveModel(modelRef);
            if(model==null||!model.Is3d)throw new InvalidOperationException("请在三维模型中点选弯头。");
            double uor=model.GetModelInfo().UorPerMeter/1000;
            var x=new VectorMm(m[0],m[4],m[8]).Unit();
            var z=new VectorMm(m[2],m[6],m[10]).Unit();
            if(Math.Abs(x.Dot(z))>0.02)throw new InvalidOperationException("弯头局部 X/Z 轴不正交。");
            var origin=new VectorMm(m[3]/uor,m[7]/uor,m[11]/uor);
            return new PadPlateElbow{IsDuct=duct,Dn=duct?(int?)null:PadPlateCatalog.MatchDn(nominal*factor),
                OutsideMm=od,CenterToEndMm=(run+outlet)/2,
                SizeLabel=duct?"D"+Math.Floor(od+0.5).ToString("0",CultureInfo.InvariantCulture):"",
                PipeNumber=Text(values,"LINENUMBER")??"",Origin=origin,AxisX=x,AxisZ=z};
        }
        private static double Required(IDictionary<string,string> values,params string[] names)
        {double result;foreach(string name in names)if(Try(values,name,out result))return result;
            throw new InvalidOperationException("弯头缺少 EC 数值："+string.Join(" / ",names)+"。");}
        private static bool Try(IDictionary<string,string> values,string name,out double result)
        {return double.TryParse(Text(values,name),NumberStyles.Float,CultureInfo.InvariantCulture,out result)&&
            !double.IsNaN(result)&&!double.IsInfinity(result);}
        private static string Text(IDictionary<string,string> values,string name)
        {string value;if(values.TryGetValue(name,out value))return value;
            foreach(var pair in values)if(pair.Key.EndsWith("."+name,StringComparison.OrdinalIgnoreCase))return pair.Value;
            return null;}
    }
}
