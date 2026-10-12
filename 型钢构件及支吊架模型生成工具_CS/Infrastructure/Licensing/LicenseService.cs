using System;
using System.IO;
using System.Reflection;

namespace SteelSectionProbe
{
    /// <summary>
    /// 工作区授权入口。验签仅在首次加载和激活时执行，不进入动态建模循环。
    /// </summary>
    internal static class LicenseService
    {
        internal static bool IsLicensingEnabled
        {
            get
            {
#if ENABLE_LICENSING
                return true;
#else
                return false;
#endif
            }
        }

#if ENABLE_LICENSING
        private static readonly Lazy<LicenseRegistration> Registration =
            new Lazy<LicenseRegistration>(CreateRegistration);
        private static string initializationError;
        private static string machineIdentityError;

        internal static bool IsTrial { get { return Current != null && Current.IsTrial; } }
        internal static string DisplayStatus
        {
            get { return !IsActivated ? "未激活" : IsTrial ? "试用中" : "已激活"; }
        }

        internal static string LicenseDescription
        {
            get
            {
                return !IsActivated ? StatusMessage : "授权用户：" + UserName + " · " +
                    (IsTrial ? "到期：" + LicenseValidity.ExpiresAt(Current.License).ToLocalTime()
                        .ToString("yyyy-MM-dd HH:mm") : "永久授权") + " · 全部功能";
            }
        }

        internal static bool IsActivated
        {
            get { return Current != null && Current.IsActivated; }
        }

        internal static string MachineCode
        {
            get { return Current == null ? string.Empty : Current.MachineCode; }
        }

        internal static string UserName
        {
            get { return IsActivated ? Current.License.UserName : string.Empty; }
        }

        internal static string StatusMessage
        {
            get
            {
                return Current == null ? initializationError : Current.StatusMessage +
                    (!IsActivated && !string.IsNullOrEmpty(machineIdentityError) ? " " + machineIdentityError : string.Empty);
            }
        }

        internal static void Activate(string code)
        {
            if (Current == null)
            {
                throw new InvalidOperationException(initializationError);
            }

            Current.Activate(code);
        }

        private static LicenseRegistration Current { get { return Registration.Value; } }

        private static LicenseRegistration CreateRegistration()
        {
            try
            {
                string publicKey;
                using (Stream stream = Assembly.GetExecutingAssembly()
                    .GetManifestResourceStream("SteelSectionProbe.license_public_key.xml"))
                {
                    if (stream == null)
                    {
                        throw new InvalidDataException("缺少授权公钥，请联系软件作者。");
                    }

                    using (var reader = new StreamReader(stream))
                    {
                        publicKey = reader.ReadToEnd();
                    }
                }

                string filePath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "SteelSectionProbe", "license", "activation.txt");
                string machineCode;
                try
                {
                    machineCode = MachineIdentity.ReadMachineCode();
                }
                catch (Exception exception) when (exception is IOException || exception is InvalidDataException ||
                    exception is UnauthorizedAccessException || exception is System.Security.SecurityException)
                {
                    machineCode = string.Empty;
                    machineIdentityError = "无法读取机器码：" + exception.Message + "；仍可使用免机器码的试用授权。";
                }

                var registration = new LicenseRegistration(publicKey, machineCode,
                    new ActivationStore(filePath));
                registration.Load();
                return registration;
            }
            catch (Exception exception) when (exception is IOException || exception is InvalidDataException ||
                exception is System.Xml.XmlException || exception is UnauthorizedAccessException ||
                exception is System.Security.SecurityException || exception is System.Security.Cryptography.CryptographicException)
            {
                initializationError = "无法初始化授权：" + exception.Message;
                return null;
            }
        }
#else
        // 无授权构建不读取机器标识或授权文件，也不执行到期检查。
        internal static bool IsActivated { get { return true; } }
        internal static bool IsTrial { get { return false; } }
        internal static string DisplayStatus { get { return "无需激活"; } }
        internal static string LicenseDescription { get { return "无授权版 · 全部功能"; } }
        internal static string StatusMessage { get { return LicenseDescription; } }
#endif
    }
}
