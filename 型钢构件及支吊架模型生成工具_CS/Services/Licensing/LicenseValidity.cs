using System;
using System.Globalization;
using System.IO;

namespace SteelSectionProbe
{
    /// <summary>
    /// 使用已验签的载荷判断授权是否有效；试用期为签发时刻到一个月后的半开区间。
    /// </summary>
    internal static class LicenseValidity
    {
        internal static DateTimeOffset IssuedAt(ActivationPayload license)
        {
            return DateTimeOffset.ParseExact(license.IssuedUtc, "O", CultureInfo.InvariantCulture);
        }

        internal static DateTimeOffset ExpiresAt(ActivationPayload license)
        {
            return DateTimeOffset.ParseExact(license.ExpiresUtc, "O", CultureInfo.InvariantCulture);
        }

        internal static bool IsActive(ActivationPayload license, DateTimeOffset utcNow)
        {
            if (license == null)
            {
                return false;
            }

            if (license.Edition == ActivationCodec.PermanentEdition)
            {
                return true;
            }

            return license.Edition == ActivationCodec.TrialEdition &&
                utcNow >= IssuedAt(license) && utcNow < ExpiresAt(license);
        }

        internal static void RequireActive(ActivationPayload license, DateTimeOffset utcNow)
        {
            if (!IsActive(license, utcNow))
            {
                throw new InvalidDataException(utcNow < IssuedAt(license) ?
                    "系统时间早于试用码签发时间，请先校准系统日期。" :
                    "此试用码已到期，请联系作者申请新授权。");
            }
        }
    }
}
