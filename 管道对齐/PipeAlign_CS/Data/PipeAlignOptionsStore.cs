using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text;

namespace PipeAlign
{
    /// <summary>
    /// 运行参数的读写（开发指南 §11：容差写入配置，不写死在业务代码里）。
    /// <para>
    /// 查找顺序：
    /// 1. DLL 同目录的 <c>PipeAlign.options.txt</c>（随插件一起分发，项目统一口径用这个）；
    /// 2. <c>%LOCALAPPDATA%\PipeAlign\PipeAlign.options.txt</c>（单个用户覆盖）。
    /// </para>
    /// <para>文件不存在时使用内置默认值，并且**不报错** —— 缺配置不是故障。</para>
    /// </summary>
    internal static class PipeAlignOptionsStore
    {
        internal static string AssemblyDirectoryPath
        {
            get
            {
                try
                {
                    string location = Assembly.GetExecutingAssembly().Location;
                    if (!string.IsNullOrEmpty(location)) return Path.GetDirectoryName(location);
                }
                catch
                {
                }
                return null;
            }
        }

        internal static string UserDirectoryPath
        {
            get
            {
                return Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "PipeAlign");
            }
        }

        internal static string AssemblyFilePath
        {
            get
            {
                string directory = AssemblyDirectoryPath;
                return directory == null ? null : Path.Combine(directory, PipeAlignOptions.FileName);
            }
        }

        internal static string UserFilePath
        {
            get { return Path.Combine(UserDirectoryPath, PipeAlignOptions.FileName); }
        }

        /// <summary>实际生效的配置文件路径（都不存在时返回用户路径，写回时用它）。</summary>
        internal static string ResolveExistingPath()
        {
            string user = UserFilePath;
            if (File.Exists(user)) return user;
            string assembly = AssemblyFilePath;
            if (assembly != null && File.Exists(assembly)) return assembly;
            return user;
        }

        /// <summary>读取配置。返回的 <paramref name="warnings"/> 里是需要提示用户的中文说明。</summary>
        internal static PipeAlignOptions Load(out string loadedFrom, out IList<string> warnings)
        {
            List<string> collected = new List<string>();
            warnings = collected;
            loadedFrom = null;

            string path = null;
            try
            {
                string user = UserFilePath;
                string assembly = AssemblyFilePath;
                if (File.Exists(user)) path = user;
                else if (assembly != null && File.Exists(assembly)) path = assembly;
            }
            catch (Exception ex)
            {
                collected.Add("查找配置文件失败：" + ex.Message);
            }

            if (path == null) return new PipeAlignOptions();

            try
            {
                string text = File.ReadAllText(path, Encoding.UTF8);
                loadedFrom = path;
                return PipeAlignOptions.Parse(text, collected);
            }
            catch (Exception ex)
            {
                collected.Add("读取配置文件失败（" + path + "）：" + ex.Message);
                return new PipeAlignOptions();
            }
        }

        /// <summary>
        /// 把当前设置写回配置文件（<c>PIPEALIGN OPTIONS</c>）。返回实际写入的路径。
        /// </summary>
        internal static string Save(PipeAlignOptions options)
        {
            if (options == null) throw new ArgumentNullException("options");
            string directory = UserDirectoryPath;
            if (!Directory.Exists(directory)) Directory.CreateDirectory(directory);
            string path = UserFilePath;
            File.WriteAllText(path, options.Serialize(), new UTF8Encoding(false));
            return path;
        }
    }
}
