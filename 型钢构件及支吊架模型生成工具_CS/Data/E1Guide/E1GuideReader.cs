using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
namespace SteelSectionProbe
{
    internal sealed class E1GuideSelection
    {
        internal ulong ElementId;
        internal double StartX,StartY,StartZ,EndX,EndY,EndZ,ClickX,ClickY,ClickZ;
        internal int? PipeDn;
        internal bool IsAuxiliaryLine;
        /// <summary>所选元素是否识别为 OpenPlant 管道（供管夹类功能判断按管道还是按面板参数取径）。</summary>
        internal bool IsPipe;
        /// <summary>所选元素是否来自参考文件（reference）。</summary>
        internal bool IsFromReference;
        /// <summary>轴线相关的提示（如"已按元素范围最长边近似管轴"）；无提示时为空。</summary>
        internal string AxisNote;
        internal string PipeNumber;
    }
    /// <summary>
    /// 读所选元素（管道 / 直线 / 多段线）的轴线与管道号。
    /// <para>
    /// 支持参考文件里的元素：调用方需把元素所属的模型引用传进来（见 <see cref="LocatedElement"/>）。
    /// 元素类型判断与多段线顶点改用 .NET 曲线查询（<c>CurvePathQuery</c>），
    /// 因为它对活动模型与参考模型一视同仁；旧代码用的 COM 引用只认活动模型。
    /// </para>
    /// </summary>
    internal static class E1GuideReader
    {
        /// <summary>在活动模型里读取（兼容原有调用）。</summary>
        internal static E1GuideSelection Read(ulong id,double clickXUor,double clickYUor,double clickZUor)
        {
            return Read(null,id,clickXUor,clickYUor,clickZUor);
        }

        internal static E1GuideSelection Read(DgnModelRef modelRef,ulong id,
            double clickXUor,double clickYUor,double clickZUor)
        {
            var model=ComponentPropertyReader.ResolveModel(modelRef);
            if(model==null || !model.Is3d)throw new InvalidOperationException("请选择活动三维模型。");
            var info=model.GetModelInfo();
            double mmPerUor=1000.0/info.UorPerMeter;
            var snapshot=ComponentPropertyReader.Read(modelRef,id);
            bool pipe=LooksLikeOpenPlantPipe(snapshot);
            var element=model.FindElementById(new ElementId(ref id));
            if(element==null)throw new InvalidOperationException("无法读取所选元素。");
            var curve=CurvePathQuery.ElementToCurveVector(element);
            bool openCurve=curve!=null && curve.GetBoundaryType()==CurveVector.BoundaryType.Open;
            var segments=openCurve?StraightSegments(curve,mmPerUor):new List<E1GuideSegment>();
            bool isStraightLine=openCurve && segments.Count==1;
            var selection=new E1GuideSelection {ElementId=id,
                IsPipe=pipe,
                IsFromReference=modelRef!=null && !ReferenceEquals(model,
                    Session.Instance.GetActiveDgnModel()),
                ClickX=clickXUor*mmPerUor,ClickY=clickYUor*mmPerUor,ClickZ=clickZUor*mmPerUor,
                PipeNumber="",IsAuxiliaryLine=isStraightLine && !pipe &&
                    (string.IsNullOrEmpty(snapshot.Schema) ||
                        !snapshot.Schema.StartsWith("OpenPlant",StringComparison.OrdinalIgnoreCase)) &&
                    !snapshot.AllProperties.Any(x=>x.Key.StartsWith("OpenPlant",StringComparison.OrdinalIgnoreCase)) &&
                    string.IsNullOrEmpty(snapshot.ReadWarning)};
            if(segments.Count>1)
            {
                var selected=E1GuideSegmentSelector.Nearest(segments,
                    selection.ClickX,selection.ClickY,selection.ClickZ);
                CopySegment(selected,selection);
            }
            else if(snapshot.StartX.HasValue && snapshot.EndX.HasValue)
            {
                selection.StartX=snapshot.StartX.Value;selection.StartY=snapshot.StartY.Value;
                selection.StartZ=snapshot.StartZ.Value;selection.EndX=snapshot.EndX.Value;
                selection.EndY=snapshot.EndY.Value;selection.EndZ=snapshot.EndZ.Value;
            }
            else if(CanUseRange(snapshot))
            {
                // 包围盒兜底：**取最长边方向当管轴**，与 Python 的 axis_from_bbox 完全一致。
                // ⚠️ 这里不要加"必须水平"的限制：竖直管道同样要靠这条兜底（A2 / E1 / T4 本来就支持
                // 竖直管，只有 K1 自己限制 ≤5°）。按水平假设会把手里的竖直管一律拒掉，
                // 而 Python 版本正是靠"最长边"把竖直管也算出来的。
                // 包围盒会丢坡向，所以只给近似提示（AxisNote）而不是报错 —— 与 Python 的 warnings 一致。
                double x=snapshot.CenterXmm.Value,y=snapshot.CenterYmm.Value,z=snapshot.CenterZMm.Value;
                double rx=snapshot.RangeXmm.Value,ry=snapshot.RangeYmm.Value,rz=snapshot.RangeZmm.Value;
                int index=rz>=rx && rz>=ry?2:(ry>=rx?1:0);
                double span=index==0?rx:(index==1?ry:rz);
                if(span<=1.0e-9)
                    throw new InvalidOperationException("所选元素的元素范围为零，无法确定管轴。"+
                        Diagnostics(modelRef,id,snapshot,curve));
                double half=span/2.0;
                selection.StartX=x-(index==0?half:0.0);selection.EndX=x+(index==0?half:0.0);
                selection.StartY=y-(index==1?half:0.0);selection.EndY=y+(index==1?half:0.0);
                selection.StartZ=z-(index==2?half:0.0);selection.EndZ=z+(index==2?half:0.0);
                selection.AxisNote="该元素没有中心线曲线，已按元素范围最长边近似管轴定位"+
                    "（仅对与世界坐标轴平行的直管段可靠；斜管、弯头 / 阀门请勿使用）。";
            }
            else
            {
                throw new InvalidOperationException((pipe?"该管道":"所选元素")+
                    "没有可读取的中心线，也没有可用的元素范围，无法定位；"+
                    "请选择直线、多段线或 OpenPlant 直管。"+Diagnostics(modelRef,id,snapshot,curve));
            }
            if(pipe)
            {
                foreach(string name in new[]{"NOMINAL_DIAMETER","OUTSIDE_DIAMETER"})
                {
                    string raw;
                    double number;
                    if(snapshot.Properties.TryGetValue(name,out raw) &&
                        double.TryParse(raw,NumberStyles.Float,CultureInfo.InvariantCulture,out number))
                    {
                        if(number>0 && number<1)number*=1000;
                        selection.PipeDn=E1GuideCatalog.MatchDn(number);
                        if(selection.PipeDn.HasValue)break;
                    }
                }
            }
            foreach(string name in new[]{"LINENUMBER","LINE_NUMBER","PIPE_NUMBER"})
            {
                string value;
                if(snapshot.Properties.TryGetValue(name,out value) && !string.IsNullOrWhiteSpace(value))
                {selection.PipeNumber=value;break;}
            }
            return selection;
        }
        private static void CopySegment(E1GuideSegment segment,E1GuideSelection selection)
        {
            selection.StartX=segment.StartX;selection.StartY=segment.StartY;selection.StartZ=segment.StartZ;
            selection.EndX=segment.EndX;selection.EndY=segment.EndY;selection.EndZ=segment.EndZ;
        }

        /// <summary>元素范围（包围盒）是否完整可用 —— 完整才允许走"最长边当管轴"的兜底。</summary>
        private static bool CanUseRange(ComponentSnapshot snapshot)
        {
            return snapshot!=null && snapshot.RangeXmm.HasValue && snapshot.RangeYmm.HasValue &&
                snapshot.RangeZmm.HasValue && snapshot.CenterXmm.HasValue &&
                snapshot.CenterYmm.HasValue && snapshot.CenterZMm.HasValue;
        }

        /// <summary>
        /// 失败时的诊断尾巴。状态栏一行会被截断，所以调用方应把它显示在能换行的文本区。
        /// </summary>
        private static string Diagnostics(DgnModelRef modelRef,ulong id,ComponentSnapshot snapshot,
            CurveVector curve)
        {
            return "　诊断："+(LocatedElement.IsReference(modelRef)?"参考文件":"活动模型")+
                "，元素 id="+id.ToString(CultureInfo.InvariantCulture)+
                "，EC 类="+(snapshot==null || string.IsNullOrEmpty(snapshot.ClassName)
                    ?"（空）":snapshot.ClassName)+
                "，EC 属性 "+((snapshot==null || snapshot.AllProperties==null)
                    ?0:snapshot.AllProperties.Count)+" 条"+
                "，曲线="+(curve==null?"无":"有")+
                "，几何来源="+(snapshot==null || string.IsNullOrEmpty(snapshot.GeometrySource)
                    ?"（空）":snapshot.GeometrySource)+
                ((snapshot==null || string.IsNullOrEmpty(snapshot.ReadWarning))
                    ?"":"，提示="+snapshot.ReadWarning);
        }

        /// <summary>
        /// 判断所选元素是不是 OpenPlant 的管道（管段）。
        /// <para>
        /// **不能只认 "PIPE" 这个子串** —— 实际模型里管道类常叫 PIPING_xxx、SEGMENT 之类，
        /// 只认 "PIPE" 会把它们全判成"不是管道"，于是落到"请选择直线、多段线或 OpenPlant 直管"
        /// 这条误导性报错上。因此这里再补一条结构性判据：
        /// **OpenPlant 架构 + 同时带公称直径与外径**，就是管道类构件。
        /// </para>
        /// </summary>
        private static bool LooksLikeOpenPlantPipe(ComponentSnapshot snapshot)
        {
            if(snapshot==null) return false;
            if(!string.IsNullOrEmpty(snapshot.ClassName) &&
                snapshot.ClassName.IndexOf("PIP",StringComparison.OrdinalIgnoreCase)>=0) return true;
            if(!string.IsNullOrEmpty(snapshot.Schema) &&
                snapshot.Schema.IndexOf("PIP",StringComparison.OrdinalIgnoreCase)>=0) return true;
            if(snapshot.AllProperties!=null &&
                snapshot.AllProperties.Any(x=>x.Key.IndexOf(".PIP",StringComparison.OrdinalIgnoreCase)>=0))
                return true;
            if(!string.IsNullOrEmpty(snapshot.Schema) &&
                snapshot.Schema.StartsWith("OpenPlant",StringComparison.OrdinalIgnoreCase) &&
                HasProperty(snapshot,"NOMINAL_DIAMETER") && HasProperty(snapshot,"OUTSIDE_DIAMETER"))
                return true;
            return false;
        }

        /// <summary>EC 属性名大小写不敏感的存在性判断（属性字典本身是大小写敏感的）。</summary>
        private static bool HasProperty(ComponentSnapshot snapshot,string name)
        {
            if(snapshot==null || snapshot.Properties==null) return false;
            if(snapshot.Properties.ContainsKey(name)) return true;
            foreach(string key in snapshot.Properties.Keys)
                if(string.Equals(key,name,StringComparison.OrdinalIgnoreCase)) return true;
            return false;
        }
        /// <summary>
        /// 逐段收集曲线里的直线段（.NET 几何坐标为 UOR，按 mmPerUor 转毫米）。
        /// 圆弧段会被跳过 —— 与"只取直线段"的既有语义一致。
        /// </summary>
        private static IList<E1GuideSegment> StraightSegments(CurveVector curve,double mmPerUor)
        {
            var segments=new List<E1GuideSegment>();
            int count=curve.Count;
            for(int index=0;index<count;index++)
            {
                var primitive=curve.GetPrimitive(index);
                if(primitive==null)continue;
                DSegment3d line;
                if(!primitive.TryGetLine(out line))continue;
                DPoint3d a,b;
                if(!primitive.GetStartEnd(out a,out b))continue;
                segments.Add(new E1GuideSegment(a.X*mmPerUor,a.Y*mmPerUor,a.Z*mmPerUor,
                    b.X*mmPerUor,b.Y*mmPerUor,b.Z*mmPerUor));
            }
            return segments;
        }
    }
}
