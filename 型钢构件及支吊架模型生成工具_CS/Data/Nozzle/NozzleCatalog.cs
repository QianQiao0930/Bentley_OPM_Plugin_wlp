using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Web.Script.Serialization;

namespace SteelSectionProbe
{
    internal static class NozzleCatalog
    {
        private sealed class CatalogData
        {
            internal Dictionary<string,Dictionary<int,NozzleSize>> Ratings;
            internal Dictionary<string,Dictionary<int,NozzleSize>> Schedules;
        }
        private static readonly Lazy<CatalogData> cache=new Lazy<CatalogData>(Load);
        internal static string[] Ratings { get { return cache.Value.Ratings.Keys.OrderBy(x=>x,StringComparer.Ordinal).ToArray(); } }
        internal static string[] Schedules { get { return cache.Value.Schedules.Keys.OrderByDescending(x=>x=="Ia_Sch10").ThenBy(x=>x,StringComparer.Ordinal).ToArray(); } }
        internal static int[] AvailableDns(string rating,string schedule)
        {
            Dictionary<int,NozzleSize> flanges,pipes;
            if(!cache.Value.Ratings.TryGetValue(rating??"",out flanges) ||
                !cache.Value.Schedules.TryGetValue(schedule??"",out pipes)) return new int[0];
            return flanges.Keys.Where(dn=>pipes.ContainsKey(dn) &&
                Math.Abs(flanges[dn].PipeOutsideMm-pipes[dn].PipeOutsideMm)<=.01)
                .OrderBy(dn=>dn).ToArray();
        }
        internal static NozzleSize Get(string rating,string schedule,int dn)
        {
            Dictionary<int,NozzleSize> flanges,pipes;
            NozzleSize flange,pipe;
            if(!cache.Value.Ratings.TryGetValue(rating??"",out flanges) ||
                !cache.Value.Schedules.TryGetValue(schedule??"",out pipes) ||
                !flanges.TryGetValue(dn,out flange) || !pipes.TryGetValue(dn,out pipe))
                throw new InvalidOperationException("尺寸表中没有 "+rating+" / "+schedule+" / DN"+dn+"。");
            if(Math.Abs(flange.PipeOutsideMm-pipe.PipeOutsideMm)>.01)
                throw new InvalidOperationException("法兰与钢管外径不一致。");
            return new NozzleSize { NominalDn=dn,Rating=rating,PipeSchedule=schedule,
                PipeOutsideMm=flange.PipeOutsideMm,PipeWallMm=pipe.PipeWallMm,
                FlangeOutsideMm=flange.FlangeOutsideMm,FlangeThicknessMm=flange.FlangeThicknessMm,
                BoltCircleMm=flange.BoltCircleMm,BoltHoleMm=flange.BoltHoleMm,
                BoltCount=flange.BoltCount,BoltSize=flange.BoltSize,
                RaisedFaceOutsideMm=flange.RaisedFaceOutsideMm,RaisedFaceHeightMm=flange.RaisedFaceHeightMm };
        }
        private static CatalogData Load()
        {
            const string resource="SteelSectionProbe.nozzle_flange_data.json";
            using(var stream=Assembly.GetExecutingAssembly().GetManifestResourceStream(resource))
            {
                if(stream==null) throw new InvalidOperationException("缺少嵌入的管口尺寸表："+resource);
                string json;
                using(var reader=new StreamReader(stream,Encoding.UTF8)) json=reader.ReadToEnd();
                var root=Map(new JavaScriptSerializer { MaxJsonLength=int.MaxValue }.DeserializeObject(json));
                var result=new CatalogData {
                    Ratings=ReadGroups(Map(root["ratings"]),true),
                    Schedules=ReadGroups(Map(root["pipe_schedules"]),false) };
                if(result.Ratings.Count==0 || result.Schedules.Count==0)
                    throw new InvalidOperationException("管口尺寸表缺少法兰或钢管系列。");
                return result;
            }
        }
        private static Dictionary<string,Dictionary<int,NozzleSize>> ReadGroups(Dictionary<string,object> groups,bool flange)
        {
            var result=new Dictionary<string,Dictionary<int,NozzleSize>>(StringComparer.Ordinal);
            foreach(var group in groups)
            {
                var sizes=new Dictionary<int,NozzleSize>();
                foreach(var row in Map(group.Value))
                {
                    int dn;
                    if(!row.Key.StartsWith("DN",StringComparison.Ordinal) || !int.TryParse(row.Key.Substring(2),out dn))
                        throw new InvalidOperationException("管口尺寸表包含无效 DN："+row.Key);
                    var fields=Map(row.Value);
                    var s=new NozzleSize { NominalDn=dn,PipeOutsideMm=Number(fields,"pipe_od") };
                    if(flange)
                    {
                        s.FlangeOutsideMm=Number(fields,"flange_od");
                        s.FlangeThicknessMm=Number(fields,"flange_thickness");
                        s.BoltCircleMm=Number(fields,"bolt_circle_diameter");
                        s.BoltHoleMm=Number(fields,"bolt_hole_diameter");
                        s.BoltCount=(int)Number(fields,"bolt_count");
                        s.BoltSize=fields.ContainsKey("bolt_size")?Convert.ToString(fields["bolt_size"],CultureInfo.InvariantCulture):"";
                        s.RaisedFaceOutsideMm=Optional(fields,"raised_face_od");
                        s.RaisedFaceHeightMm=Optional(fields,"raised_face_height");
                    }
                    else s.PipeWallMm=Number(fields,"wall");
                    sizes.Add(dn,s);
                }
                result.Add(group.Key,sizes);
            }
            return result;
        }
        private static Dictionary<string,object> Map(object value)
        {
            var result=value as Dictionary<string,object>;
            if(result==null) throw new InvalidOperationException("管口尺寸表结构无效。");
            return result;
        }
        private static double Number(Dictionary<string,object> values,string key)
        {
            object value;
            if(!values.TryGetValue(key,out value)) throw new InvalidOperationException("管口尺寸表缺少字段："+key);
            double result=Convert.ToDouble(value,CultureInfo.InvariantCulture);
            if(double.IsNaN(result) || double.IsInfinity(result) || result<0)
                throw new InvalidOperationException("管口尺寸表字段无效："+key);
            return result;
        }
        private static double Optional(Dictionary<string,object> values,string key)
        { return values.ContainsKey(key)?Number(values,key):0; }
    }
}
