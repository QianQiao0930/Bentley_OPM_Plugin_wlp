using System;
using System.IO;
using System.Security.Cryptography;

namespace SteelSectionProbe
{
    /// <summary>An immutable CEL library revision and one selected model, independent of UI state.</summary>
    internal sealed class ActuatorCelAsset
    {
        internal const int MaxBytes = 16 * 1024 * 1024;
        private readonly byte[] bytes;
        internal string CellName { get; private set; }
        internal string SourcePath { get; private set; }
        internal string Hash { get; private set; }
        internal int ByteCount { get { return bytes.Length; } }

        internal ActuatorCelAsset(byte[] data, string cellName, string sourcePath, string expectedHash = null)
        {
            if (data == null || data.Length == 0 || data.Length > MaxBytes)
                throw new InvalidOperationException("CEL 文件必须非空，且不大于 16 MiB。");
            if (string.IsNullOrWhiteSpace(cellName)) throw new InvalidOperationException("请选择库内三维单元。");
            bytes = (byte[])data.Clone();
            Hash = ComputeHash(bytes);
            if (expectedHash != null && !string.Equals(Hash, expectedHash, StringComparison.Ordinal))
                throw new InvalidOperationException("执行机构保存的 CEL 数据与校验值不一致。");
            CellName = cellName;
            SourcePath = sourcePath ?? string.Empty;
        }

        internal byte[] CopyBytes() { return (byte[])bytes.Clone(); }

        internal static string ComputeHash(byte[] data)
        {
            using (var sha = SHA256.Create()) return BitConverter.ToString(sha.ComputeHash(data)).Replace("-", "");
        }

        internal string Materialize(string root)
        {
            string directory = Path.Combine(root, Hash);
            Directory.CreateDirectory(directory);
            string path = Path.Combine(directory, "library.cel");
            if (!File.Exists(path))
            {
                // Finish the entire write before exposing the canonical immutable file.
                string temporary = Path.Combine(directory, Guid.NewGuid().ToString("N") + ".tmp");
                try
                {
                    using (var file = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                        file.Write(bytes, 0, bytes.Length);
                    try { File.Move(temporary, path); }
                    catch (IOException) { if (!File.Exists(path)) throw; }
                }
                finally { if (File.Exists(temporary)) File.Delete(temporary); }
            }
            using (var file = File.OpenRead(path))
            using (var sha = SHA256.Create())
                if (BitConverter.ToString(sha.ComputeHash(file)).Replace("-", "") != Hash)
                    throw new InvalidOperationException("CEL 本地缓存校验失败：" + path);
            return path;
        }
    }
}
