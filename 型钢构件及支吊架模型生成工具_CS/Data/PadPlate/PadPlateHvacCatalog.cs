using System;
using System.Collections.Generic;
using System.Globalization;

namespace SteelSectionProbe
{
    /// <summary>从所选直风管的 EC 快照识别 HVAC 圆风管及实际外径；纯数据，不触碰模型。</summary>
    internal static class PadPlateHvacCatalog
    {
        internal static PadPlateHvacDuct Resolve(IEnumerable<KeyValuePair<string,string>> properties)
        {
            bool hvac=false,round=false,rect=false,elbow=false;
            var values=new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase);
            if(properties==null)return null;
            foreach(var pair in properties)
            {
                int first=pair.Key.IndexOf('.');if(first<0)continue;
                int second=pair.Key.IndexOf('.',first+1);if(second<0)continue;
                string className=pair.Key.Substring(first+1,second-first-1);
                if(className.IndexOf("HVAC",StringComparison.OrdinalIgnoreCase)<0)continue;
                hvac=true;
                if(className.IndexOf("ELBOW",StringComparison.OrdinalIgnoreCase)>=0)elbow=true;
                if(className.IndexOf("RECT",StringComparison.OrdinalIgnoreCase)>=0)rect=true;
                if(className.IndexOf("ROUND",StringComparison.OrdinalIgnoreCase)>=0)round=true;
                string property=pair.Key.Substring(second+1);
                if(!values.ContainsKey(property))values.Add(property,pair.Value);
            }
            if(!hvac)return null;
            if(elbow)throw new InvalidOperationException("Y2 请点选 HVAC 直风管；弯头请切换到弯头垫板。");
            if(rect||!round)throw new InvalidOperationException("Y2 当前只支持 HVAC 圆形直风管。");
            double raw=0;bool found=false;
            foreach(string name in new[]{"OUTSIDE_DIAMETER","MAIN_DIAMETER","RUN_DIAMETER","EQUIVALENT_DIAMETER"})
            {
                string value;double parsed;
                if(values.TryGetValue(name,out value)&&double.TryParse(value,NumberStyles.Float,
                    CultureInfo.InvariantCulture,out parsed)&&Finite(parsed)&&parsed>0)
                {raw=parsed;found=true;break;}
            }
            if(!found)throw new InvalidOperationException("圆风管缺少实际外径：OUTSIDE_DIAMETER / MAIN_DIAMETER / RUN_DIAMETER。");
            string unit;values.TryGetValue("UNIT_OF_MEASURE",out unit);
            double od=raw*UnitScale(unit,raw);
            if(!Finite(od)||od<=0)throw new InvalidOperationException("风管实际外径无效。");
            return new PadPlateHvacDuct{OutsideMm=od,
                SizeLabel="D"+Math.Floor(od+0.5).ToString("0",CultureInfo.InvariantCulture)};
        }
        private static double UnitScale(string raw,double diameter)
        {
            string unit=(raw??"").Trim().ToUpperInvariant();
            if(unit=="MM"||unit=="MILLIMETER"||unit=="MILLIMETRE"||unit=="毫米")return 1;
            if(unit=="M"||unit=="METER"||unit=="METRE"||unit=="米")return 1000;
            if(unit=="IN"||unit=="INCH"||unit=="INCHES")return 25.4;
            return diameter>0&&diameter<2?1000:1;
        }
        private static bool Finite(double value){return !double.IsNaN(value)&&!double.IsInfinity(value);}
    }
}
