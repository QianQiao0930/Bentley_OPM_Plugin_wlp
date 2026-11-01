using System;
using System.Globalization;
using System.Linq;
using Bentley.ECObjects.Instance;

namespace SteelSectionProbe
{
    /// <summary>Each native instance owns its full CEL revision; source path is descriptive only.</summary>
    internal static class ActuatorCelInstanceData
    {
        internal const string ClassName = "SSP_CEL_VALVE_ACTUATOR";
        internal static readonly string[] SizeFields = { "TOTAL_HEIGHT", "GEAR_BOX_HEIGHT", "GEAR_BOX_WIDTH",
            "GEAR_BOX_THICKNESS", "HANDLE_WIDTH", "HANDLE_HEIGHT", "HANDLE_LENGTH", "HANDLE_THICKNESS" };

        internal static void Write(IECInstance instance, ActuatorCelAsset asset, string token)
        {
            instance["SSP_CEL_VERSION"].IntValue = 1;
            instance["SSP_CEL_NAME"].StringValue = asset.CellName;
            instance["SSP_CEL_SOURCE"].StringValue = asset.SourcePath;
            instance["SSP_CEL_SHA256"].StringValue = asset.Hash;
            instance["SSP_CEL_DATA"].NativeValue = asset.CopyBytes();
            instance["SSP_CEL_TOKEN"].StringValue = token;
            // Verify the EC container accepts binary bytes before offering the native tool.
            var reread = Read(instance);
            if (reread.Hash != asset.Hash || reread.CellName != asset.CellName)
                throw new InvalidOperationException("执行机构 CEL 属性回读不一致，尚未启动放置。");
            Number(instance, "ANGLE", 0); Number(instance, "HANDLE_OFFSET", 0);
            Number(instance, "LENGTH", 1); Number(instance, "DIAMETER", 1);
            foreach (string name in SizeFields) Number(instance, name, 1);
        }

        internal static ActuatorCelAsset Read(IECInstance instance)
        {
            if (instance == null || instance["SSP_CEL_VERSION"].IntValue != 1)
                throw new InvalidOperationException("执行机构 CEL 数据版本不受支持。");
            var data = instance["SSP_CEL_DATA"].NativeValue as byte[];
            string hash = instance["SSP_CEL_SHA256"].StringValue;
            if (string.IsNullOrEmpty(hash) || hash.Length != 64)
                throw new InvalidOperationException("执行机构缺少 CEL 数据校验值。");
            return new ActuatorCelAsset(data, instance["SSP_CEL_NAME"].StringValue,
                instance["SSP_CEL_SOURCE"].StringValue, hash);
        }

        private static void Number(IECInstance instance, string name, double value)
        {
            var property = instance.ClassDefinition.Properties(true).First(item => item.Name == name);
            if (property.Type.Name.Equals("string", StringComparison.OrdinalIgnoreCase))
                instance[name].StringValue = value.ToString(CultureInfo.InvariantCulture);
            else instance[name].DoubleValue = value;
        }
    }
}
