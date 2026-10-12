using System;
using System.IO;
using System.Text;

namespace SteelSectionProbe
{
    /// <summary>
    /// 只保存已签名的激活码，原子替换避免写入失败破坏已有授权。
    /// </summary>
    internal sealed class ActivationStore
    {
        private readonly string filePath;

        internal ActivationStore(string filePath)
        {
            this.filePath = filePath;
        }

        internal string Read()
        {
            if (!File.Exists(filePath))
            {
                return null;
            }

            using (var stream = new FileStream(filePath, FileMode.Open, FileAccess.Read, FileShare.Read))
            {
                if (stream.Length > ActivationCodec.MaximumCodeLength)
                {
                    throw new InvalidDataException("本地授权文件已损坏，请重新输入激活码。");
                }

                using (var reader = new StreamReader(stream, Encoding.UTF8, true))
                {
                    return reader.ReadToEnd();
                }
            }
        }

        internal void Save(string code)
        {
            string normalized = ActivationCodec.NormalizeCode(code);
            string directory = Path.GetDirectoryName(filePath);
            Directory.CreateDirectory(directory);
            string temporaryPath = Path.Combine(directory, Guid.NewGuid().ToString("N") + ".tmp");
            try
            {
                using (var stream = new FileStream(temporaryPath, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                {
                    byte[] bytes = Encoding.UTF8.GetBytes(normalized);
                    stream.Write(bytes, 0, bytes.Length);
                    stream.Flush(true);
                }

                if (File.Exists(filePath))
                {
                    File.Replace(temporaryPath, filePath, null);
                }
                else
                {
                    File.Move(temporaryPath, filePath);
                }
            }
            finally
            {
                if (File.Exists(temporaryPath))
                {
                    File.Delete(temporaryPath);
                }
            }
        }
    }
}
