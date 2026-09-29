using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using Bentley.DgnPlatformNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>Reuses the read-only EC snapshot and never retains Bentley EC instances.</summary>
    internal static class ElbowTrunnionReader
    {
        /// <summary>在活动模型里读取（兼容原有调用）。</summary>
        internal static ElbowTrunnionSelection Read(ulong id,ElbowOrientation orientation,
            TrunnionOrientation trunnion)
        {
            return Read(null,id,orientation,trunnion);
        }

        /// <summary>
        /// <paramref name="modelRef"/> 为元素所属的模型引用（参考文件里的弯头必须传，
        /// 见 <see cref="LocatedElement"/>）；null 表示活动模型。
        /// </summary>
        internal static ElbowTrunnionSelection Read(DgnModelRef modelRef,ulong id,
            ElbowOrientation orientation,TrunnionOrientation trunnion)
        {
            var snapshot=ComponentPropertyReader.Read(modelRef,id);
            var groups=new Dictionary<string,Dictionary<string,string>>(StringComparer.OrdinalIgnoreCase);
            foreach (var pair in snapshot.AllProperties)
            {
                int schemaEnd=pair.Key.IndexOf('.');
                if (schemaEnd<0) continue;
                int classEnd=pair.Key.IndexOf('.',schemaEnd+1);
                if (classEnd<0) continue;
                string key=pair.Key.Substring(0,classEnd);
                Dictionary<string,string> props;
                if (!groups.TryGetValue(key,out props))
                {
                    props=new Dictionary<string,string>(StringComparer.OrdinalIgnoreCase);
                    groups.Add(key,props);
                }
                props[pair.Key.Substring(classEnd+1)]=pair.Value;
            }
            string classKey=ElbowTrunnionCatalog.SelectElbowClass(groups);
            if (classKey==null)
                throw new InvalidOperationException("所选元素不是带 OpenPlant EC 属性的弯头。");
            var values=groups[classKey];
            double angle;
            if (TryNumber(values,"ANGLE",out angle))
            {
                if (Math.Abs(angle-90)>0.5)
                    throw new InvalidOperationException("当前只支持 90° 弯头。");
            }
            else if (classKey.IndexOf("90_DEGREE",StringComparison.OrdinalIgnoreCase)<0)
                throw new InvalidOperationException("无法确认弯头角度为 90°。");
            bool duct=classKey.IndexOf("HVAC",StringComparison.OrdinalIgnoreCase)>=0;
            if(duct && (classKey.IndexOf("RECT",StringComparison.OrdinalIgnoreCase)>=0 ||
                classKey.IndexOf("RECTANGULAR",StringComparison.OrdinalIgnoreCase)>=0))
                throw new InvalidOperationException("当前只支持圆形风管弯头 HVAC_ROUND_ELBOW，暂不支持矩形风管。");
            double diameter=duct
                ? Required(values,"OUTSIDE_DIAMETER","MAIN_DIAMETER","RUN_DIAMETER","EQUIVALENT_DIAMETER")
                : Required(values,"NOMINAL_DIAMETER","NOMINAL_DIAMETER_RUN_END");
            string unit=Text(values,"UNIT_OF_MEASURE");
            double factor=ElbowTrunnionCalculator.UnitScale(unit,diameter);
            double outside=(duct?diameter:Required(values,"OUTSIDE_DIAMETER"))*factor;
            if (outside<=0) throw new InvalidOperationException("弯头外径无效。");
            string dnNote="";
            int mainDn=duct ? ElbowTrunnionCatalog.DuctMainDn(outside,out dnNote)
                : ElbowTrunnionCatalog.MainDn(diameter*factor);
            string mainLabel=duct ? "D"+Math.Floor(outside+0.5).ToString("0",CultureInfo.InvariantCulture) : "";
            double run,outlet,length;
            bool hasLength=TryNumber(values,"LENGTH",out length);
            if (!TryNumber(values,"DESIGN_LENGTH_CENTER_TO_RUN_END",out run) &&
                !TryNumber(values,"DESIGN_LENGTH_CENTER_TO_RUN_END_EFFECTIVE",out run))
            {
                if(hasLength) run=length/2;
                else if(!duct || !TryNumber(values,"RADIUS",out run) || run<=0)
                    throw new InvalidOperationException(duct?"风管弯头缺少 RADIUS / 中心至端面长度。":"缺少 Run 端中心距。");
            }
            if (!TryNumber(values,"DESIGN_LENGTH_CENTER_TO_OUTLET_END",out outlet) &&
                !TryNumber(values,"DESIGN_LENGTH_CENTER_TO_OUTLET_END_EFFECTIVE",out outlet))
            {
                if(hasLength) outlet=length/2;
                else if(!duct || !TryNumber(values,"RADIUS",out outlet) || outlet<=0)
                    throw new InvalidOperationException(duct?"风管弯头缺少 RADIUS / 中心至端面长度。":"缺少 Outlet 端中心距。");
            }
            var matrix=new double[12];
            for(int i=0;i<12;i++)
                matrix[i]=Required(values,"TRANSFORMATION_MATRIX.M"+i.ToString("00",CultureInfo.InvariantCulture),
                    "M"+i.ToString("00",CultureInfo.InvariantCulture));
            var model=ComponentPropertyReader.ResolveModel(modelRef);
            if (model==null || !model.Is3d) throw new InvalidOperationException("请在三维 DGN 模型中点选弯头。");
            var frame=ElbowTrunnionCalculator.Frame(matrix,model.GetModelInfo().UorPerMeter/1000,
                run*factor,outlet*factor,orientation,
                orientation==ElbowOrientation.Vertical && trunnion==TrunnionOrientation.Horizontal);
            string pipeNumber=Text(values,"LINENUMBER");
            if (string.IsNullOrWhiteSpace(pipeNumber))
                pipeNumber=snapshot.AllProperties.FirstOrDefault(v=>v.Key.StartsWith("OpenPlant",StringComparison.OrdinalIgnoreCase)
                    && v.Key.EndsWith(".LINENUMBER",StringComparison.OrdinalIgnoreCase)).Value;
            return new ElbowTrunnionSelection { ElementId=id,ClassName=classKey,
                MainDn=mainDn,MainSizeLabel=mainLabel,MainDnNote=dnNote,
                OutsideDiameterMm=outside,Frame=frame,
                PipeNumber=pipeNumber };
        }
        private static double Required(IDictionary<string,string> values,params string[] names)
        {
            double result;
            foreach(string name in names)
                if (TryNumber(values,name,out result)) return result;
            throw new InvalidOperationException("弯头缺少 EC 数值：" + string.Join(" / ",names) + "。");
        }
        private static bool TryNumber(IDictionary<string,string> values,string name,out double result)
        {
            string value=Text(values,name);
            return double.TryParse(value,NumberStyles.Float,CultureInfo.InvariantCulture,out result)
                && !double.IsNaN(result) && !double.IsInfinity(result);
        }
        private static string Text(IDictionary<string,string> values,string name)
        {
            string value;
            if (values.TryGetValue(name,out value)) return value;
            foreach(var pair in values)
                if (pair.Key.EndsWith("."+name,StringComparison.OrdinalIgnoreCase)) return pair.Value;
            return null;
        }
    }
}


