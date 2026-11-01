using System;
using System.Collections.Generic;
using System.Text;
using Bentley.Building.Mechanical.ComponentLibrary.ValveOperator;
using Bentley.Building.Mechanical.Components;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET.InteropServices;

namespace ActuatorCallbackCheck
{
    /// <summary>Uses native gearbox setup and Topwork placement with fixed CEL body geometry.</summary>
    public sealed class CelGearboxComponent : GearBoxOperatorScript
    {
        // Inherit GearBoxOperatorScript.Setup; never change the existing handwheel handler's base.
        public override List<ElementHolder> Create3DElements()
        {
            var trace = new StringBuilder();
            trace.AppendLine("Version=5; Route=parametric GearBoxOperatorScript.Create3DElements override; Placement=official Topwork tool");
            trace.AppendLine("Assembly=" + typeof(CelGearboxComponent).Assembly.Location
                + "; MVID=" + typeof(CelGearboxComponent).Assembly.ManifestModule.ModuleVersionId);
            try
            {
                if (BMECObject == null || BMECObject.GetIntValue("SSP_CEL_VERSION") != 1)
                    throw new InvalidOperationException("CEL 齿轮箱缺少受支持的资源版本。");
                trace.AppendLine("Instance=" + BMECObject.Instance.InstanceId + "; Transform=" + BMECObject.Transform3d);
                var result = new List<ElementHolder> { CelResource.CloneForActiveModel() };
                using (var app = new BMApplication())
                {
                    // Exact frame emitted by this installed SDK's GearBoxOperatorDraw:
                    // origin (0,0,0), direction (-1,0,0), orientation (0,0,1).
                    // Preserve this native marker while omitting the stock solids.
                    var marker = app.CreatePointStringElement(DPoint3d.Zero,
                        new DVector3d(-1, 0, 0), new DVector3d(0, 0, 1));
                    if (marker == null) throw new InvalidOperationException("无法创建原生齿轮箱方向标记。");
                    marker.SetGraphicsType(BMdGraphicsType.bmdGraphicsTypeEdge, false);
                    result.Add(marker);
                }
                trace.AppendLine("CallbackResult=CEL geometry clone + native gearbox direction marker; StockGearboxGeometryCalled=false; ResourceSha256=" + CelResource.Hash);
                trace.AppendLine("LocalOrigin=unchanged CEL origin; NativeMarkerOrigin=0,0,0; Direction=-1,0,0; Orientation=0,0,1; FixedCelGeometry=true");
                return result;
            }
            catch (Exception error) { trace.AppendLine("CallbackFailed=" + error); throw; }
            finally { TraceLog.Save("gearbox_callback", trace.ToString()); }
        }
    }
}
