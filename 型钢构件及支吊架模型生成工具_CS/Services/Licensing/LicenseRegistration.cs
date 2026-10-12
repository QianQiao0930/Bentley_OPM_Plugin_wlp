using System;
using System.IO;
using System.Security.Cryptography;

namespace SteelSectionProbe
{
    /// <summary>
    /// 一次加载并缓存授权结果。新的激活码必须验签且保存成功才替换当前授权。
    /// </summary>
    internal sealed class LicenseRegistration
    {
        private readonly string publicKey;
        private readonly ActivationStore store;
        private readonly Func<DateTimeOffset> utcClock;
        private string loadMessage;

        internal LicenseRegistration(string publicKey, string machineCode, ActivationStore store,
            Func<DateTimeOffset> utcClock = null)
        {
            this.publicKey = publicKey;
            this.store = store;
            this.utcClock = utcClock ?? (() => DateTimeOffset.UtcNow);
            MachineCode = string.IsNullOrEmpty(machineCode) ? string.Empty : ActivationCodec.NormalizeMachineCode(machineCode);
            loadMessage = "尚未激活，可向作者申请永久激活码或一个月试用码。";
        }

        internal string MachineCode { get; private set; }
        internal ActivationPayload License { get; private set; }
        internal bool IsActivated { get { return LicenseValidity.IsActive(License, utcClock()); } }
        internal bool IsTrial { get { return License != null && License.Edition == ActivationCodec.TrialEdition; } }
        internal string StatusMessage
        {
            get
            {
                if (License == null)
                {
                    return loadMessage;
                }

                if (!IsTrial)
                {
                    return "已激活，全部功能已开放（永久授权）。";
                }

                if (utcClock() < LicenseValidity.IssuedAt(License))
                {
                    return "系统时间早于试用码签发时间，请校准系统日期。";
                }

                return IsActivated ? "试用中，全部功能已开放；到期：" +
                    LicenseValidity.ExpiresAt(License).ToLocalTime().ToString("yyyy-MM-dd HH:mm") :
                    "试用已到期，当前为未激活状态，请联系作者申请授权。";
            }
        }

        internal void Load()
        {
            License = null;
            try
            {
                string code = store.Read();
                if (code != null)
                {
                    License = ActivationCodec.Verify(code, publicKey, MachineCode);
                }

                loadMessage = "尚未激活，可向作者申请永久激活码或一个月试用码。";
            }
            catch (Exception exception) when (exception is IOException || exception is InvalidDataException ||
                exception is System.Xml.XmlException || exception is UnauthorizedAccessException ||
                exception is CryptographicException || exception is System.Security.SecurityException)
            {
                loadMessage = "本地授权未通过验证：" + exception.Message;
            }
        }

        internal void Activate(string code)
        {
            ActivationPayload verified = ActivationCodec.Verify(code, publicKey, MachineCode);
            LicenseValidity.RequireActive(verified, utcClock());
            if (IsActivated && !IsTrial && verified.Edition == ActivationCodec.TrialEdition)
            {
                throw new InvalidDataException("本机已拥有永久授权，无需导入试用码。");
            }

            store.Save(code);
            License = verified;
        }
    }
}
