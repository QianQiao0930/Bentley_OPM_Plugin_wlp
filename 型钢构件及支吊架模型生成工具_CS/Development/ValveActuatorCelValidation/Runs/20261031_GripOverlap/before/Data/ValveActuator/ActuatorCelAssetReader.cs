using System;
using System.IO;
using System.Linq;

namespace SteelSectionProbe
{
    /// <summary>Freezes the chosen disk file, then validates the chosen model in that exact revision.</summary>
    internal static class ActuatorCelAssetReader
    {
        internal static string CacheRoot
        {
            get { return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "SteelSectionProbe", "resources", "ValveActuatorCel"); }
        }

        internal static ActuatorCelAsset Read(CelLibraryEntry selected)
        {
            if (selected == null) throw new InvalidOperationException("请先选择 CEL 文件及库内单元。");
            string path = CelLibraryReader.ValidatePath(selected.LibraryPath);
            byte[] data;
            using (var file = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read))
            {
                if (file.Length <= 0 || file.Length > ActuatorCelAsset.MaxBytes)
                    throw new InvalidOperationException("CEL 文件必须非空，且不大于 16 MiB。");
                data = new byte[(int)file.Length];
                int offset = 0;
                while (offset < data.Length)
                {
                    int read = file.Read(data, offset, data.Length - offset);
                    if (read == 0) throw new IOException("CEL 文件未能完整读取。");
                    offset += read;
                }
            }
            var asset = new ActuatorCelAsset(data, selected.Name, path);
            var revision = CelLibraryReader.Read(asset.Materialize(CacheRoot));
            var entry = revision.Entries.SingleOrDefault(item => item.Name == selected.Name);
            if (entry == null) throw new InvalidOperationException("CEL 文件已变化，所选单元已不存在，请刷新单元库。");
            RequireSupported(entry);
            return asset;
        }

        internal static void RequireSupported(CelLibraryEntry entry)
        {
            // Reuse the verified native-import resolution. Do not silently reinterpret a new library's scale.
            if (!entry.Is3D || entry.IsPointCell || !entry.MasterUnitLabel.Equals("mm", StringComparison.OrdinalIgnoreCase)
                || Math.Abs(entry.UorPerMasterUnit - 1000) > 0.001)
                throw new InvalidOperationException("本轮执行机构支持三维图形单元，源库单位须为 mm、分辨率为 1000 UOR/mm。");
            if (Math.Abs(entry.SourceOriginX) > 0.000001 || Math.Abs(entry.SourceOriginY) > 0.000001 || Math.Abs(entry.SourceOriginZ) > 0.000001)
                throw new InvalidOperationException("本轮执行机构要求源库 GlobalOrigin 为零，请先校核该单元的安装原点。");
        }
    }
}
