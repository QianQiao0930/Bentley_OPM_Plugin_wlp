using System;
using System.Collections.Generic;
using Bentley.Building.Mechanical.ComponentLibrary.ValveOperator;
using Bentley.Building.Mechanical.Components;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET.InteropServices;

namespace SteelSectionProbe
{
    /// <summary>Native gearbox interaction; body comes from this instance's persisted CEL revision.</summary>
    public sealed class CelValveActuatorComponent : GearBoxOperatorScript
    {
        public override List<ElementHolder> Create3DElements()
        {
            var result = new List<ElementHolder>();
            try
            {
                var asset = ActuatorCelInstanceData.Read(BMECObject.Instance);
                result.Add(ActuatorCelGraphics.Clone(asset));
                using (var app = new BMApplication())
                {
                    var marker = app.CreatePointStringElement(DPoint3d.Zero, new DVector3d(-1, 0, 0), new DVector3d(0, 0, 1));
                    if (marker == null) throw new InvalidOperationException("无法创建原生齿轮箱方向标记。");
                    marker.SetGraphicsType(BMdGraphicsType.bmdGraphicsTypeEdge, false);
                    result.Add(marker);
                }
                ValveActuatorLog.Callback(asset, BMECObject.Instance.InstanceId);
                return result;
            }
            catch (Exception error)
            {
                foreach (var holder in result) holder?.Dispose();
                ValveActuatorLog.Write("callback-failed", error.ToString());
                throw;
            }
        }
    }
}
