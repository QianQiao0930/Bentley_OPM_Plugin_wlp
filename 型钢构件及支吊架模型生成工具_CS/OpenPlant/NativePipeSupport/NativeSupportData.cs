using System;
using System.Globalization;
using System.Linq;
using Bentley.ECObjects.Instance;
using Bentley.OpenPlant.Modeler.Api;

namespace SteelSectionProbe
{
    /// <summary>A1宿主试验确认的出图契约。只操作当前新建支吊架，不改Schema或全局提取规则。</summary>
    internal static class NativeSupportData
    {
        internal static void Finite(double value)
        { if (double.IsNaN(value) || double.IsInfinity(value)) throw new InvalidOperationException("支吊架坐标或尺寸不是有限值。"); }

        internal static void RequireProperty(IECInstance instance, string name)
        {
            if (!instance.ClassDefinition.Properties(true).Any(item => item.Name == name))
                throw new InvalidOperationException("当前工作集缺少支吊架出图必需属性：" + name);
        }

        internal static void Write(BMECObject support, double[] pointMm)
        {
            foreach (string name in new[] { "STATE", "SHOP_FIELD", "SUPPORT_POINT_X", "SUPPORT_POINT_Y", "SUPPORT_POINT_Z" })
                RequireProperty(support.Instance, name);
            support.Instance["STATE"].StringValue = "Design";
            support.Instance["SHOP_FIELD"].StringValue = "SHOP";
            for (int i = 0; i < 3; i++)
            {
                Finite(pointMm[i]);
                if (!support.SetDoubleValueFromMM("SUPPORT_POINT_" + "XYZ"[i], pointMm[i]))
                    throw new InvalidOperationException("ISO支撑点坐标写入失败。");
            }
        }

        internal static double ReadCoordinate(BMECObject support, string name)
        {
            RequireProperty(support.Instance, name);
            if (support.Instance[name].IsNull) throw new InvalidOperationException("ISO支撑点坐标为空：" + name);
            double value = support.GetDoubleValueInMM(name); Finite(value); return value;
        }

        internal static void Validate(BMECObject support, string parentId, double[] pointMm, double uorPerMm, Action<string> log, bool parametric = false)
        {
            var parents = BMECApi.Instance.GetRelatedInstances(support.Instance, "DEVICE_HAS_SUPPORT", false, true);
            if (parents == null || parents.Count != 1 || parents[0].InstanceId != parentId)
                throw new InvalidOperationException("支吊架父管道关系缺失或不一致。");
            var p = support.Transform3d.Translation;
            double modelError = Math.Sqrt(Math.Pow(p.X / uorPerMm - pointMm[0], 2) + Math.Pow(p.Y / uorPerMm - pointMm[1], 2) + Math.Pow(p.Z / uorPerMm - pointMm[2], 2));
            double isoErrorSquared = 0;
            for (int i = 0; i < 3; i++) isoErrorSquared += Math.Pow(ReadCoordinate(support, "SUPPORT_POINT_" + "XYZ"[i]) - pointMm[i], 2);
            double isoError = Math.Sqrt(isoErrorSquared); Finite(modelError); Finite(isoError);
            if (modelError > 1 || isoError > 1) throw new InvalidOperationException("支吊架三维/ISO支撑点与目标管轴位置不一致。");
            if (support.IsParametric != parametric) throw new InvalidOperationException("原生组件图形类型与本次创建方式不一致。");
            if (support.Instance["STATE"].IsNull || support.Instance["STATE"].StringValue != "Design"
                || support.Instance["SHOP_FIELD"].IsNull || support.Instance["SHOP_FIELD"].StringValue != "SHOP")
                throw new InvalidOperationException("支吊架Design/SHOP出图状态未保存。");
            log("原生关联及三维/ISO点通过；误差=" + modelError.ToString("0.###", CultureInfo.InvariantCulture) + "/" + isoError.ToString("0.###", CultureInfo.InvariantCulture) + " mm；Design/SHOP。");
        }
    }
}
