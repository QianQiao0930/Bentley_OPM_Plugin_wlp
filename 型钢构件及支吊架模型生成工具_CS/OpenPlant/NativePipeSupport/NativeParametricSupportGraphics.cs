extern alias NativeOPM;
using System;
using System.Collections.Generic;
using Bentley.Building.Mechanical.Components;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.OpenPlant.Modeler.Api;

namespace SteelSectionProbe
{
    /// <summary>A1宿主验证过的离线几何桥接、原生方向标记和ISO坐标同步。</summary>
    internal static class NativeParametricSupportGraphics
    {
        /// <param name="includeDirectionMarker">
        /// true时创建原生方向标记（旋转操作柄所需）；弯头耳轴传false，仅保留实体与ISO同步，父关联随动不受影响。
        /// 点串与自带 SinglePipeTrunnion / SupportLocation 相同：direction=−X（管轴滑动），orientation=+Z。
        /// 耳轴端必须落在局部 −Z，不能靠改点串把旋转柄从立管上挪走。
        /// </param>
        internal static List<ElementHolder> Create(Element local, IBMECObject support, bool includeDirectionMarker = true)
        {
            var result = new List<ElementHolder>();
            try
            {
                result.Add(Extract(local));
                if (includeDirectionMarker)
                {
                    using (var app = new BMApplication())
                    {
                        var marker = app.CreatePointStringElement(DPoint3d.Zero, new DVector3d(-1, 0, 0), new DVector3d(0, 0, 1));
                        if (marker == null) throw new InvalidOperationException("无法创建原生支架方向标记。");
                        result.Add(marker);
                    }
                }
                // 保留Support所需的三维Edge分类，但不调用SetTypeAndSymbology：
                // 该方法还会用OPM模型样式递归覆盖Cell内钢件、紧固件和参考体的原有外观。
                foreach (var holder in result)
                    holder.SetGraphicsType(BMdGraphicsType.bmdGraphicsTypeEdge, false);
                var origin = support.Transform3d.Translation;
                NativeSupportData.Finite(origin.X); NativeSupportData.Finite(origin.Y); NativeSupportData.Finite(origin.Z);
                if (!support.SetDoubleValueFromUors("SUPPORT_POINT_X", origin.X)
                    || !support.SetDoubleValueFromUors("SUPPORT_POINT_Y", origin.Y)
                    || !support.SetDoubleValueFromUors("SUPPORT_POINT_Z", origin.Z))
                    throw new InvalidOperationException("原生支架无法同步ISO支撑点。");
                return result;
            }
            catch { foreach (var holder in result) holder?.Dispose(); throw; }
        }

        private static unsafe ElementHolder Extract(Element element)
        {
            using (var temporary = new BMECObject())
            fixed (byte* handle = element.ElementHandle)
            {
                temporary.SetNonParametricElement((NativeOPM::Bentley.DgnPlatform.EditElementHandle*)handle);
                var cache = BMECApi.Instance.GraphicsCache;
                uint id = temporary.LegacyGraphicsId;
                try
                {
                    var clone = cache.GetById(id)?.Clone() as ElementHolder;
                    if (clone == null) throw new InvalidOperationException("无法克隆原生支架离线图形。");
                    return clone;
                }
                finally { cache.Remove(id); }
            }
        }
    }
}
