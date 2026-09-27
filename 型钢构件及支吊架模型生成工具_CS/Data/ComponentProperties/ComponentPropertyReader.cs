using System;
using System.Collections.Generic;
using System.Globalization;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.DgnEC;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;
using Bentley.EC.Persistence.Query;
using Bentley.ECObjects.Instance;

namespace SteelSectionProbe
{
    /// <summary>
    /// Reads Bentley objects only while the query collection is being enumerated.
    /// <para>
    /// 支持参考文件（reference）里的元素：这类元素的 ElementId 属于**它自己那个文件的
    /// ID 空间**，按 ID 在活动模型里找不到，因此必须把元素所属的模型引用一起传进来。
    /// 几何读取分两条路径：元素属于活动模型时仍走原 COM 路径（行为完全不变）；
    /// 元素来自参考文件时改用 .NET 曲线查询（不依赖活动模型）。
    /// </para>
    /// </summary>
    internal static class ComponentPropertyReader
    {
        /// <summary>在活动模型里读取（兼容原有调用）。</summary>
        internal static ComponentSnapshot Read(ulong id)
        {
            return Read(null,id);
        }

        /// <summary>
        /// 读取元素快照。<paramref name="modelRef"/> 为元素所属的模型引用
        /// （见 <see cref="LocatedElement"/>）；传 null 表示活动模型。
        /// </summary>
        internal static ComponentSnapshot Read(DgnModelRef modelRef,ulong id)
        {
            var model=ResolveModel(modelRef);
            if(model==null) throw new InvalidOperationException("没有活动模型。");
            var elementId=new ElementId(ref id);
            Element element=model.FindElementById(elementId);
            if(element==null)
                throw new InvalidOperationException(modelRef==null
                    ?"所选元素已不存在。"
                    :"所选元素在它所属的模型里已不存在。");
            var snapshot=new ComponentSnapshot {ElementId=id};
            try { ReadGeometry(element,id,snapshot); }
            catch(Exception ex) { snapshot.ReadWarning="几何读取失败："+ex.Message; }
            try { ReadEc(element,snapshot); }
            catch(Exception ex) { snapshot.ReadWarning+=" EC 读取失败："+ex.Message; }
            return snapshot;
        }

        /// <summary>解析模型引用；取不到模型时回落到活动模型。</summary>
        internal static DgnModel ResolveModel(DgnModelRef modelRef)
        {
            if(modelRef!=null)
            {
                var fromReference=modelRef.GetDgnModel();
                if(fromReference!=null) return fromReference;
            }
            return Session.Instance.GetActiveDgnModel();
        }

        private static void ReadGeometry(Element element,ulong id,ComponentSnapshot snapshot)
        {
            var modelRef=element==null?null:element.DgnModelRef;
            var model=ResolveModel(modelRef);
            if(model==null) return;
            var modelInfo=model.GetModelInfo();
            double uorPerMm=modelInfo.UorPerMeter/1000.0;
            if(uorPerMm<=0) return;
            // 活动模型里的元素继续走 COM（能力最全，含 Cell 的范围）；参考文件的元素在
            // ActiveModelReference 里查不到，改用 .NET 曲线查询。
            // ⚠️ 必须**按模型身份**选路径，不能"先试 COM"：ComApp.ActiveModelReference 只认活动模型，
            // 而元素 ID 是两个文件各自编号的 —— 活动模型里很可能存在同号的另一个元素，
            // 那样会读出**另一个构件**的几何（表现为"信息有值、放置位置却完全不对"）。
            if(!LocatedElement.IsReference(modelRef) &&
                TryReadGeometryFromCom(id,snapshot,modelInfo,uorPerMm)) return;
            ReadGeometryFromCurve(element,snapshot,uorPerMm);
        }

        /// <summary>原路径：只用活动模型的 COM 引用。元素不在活动模型时返回 false。</summary>
        private static bool TryReadGeometryFromCom(ulong id,ComponentSnapshot snapshot,
            ModelInfo modelInfo,double uorPerMm)
        {
            var com=Bentley.MstnPlatformNET.InteropServices.Utilities.ComApp.ActiveModelReference
                .GetElementByID64(checked((long)id));
            if(com==null) return false;
            var range=com.Range;
            if(range.High.X>=range.Low.X)
            {
                snapshot.RangeXmm=(range.High.X-range.Low.X)*modelInfo.UorPerMaster/uorPerMm;
                snapshot.RangeYmm=(range.High.Y-range.Low.Y)*modelInfo.UorPerMaster/uorPerMm;
                snapshot.RangeZmm=(range.High.Z-range.Low.Z)*modelInfo.UorPerMaster/uorPerMm;
                snapshot.CenterXmm=(range.Low.X+range.High.X)*modelInfo.UorPerMaster/uorPerMm/2;
                snapshot.CenterYmm=(range.Low.Y+range.High.Y)*modelInfo.UorPerMaster/uorPerMm/2;
                snapshot.CenterZMm=(range.Low.Z+range.High.Z)*modelInfo.UorPerMaster/uorPerMm/2;
                snapshot.LengthMm=Math.Max(snapshot.RangeXmm.Value,Math.Max(snapshot.RangeYmm.Value,snapshot.RangeZmm.Value));
                snapshot.GeometrySource="元素范围近似";
            }
            // Native curve geometry is used only for an open path. A closed profile is not a pipe axis.
            try
            {
                var chain=com.AsChainableElement();
                if(chain==null || chain.Length<=0) return true;
                var start=chain.StartPoint;
                var end=chain.EndPoint;
                double dx=start.X-end.X,dy=start.Y-end.Y,dz=start.Z-end.Z;
                if(Math.Sqrt(dx*dx+dy*dy+dz*dz)<=1e-9) return true;
                snapshot.StartX=start.X*modelInfo.UorPerMaster/uorPerMm;
                snapshot.StartY=start.Y*modelInfo.UorPerMaster/uorPerMm;
                snapshot.StartZ=start.Z*modelInfo.UorPerMaster/uorPerMm;
                snapshot.EndX=end.X*modelInfo.UorPerMaster/uorPerMm;
                snapshot.EndY=end.Y*modelInfo.UorPerMaster/uorPerMm;
                snapshot.EndZ=end.Z*modelInfo.UorPerMaster/uorPerMm;
                snapshot.LengthMm=chain.Length*modelInfo.UorPerMaster/uorPerMm;
                snapshot.CenterZMm=(snapshot.StartZ+snapshot.EndZ)/2;
                snapshot.GeometrySource="开放曲线";
            }
            catch { /* Cells and non-chain elements retain their range. */ }
            return true;
        }

        /// <summary>
        /// 参考文件元素的几何。优先走 .NET 曲线查询；曲线查不到时改走"显示几何"通道 ——
        /// OpenPlant 的管道/管件多是实体，没有曲线路径，只有显示几何通道拿得到。
        /// .NET 几何坐标是 UOR，因此直接除以 uorPerMm 即为毫米
        /// （COM 的坐标是 master 单位，两者换算不同）。
        /// </summary>
        private static void ReadGeometryFromCurve(Element element,ComponentSnapshot snapshot,
            double uorPerMm)
        {
            double mmPerUor=1.0/uorPerMm;
            var curve=CurvePathQuery.ElementToCurveVector(element);
            bool openCurve=curve!=null && curve.GetBoundaryType()==CurveVector.BoundaryType.Open;
            bool haveRange=false;
            if(!openCurve)
            {
                DRange3d displayRange;
                CurveVector displayCurve;
                if(TryReadDisplayGeometry(element,out displayRange,out displayCurve))
                {
                    if(displayCurve!=null &&
                        displayCurve.GetBoundaryType()==CurveVector.BoundaryType.Open)
                    {
                        curve=displayCurve;
                        openCurve=true;
                    }
                    if(displayRange.High.X>=displayRange.Low.X)
                    {
                        FillRange(snapshot,displayRange,mmPerUor,"显示几何（参考文件）");
                        haveRange=true;
                    }
                }
            }
            if(!haveRange && curve!=null)
            {
                DRange3d range;
                if(curve.GetRange(out range) && range.High.X>=range.Low.X)
                    FillRange(snapshot,range,mmPerUor,"元素范围（参考文件）");
            }
            if(!openCurve || curve==null) return;
            DPoint3d start,end;
            if(!curve.GetStartEnd(out start,out end)) return;
            double dx=start.X-end.X,dy=start.Y-end.Y,dz=start.Z-end.Z;
            if(Math.Sqrt(dx*dx+dy*dy+dz*dz)<=1e-9) return;
            snapshot.StartX=start.X*mmPerUor;
            snapshot.StartY=start.Y*mmPerUor;
            snapshot.StartZ=start.Z*mmPerUor;
            snapshot.EndX=end.X*mmPerUor;
            snapshot.EndY=end.Y*mmPerUor;
            snapshot.EndZ=end.Z*mmPerUor;
            snapshot.LengthMm=Math.Sqrt(dx*dx+dy*dy+dz*dz)*mmPerUor;
            snapshot.CenterZMm=(snapshot.StartZ+snapshot.EndZ)/2;
            snapshot.GeometrySource="开放曲线（参考文件）";
        }

        private static void FillRange(ComponentSnapshot snapshot,DRange3d range,double mmPerUor,
            string source)
        {
            snapshot.RangeXmm=(range.High.X-range.Low.X)*mmPerUor;
            snapshot.RangeYmm=(range.High.Y-range.Low.Y)*mmPerUor;
            snapshot.RangeZmm=(range.High.Z-range.Low.Z)*mmPerUor;
            snapshot.CenterXmm=(range.Low.X+range.High.X)*mmPerUor/2;
            snapshot.CenterYmm=(range.Low.Y+range.High.Y)*mmPerUor/2;
            snapshot.CenterZMm=(range.Low.Z+range.High.Z)*mmPerUor/2;
            snapshot.LengthMm=Math.Max(snapshot.RangeXmm.Value,
                Math.Max(snapshot.RangeYmm.Value,snapshot.RangeZmm.Value));
            snapshot.GeometrySource=source;
        }

        /// <summary>
        /// 显示几何通道：<see cref="ElementGraphicsOutput.Process"/> 会把元素的**显示几何**
        /// 交给处理器，这条通道与元素所在模型无关 —— 参考文件里的元素同样能拿到，
        /// 因此它正是曲线查询对参考元素失效时的兜底。
        /// </summary>
        private static bool TryReadDisplayGeometry(Element element,out DRange3d range,
            out CurveVector openCurve)
        {
            range=DRange3d.NullRange;
            openCurve=null;
            if(element==null) return false;
            try
            {
                var accumulator=new GeometryAccumulator();
                ElementGraphicsOutput.Process(element,accumulator);
                range=accumulator.Range;
                openCurve=accumulator.OpenCurve;
                return true;
            }
            catch { return false; }
        }

        /// <summary>收集显示几何的包围盒，并记住第一条开放曲线（可当作轴线）。</summary>
        private sealed class GeometryAccumulator : ElementGraphicsProcessor
        {
            internal DRange3d Range=DRange3d.NullRange;
            internal CurveVector OpenCurve;

            public override BentleyStatus ProcessCurveVector(CurveVector curves,bool isClosed)
            {
                if(curves!=null)
                {
                    DRange3d range;
                    if(curves.GetRange(out range))
                    {
                        Range.Extend(range.Low);
                        Range.Extend(range.High);
                    }
                    if(!isClosed && OpenCurve==null) OpenCurve=curves;
                }
                return BentleyStatus.Success;
            }
        }

        private static void ReadEc(Element element, ComponentSnapshot snapshot)
        {
            var scope = FindInstancesScope.CreateScope(element, new FindInstancesScopeOption(DgnECHostType.Element));
            var query = new ECQuery();
            query.SelectClause.SelectAllProperties = true;
            ECQueryProcessAccessor.SetIn(query.ExtendedDataValueSetter, ECQueryProcessFlags.SearchAllClasses);
            using (var instances = DgnECManager.Manager.FindInstances(scope, query))
            {
                int bestScore = -1;
                foreach (IDgnECInstance instance in instances)
                {
                    // Copy every value here. Bentley instances must not outlive this enumeration.
                    var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
                    foreach (var property in instance.ClassDefinition.Properties(true))
                    {
                        string name = property.Name;
                        try
                        {
                            CaptureValue(instance[name], name, values);
                        }
                        catch { /* An inaccessible property does not hide the remaining values. */ }
                    }
                    string schema = instance.ClassDefinition.Schema.Name;
                    string className = instance.ClassDefinition.Name;
                    foreach (var pair in values)
                        snapshot.AllProperties.Add(new KeyValuePair<string, string>(schema + "." + className + "." + pair.Key, pair.Value));
                    int score = schema.StartsWith("OpenPlant", StringComparison.OrdinalIgnoreCase) ? 10 : 0;
                    if (className.StartsWith("PIPE", StringComparison.OrdinalIgnoreCase)) score += 3;
                    if (values.ContainsKey("OUTSIDE_DIAMETER")) score += 2;
                    if (score <= bestScore) continue;
                    bestScore = score;
                    snapshot.Schema = schema;
                    snapshot.ClassName = className;
                    snapshot.InstanceId = instance.InstanceId;
                    snapshot.Properties.Clear();
                    foreach (var pair in values) snapshot.Properties.Add(pair.Key, pair.Value);
                }
            }
        }
        private static void CaptureValue(IECPropertyValue value, string name, IDictionary<string, string> values)
        {
            if (value == null || value.IsNull) return;
            if (value.IsArray || value.IsStruct)
            {
                if (value.ContainedValues == null) return;
                foreach (IECPropertyValue child in value.ContainedValues)
                    CaptureValue(child, string.IsNullOrEmpty(child.AccessString) ? name : child.AccessString, values);
                return;
            }
            object native = value.NativeValue;
            string text = native == null ? value.XmlStringValue : Convert.ToString(native, CultureInfo.InvariantCulture);
            if (!string.IsNullOrWhiteSpace(text)) values[name] = text;
        }
    }
}
