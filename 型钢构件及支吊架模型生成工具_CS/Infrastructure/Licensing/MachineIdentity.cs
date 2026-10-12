using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using Microsoft.Win32;

namespace SteelSectionProbe
{
    /// <summary>
    /// 用 Windows 安装标识派生机器码，不暴露注册表原值。
    /// 重装系统后可能变化；同一系统内升级插件不改变机器码。
    /// </summary>
    internal static class MachineIdentity
    {
        internal static string ReadMachineCode()
        {
            string installationId;
            using (RegistryKey root = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64))
            using (RegistryKey key = root.OpenSubKey(@"SOFTWARE\Microsoft\Cryptography"))
            {
                installationId = key == null ? null : key.GetValue("MachineGuid") as string;
            }

            Guid parsedId;
            if (!Guid.TryParse(installationId, out parsedId) || parsedId == Guid.Empty)
            {
                throw new InvalidDataException("无法读取本机安装标识，请检查 Windows 注册表读取权限。");
            }

            using (SHA256 sha256 = SHA256.Create())
            {
                byte[] digest = sha256.ComputeHash(Encoding.UTF8.GetBytes(
                    ActivationCodec.ProductId + ":" + parsedId.ToString("D")));
                string hex = BitConverter.ToString(digest, 0, 16).Replace("-", string.Empty);
                return "SSP-" + hex.Substring(0, 8) + "-" + hex.Substring(8, 8) + "-" +
                    hex.Substring(16, 8) + "-" + hex.Substring(24, 8);
            }
        }
    }
}
