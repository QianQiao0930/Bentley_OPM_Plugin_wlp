using System;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Runtime.Serialization;
using System.Runtime.Serialization.Json;
using System.Security.Cryptography;
using System.Text.RegularExpressions;

namespace SteelSectionProbe
{
    /// <summary>
    /// 校验离线激活码。只含公钥验签能力，签发逻辑仅在独立开发工具中。
    /// </summary>
    internal static class ActivationCodec
    {
        internal const string ProductId = "SteelSectionProbe";
        internal const string PermanentEdition = "FullPermanent";
        internal const string TrialEdition = "FullTrial";
        internal const string UnboundMachineCode = "*";
        internal const int MaximumCodeLength = 8192;
        private const string CodePrefix = "SSP1";

        internal static byte[] Serialize(ActivationPayload payload)
        {
            using (var stream = new MemoryStream())
            {
                new DataContractJsonSerializer(typeof(ActivationPayload)).WriteObject(stream, payload);
                return stream.ToArray();
            }
        }

        internal static string Encode(byte[] payload, byte[] signature)
        {
            return CodePrefix + "." + ToBase64Url(payload) + "." + ToBase64Url(signature);
        }

        internal static string NormalizeCode(string code)
        {
            if (string.IsNullOrWhiteSpace(code) || code.Length > MaximumCodeLength)
            {
                throw new InvalidDataException("请粘贴完整激活码，长度不能超过 8192 个字符。");
            }

            return new string(code.Where(character => !char.IsWhiteSpace(character)).ToArray());
        }

        internal static string NormalizeMachineCode(string machineCode)
        {
            string normalized = (machineCode ?? string.Empty).Trim().ToUpperInvariant();
            if (!Regex.IsMatch(normalized, @"\ASSP(?:-[0-9A-F]{8}){4}\z"))
            {
                throw new InvalidDataException("机器码格式不正确，请完整复制程序显示的机器码。");
            }

            return normalized;
        }

        internal static ActivationPayload Verify(string code, string publicKey, string machineCode)
        {
            string[] parts = NormalizeCode(code).Split('.');
            if (parts.Length != 3 || parts[0] != CodePrefix)
            {
                throw new InvalidDataException("激活码格式不正确，请完整复制激活码。");
            }

            byte[] payloadBytes = FromBase64Url(parts[1]);
            byte[] signature = FromBase64Url(parts[2]);
            if (payloadBytes.Length == 0 || payloadBytes.Length > 4096 || signature.Length != 256)
            {
                throw new InvalidDataException("激活码内容不完整或已损坏。");
            }

            using (var rsa = new RSACryptoServiceProvider())
            {
                rsa.PersistKeyInCsp = false;
                rsa.FromXmlString(publicKey);
                if (!rsa.PublicOnly || rsa.KeySize != 2048)
                {
                    throw new InvalidDataException("授权公钥配置不正确。");
                }

                // 先验证原始字节的签名，再解析载荷，不能重新序列化后验签。
                if (!rsa.VerifyData(payloadBytes, CryptoConfig.MapNameToOID("SHA256"), signature))
                {
                    throw new InvalidDataException("激活码签名无效，请核对或联系软件作者重新签发。");
                }
            }

            ActivationPayload payload;
            try
            {
                using (var stream = new MemoryStream(payloadBytes, false))
                {
                    payload = (ActivationPayload)new DataContractJsonSerializer(typeof(ActivationPayload))
                        .ReadObject(stream);
                }
            }
            catch (SerializationException exception)
            {
                throw new InvalidDataException("激活码内容无法识别。", exception);
            }

            ValidatePayload(payload);
            if (payload.Edition == PermanentEdition &&
                !string.Equals(payload.MachineCode, NormalizeMachineCode(machineCode), StringComparison.Ordinal))
            {
                throw new InvalidDataException("此激活码不属于当前电脑，请使用本机机器码申请激活。");
            }

            return payload;
        }

        internal static void ValidatePayload(ActivationPayload payload)
        {
            Guid licenseId;
            DateTimeOffset issuedUtc;
            if (payload == null || payload.Product != ProductId || !Guid.TryParse(payload.LicenseId, out licenseId) ||
                licenseId == Guid.Empty || string.IsNullOrWhiteSpace(payload.UserName) ||
                payload.UserName.Length > 100 || payload.UserName.Any(char.IsControl) ||
                !DateTimeOffset.TryParseExact(payload.IssuedUtc, "O", CultureInfo.InvariantCulture,
                    DateTimeStyles.None, out issuedUtc) || issuedUtc.Offset != TimeSpan.Zero)
            {
                throw new InvalidDataException("激活码的授权信息不正确或不适用于本程序。");
            }

            if (payload.Edition == TrialEdition)
            {
                DateTimeOffset expiresUtc;
                bool isMonthlyTrial = payload.Version == 2 && payload.TrialDays == 0;
                bool isNinetyDayTrial = payload.Version == 3 && payload.TrialDays == 90;
                if ((!isMonthlyTrial && !isNinetyDayTrial) || payload.MachineCode != UnboundMachineCode ||
                    !DateTimeOffset.TryParseExact(payload.ExpiresUtc, "O", CultureInfo.InvariantCulture,
                        DateTimeStyles.None, out expiresUtc) || expiresUtc.Offset != TimeSpan.Zero ||
                    issuedUtc.Year >= 9999 ||
                    expiresUtc != (isNinetyDayTrial ? issuedUtc.AddDays(90) : issuedUtc.AddMonths(1)))
                {
                    throw new InvalidDataException("试用授权必须从签发时刻起有效一个自然月或 90 天，且不绑定机器。");
                }

                return;
            }

            if (payload.Version != 1 || payload.Edition != PermanentEdition || payload.TrialDays != 0 || !string.IsNullOrEmpty(payload.ExpiresUtc))
            {
                throw new InvalidDataException("激活码的授权类型不正确。");
            }

            if (NormalizeMachineCode(payload.MachineCode) != payload.MachineCode)
            {
                throw new InvalidDataException("激活码中的机器码不正确。");
            }
        }

        private static string ToBase64Url(byte[] bytes)
        {
            return Convert.ToBase64String(bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_');
        }

        private static byte[] FromBase64Url(string value)
        {
            if (value.Length == 0 || !Regex.IsMatch(value, @"\A[A-Za-z0-9_-]+\z") || value.Length % 4 == 1)
            {
                throw new InvalidDataException("激活码编码不正确。");
            }

            try
            {
                string padded = value.Replace('-', '+').Replace('_', '/');
                padded = padded.PadRight((padded.Length + 3) / 4 * 4, '=');
                byte[] bytes = Convert.FromBase64String(padded);
                if (ToBase64Url(bytes) != value)
                {
                    throw new InvalidDataException("激活码编码不规范。");
                }

                return bytes;
            }
            catch (FormatException exception)
            {
                throw new InvalidDataException("激活码编码不正确。", exception);
            }
        }
    }
}
