using System;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;

namespace SteelSectionProbe
{
    /// <summary>
    /// 仅供作者使用的签发器，绝不编译进插件。
    /// </summary>
    internal static class LicenseSigner
    {
        internal static string Issue(string privateKeyPath, string machineCode, string userName,
            bool isTrial = false, int trialDays = 0)
        {
            if ((trialDays != 0 && trialDays != 90) || (!isTrial && trialDays != 0))
            {
                throw new InvalidDataException("试用期限仅支持一个自然月或 90 天。");
            }

            DateTimeOffset issuedUtc = DateTimeOffset.UtcNow;
            var payload = new ActivationPayload
            {
                Version = isTrial ? (trialDays == 90 ? 3 : 2) : 1,
                Product = ActivationCodec.ProductId,
                LicenseId = Guid.NewGuid().ToString("D"),
                MachineCode = isTrial ? ActivationCodec.UnboundMachineCode : ActivationCodec.NormalizeMachineCode(machineCode),
                UserName = (userName ?? string.Empty).Trim(),
                IssuedUtc = issuedUtc.ToString("O", CultureInfo.InvariantCulture),
                Edition = isTrial ? ActivationCodec.TrialEdition : ActivationCodec.PermanentEdition,
                ExpiresUtc = isTrial
                    ? (trialDays == 90 ? issuedUtc.AddDays(90) : issuedUtc.AddMonths(1))
                        .ToString("O", CultureInfo.InvariantCulture)
                    : null,
                TrialDays = trialDays
            };
            ActivationCodec.ValidatePayload(payload);

            using (var rsa = new RSACryptoServiceProvider())
            {
                rsa.PersistKeyInCsp = false;
                rsa.FromXmlString(File.ReadAllText(privateKeyPath, Encoding.UTF8));
                if (rsa.PublicOnly || rsa.KeySize != 2048)
                {
                    throw new InvalidDataException("请选择本产品的 2048 位授权私钥文件。");
                }

                using (Stream stream = Assembly.GetExecutingAssembly()
                    .GetManifestResourceStream("SteelSectionProbe.license_public_key.xml"))
                {
                    if (stream == null)
                    {
                        throw new InvalidDataException("签发工具缺少产品公钥，请重新编译签发工具。");
                    }

                    using (var reader = new StreamReader(stream))
                    using (var verifier = new RSACryptoServiceProvider())
                    {
                        verifier.PersistKeyInCsp = false;
                        verifier.FromXmlString(reader.ReadToEnd());
                        if (rsa.ToXmlString(false) != verifier.ToXmlString(false))
                        {
                            throw new InvalidDataException("此私钥与插件公钥不匹配，请选择原产品私钥。");
                        }
                    }
                }

                byte[] bytes = ActivationCodec.Serialize(payload);
                string code = ActivationCodec.Encode(bytes,
                    rsa.SignData(bytes, CryptoConfig.MapNameToOID("SHA256")));
                ActivationCodec.Verify(code, rsa.ToXmlString(false), payload.MachineCode);
                return code;
            }
        }

        internal static void InitializeKeys(string privateKeyPath, string publicKeyPath)
        {
            // 禁止覆盖已有密钥，否则此前签发的永久激活码会失效。
            if (File.Exists(privateKeyPath) || File.Exists(publicKeyPath))
            {
                throw new IOException("密钥已存在，禁止覆盖。请备份并继续使用原密钥。");
            }

            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(privateKeyPath)));
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(publicKeyPath)));
            using (var rsa = new RSACryptoServiceProvider(2048))
            {
                rsa.PersistKeyInCsp = false;
                var security = new FileSecurity();
                security.SetAccessRuleProtection(true, false);
                security.SetOwner(WindowsIdentity.GetCurrent().User);
                security.AddAccessRule(new FileSystemAccessRule(WindowsIdentity.GetCurrent().User,
                    FileSystemRights.FullControl, AccessControlType.Allow));
                security.AddAccessRule(new FileSystemAccessRule(new SecurityIdentifier(WellKnownSidType.LocalSystemSid, null),
                    FileSystemRights.FullControl, AccessControlType.Allow));
                using (var stream = new FileStream(privateKeyPath, FileMode.CreateNew, FileSystemRights.Write,
                    FileShare.None, 4096, FileOptions.None, security))
                {
                    byte[] bytes = Encoding.UTF8.GetBytes(rsa.ToXmlString(true));
                    stream.Write(bytes, 0, bytes.Length);
                    stream.Flush(true);
                }

                using (var stream = new FileStream(publicKeyPath, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                {
                    byte[] bytes = Encoding.UTF8.GetBytes(rsa.ToXmlString(false));
                    stream.Write(bytes, 0, bytes.Length);
                    stream.Flush(true);
                }
            }
        }
    }
}
