using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using Bentley.Interop.MicroStationDGN;
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
        internal string PipeNumber;
    }
    internal static class E1GuideReader
    {
        internal static E1GuideSelection Read(ulong id,double clickXUor,double clickYUor,double clickZUor)
        {
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null || !model.Is3d)throw new InvalidOperationException("请选择活动三维模型。");
            var info=model.GetModelInfo();
            double mmPerUor=1000.0/info.UorPerMeter;
            double mmPerMaster=info.UorPerMaster*mmPerUor;
            var snapshot=ComponentPropertyReader.Read(id);
            bool pipe=(!string.IsNullOrEmpty(snapshot.ClassName) &&
                snapshot.ClassName.IndexOf("PIPE",StringComparison.OrdinalIgnoreCase)>=0) ||
                snapshot.AllProperties.Any(x=>x.Key.IndexOf(".PIPE.",StringComparison.OrdinalIgnoreCase)>=0 ||
                    x.Key.IndexOf(".PIPE_",StringComparison.OrdinalIgnoreCase)>=0);
            var com=Bentley.MstnPlatformNET.InteropServices.Utilities.ComApp.ActiveModelReference.GetElementByID64(checked((long)id));
            if(com==null)throw new InvalidOperationException("无法读取所选元素。");
            bool polyline=com.Type==MsdElementType.LineString || com.Type==MsdElementType.ComplexString;
            if(!pipe && com.Type!=MsdElementType.Line && !polyline)
                throw new InvalidOperationException("请选择直线、多段线或 OpenPlant 直管。");
            var selection=new E1GuideSelection {ElementId=id,
                IsPipe=pipe,
                ClickX=clickXUor*mmPerUor,ClickY=clickYUor*mmPerUor,ClickZ=clickZUor*mmPerUor,
                PipeNumber="",IsAuxiliaryLine=com.Type==MsdElementType.Line && !pipe &&
                    (string.IsNullOrEmpty(snapshot.Schema) ||
                        !snapshot.Schema.StartsWith("OpenPlant",StringComparison.OrdinalIgnoreCase)) &&
                    !snapshot.AllProperties.Any(x=>x.Key.StartsWith("OpenPlant",StringComparison.OrdinalIgnoreCase)) &&
                    string.IsNullOrEmpty(snapshot.ReadWarning)};
            if(polyline)
            {
                var selected=E1GuideSegmentSelector.Nearest(
                    StraightSegments(com,mmPerMaster),selection.ClickX,selection.ClickY,selection.ClickZ);
                CopySegment(selected,selection);
            }
            else if(snapshot.StartX.HasValue && snapshot.EndX.HasValue)
            {
                selection.StartX=snapshot.StartX.Value;selection.StartY=snapshot.StartY.Value;
                selection.StartZ=snapshot.StartZ.Value;selection.EndX=snapshot.EndX.Value;
                selection.EndY=snapshot.EndY.Value;selection.EndZ=snapshot.EndZ.Value;
            }
            else
            {
                if(!pipe)throw new InvalidOperationException("该直线没有可读取的轴线。");
                var range=com.Range;
                double x=(range.Low.X+range.High.X)/2*mmPerMaster;
                double y=(range.Low.Y+range.High.Y)/2*mmPerMaster;
                double z=(range.Low.Z+range.High.Z)/2*mmPerMaster;
                double rx=(range.High.X-range.Low.X)*mmPerMaster;
                double ry=(range.High.Y-range.Low.Y)*mmPerMaster;
                double rz=(range.High.Z-range.Low.Z)*mmPerMaster;
                if(Math.Max(rx,ry)<Math.Max(50,rz*2))
                    throw new InvalidOperationException("无法从管道范围可靠判断水平轴线，请选择辅助线。");
                // A bounding box loses the sign of the slope; never treat a clearly sloped pipe as level.
                double crossSpan=Math.Min(rx,ry);
                if(rz>Math.Max(50,crossSpan*1.5))
                    throw new InvalidOperationException("该斜管没有可读取的真实中心线；请沿管轴绘制辅助线后点取。");
                selection.StartX=x-(rx>=ry?rx/2:0);selection.EndX=x+(rx>=ry?rx/2:0);
                selection.StartY=y-(ry>rx?ry/2:0);selection.EndY=y+(ry>rx?ry/2:0);
                selection.StartZ=z;selection.EndZ=z;
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
        private static IList<E1GuideSegment> StraightSegments(Element element,double mmPerMaster)
        {
            var segments=new List<E1GuideSegment>();
            if(element.Type==MsdElementType.LineString)
            {
                AddVertices(element.AsVertexList().GetVertices(),mmPerMaster,segments);
            }
            else if(element.Type==MsdElementType.ComplexString)
            {
                var children=element.AsComplexStringElement().GetSubElements();
                while(children.MoveNext())
                {
                    var part=children.Current;
                    if(part.Type!=MsdElementType.Line && part.Type!=MsdElementType.LineString)
                        throw new InvalidOperationException("组合多段线含曲线段；请选择仅由直线构成的多段线。");
                    AddVertices(part.AsVertexList().GetVertices(),mmPerMaster,segments);
                }
            }
            return segments;
        }
        private static void AddVertices(Point3d[] vertices,double scale,ICollection<E1GuideSegment> segments)
        {
            if(vertices==null)return;
            for(int i=0;i+1<vertices.Length;i++)
            {
                var a=vertices[i];var b=vertices[i+1];
                segments.Add(new E1GuideSegment(a.X*scale,a.Y*scale,a.Z*scale,
                    b.X*scale,b.Y*scale,b.Z*scale));
            }
        }
    }
}
