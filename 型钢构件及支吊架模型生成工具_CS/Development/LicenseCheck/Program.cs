using System;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;

namespace SteelSectionProbe
{
    internal static class Program
    {
        private const string MachineCode = "SSP-01234567-89ABCDEF-01234567-89ABCDEF";
        private const string OtherMachine = "SSP-00000000-89ABCDEF-01234567-89ABCDEF";
        private static int checks;

        private static int Main(string[] args)
        {
            string temporaryDirectory = Path.Combine(AppDomain.CurrentDomain.BaseDirectory,
                "SteelSupportLicenseCheck-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(temporaryDirectory);
            try
            {
                using (var signer = new RSACryptoServiceProvider(2048))
                using (var otherSigner = new RSACryptoServiceProvider(2048))
                {
                    signer.PersistKeyInCsp = false;
                    otherSigner.PersistKeyInCsp = false;
                    string publicKey = signer.ToXmlString(false);
                    ActivationPayload payload = NewPayload();
                    string code = Sign(signer, payload);
                    Check(ActivationCodec.Verify(code, publicKey, MachineCode).UserName == "测试用户", "有效激活码");
                    Check(ActivationCodec.Verify(" \r\n" + code.Replace(".", ".\n") + "\t", publicKey, MachineCode) != null,
                        "允许粘贴换行空格");
                    Reject(() => ActivationCodec.Verify(code, publicKey, OtherMachine), "拒绝跨机器");
                    Reject(() => ActivationCodec.Verify(code, otherSigner.ToXmlString(false), MachineCode), "拒绝其他公钥");
                    Reject(() => ActivationCodec.Verify(code, signer.ToXmlString(true), MachineCode), "验证端不能加载私钥");

                    string[] parts = code.Split('.');
                    byte[] changedPayload = ActivationCodec.Serialize(NewPayload());
                    changedPayload[changedPayload.Length / 2] ^= 1;
                    Reject(() => ActivationCodec.Verify(ActivationCodec.Encode(changedPayload, Decode(parts[2])), publicKey, MachineCode),
                        "拒绝载荷篡改");
                    byte[] changedSignature = Decode(parts[2]);
                    changedSignature[0] ^= 1;
                    Reject(() => ActivationCodec.Verify(ActivationCodec.Encode(Decode(parts[1]), changedSignature), publicKey, MachineCode),
                        "拒绝签名篡改");
                    foreach (string invalid in new[] { "", "SSP1", code + ".extra", code.Substring(0, code.Length - 5),
                        code.Replace("SSP1", "SSP2"), "SSP1.!.!", new string('A', 8193) })
                    {
                        Reject(() => ActivationCodec.Verify(invalid, publicKey, MachineCode), "拒绝无效格式");
                    }

                    AssertInvalidPayload(signer, publicKey, value => value.Version = 2, "版本");
                    AssertInvalidPayload(signer, publicKey, value => value.Product = "OtherProduct", "产品");
                    AssertInvalidPayload(signer, publicKey, value => value.Edition = "Trial", "授权范围");
                    AssertInvalidPayload(signer, publicKey, value => value.LicenseId = "invalid", "授权编号");
                    AssertInvalidPayload(signer, publicKey, value => value.LicenseId = Guid.Empty.ToString(), "空授权编号");
                    AssertInvalidPayload(signer, publicKey, value => value.UserName = " ", "空用户");
                    AssertInvalidPayload(signer, publicKey, value => value.UserName = "User\nName", "用户控制字符");
                    AssertInvalidPayload(signer, publicKey, value => value.UserName = new string('中', 101), "过长用户");
                    AssertInvalidPayload(signer, publicKey, value => value.IssuedUtc = "invalid", "签发日期");
                    AssertInvalidPayload(signer, publicKey, value => value.MachineCode = "bad", "机器码");

                    // 永久授权不因客户端时钟倒退或多年后的日期而过期。
                    payload.IssuedUtc = new DateTimeOffset(2000, 1, 1, 0, 0, 0, TimeSpan.Zero).ToString("O");
                    Check(ActivationCodec.Verify(Sign(signer, payload), publicKey, MachineCode) != null, "永久授权没有到期检查");
                    string storagePath = Path.Combine(temporaryDirectory, "license", "activation.txt");
                    var store = new ActivationStore(storagePath);
                    var registration = new LicenseRegistration(publicKey, MachineCode, store);
                    registration.Load();
                    Check(!registration.IsActivated, "首次运行未激活");
                    registration.Activate(code);
                    Check(registration.IsActivated && File.ReadAllText(storagePath) == code, "激活并落盘");
                    string licenseId = registration.License.LicenseId;
                    Reject(() => registration.Activate("invalid"), "错误码激活失败");
                    Check(registration.IsActivated && registration.License.LicenseId == licenseId && store.Read() == code,
                        "错误码保留已有授权");
                    using (var lockedFile = new FileStream(storagePath, FileMode.Open, FileAccess.Read, FileShare.Read))
                    {
                        Reject(() => registration.Activate(Sign(signer, NewPayload())), "授权文件被占用时保存失败");
                    }

                    Check(registration.IsActivated && registration.License.LicenseId == licenseId && store.Read() == code,
                        "保存失败保留已有授权及文件");
                    payload = NewPayload();
                    payload.UserName = "第二位测试用户";
                    registration.Activate(Sign(signer, payload));
                    Check(registration.License.UserName == payload.UserName, "已有授权原子替换");
                    var restarted = new LicenseRegistration(publicKey, MachineCode, store);
                    restarted.Load();
                    Check(restarted.IsActivated && restarted.License.UserName == payload.UserName, "重启自动读取");
                    var moved = new LicenseRegistration(publicKey, OtherMachine, store);
                    moved.Load();
                    Check(!moved.IsActivated && moved.StatusMessage.Contains("不属于"), "复制授权文件无法激活另一台电脑");
                    File.WriteAllText(storagePath, "corrupt");
                    restarted.Load();
                    Check(!restarted.IsActivated && restarted.StatusMessage.Contains("未通过"), "损坏文件保持未激活");
                    File.WriteAllText(storagePath, new string('A', 9000));
                    restarted.Load();
                    Check(!restarted.IsActivated, "拒绝超大授权文件");
                    Check(Directory.GetFiles(Path.GetDirectoryName(storagePath), "*.tmp").Length == 0, "清理临时文件");

                    // 用真实拒写场景验证保存失败后不能解锁。
                    string blockedPath = Path.Combine(temporaryDirectory, "blocked.txt");
                    File.WriteAllText(blockedPath, "blocking parent directory");
                    var blocked = new LicenseRegistration(publicKey, MachineCode,
                        new ActivationStore(Path.Combine(blockedPath, "activation.txt")));
                    Reject(() => blocked.Activate(code), "保存失败");
                    Check(!blocked.IsActivated, "保存失败不能解锁");
                    CheckTrialLicenses(signer, publicKey, temporaryDirectory);
                    CheckNinetyDayTrial(signer, publicKey, temporaryDirectory);
                }

                Check(MachineIdentity.ReadMachineCode() == MachineIdentity.ReadMachineCode(), "本机机器码稳定");
                if (args.Length >= 2)
                {
                    // 用作者实际密钥验证签发器与嵌入公钥的配对；仅在临时目录保存测试码。
                    string code = LicenseSigner.Issue(args[0], MachineCode, "签发器自检");
                    string publicKey = File.ReadAllText(args[1]);
                    Check(ActivationCodec.Verify(code, publicKey, MachineCode).UserName == "签发器自检", "实际签发器与产品公钥匹配");
                    string trialCode = LicenseSigner.Issue(args[0], string.Empty, "试用签发自检", true);
                    ActivationPayload trial = ActivationCodec.Verify(trialCode, publicKey, OtherMachine);
                    Check(trial.Edition == ActivationCodec.TrialEdition && trial.MachineCode == "*",
                        "实际签发器生成免机器码试用授权");
                    Check(LicenseValidity.ExpiresAt(trial) == LicenseValidity.IssuedAt(trial).AddMonths(1),
                        "实际试用签发日期到期日相差一个自然月");
                    ActivationPayload ninetyDayTrial = ActivationCodec.Verify(
                        LicenseSigner.Issue(args[0], string.Empty, "90 天签发自检", true, 90), publicKey, OtherMachine);
                    Check(ninetyDayTrial.Version == 3 && ninetyDayTrial.TrialDays == 90,
                        "实际签发器生成 90 天试用码");
                    Check(LicenseValidity.ExpiresAt(ninetyDayTrial) == LicenseValidity.IssuedAt(ninetyDayTrial).AddDays(90),
                        "实际 90 天试用码从签发时刻计时");
                    Reject(() => LicenseSigner.Issue(args[0], MachineCode, "错误期限", true, 30), "不支持任意试用期限");
                    Reject(() => LicenseSigner.Issue(args[0], MachineCode, "错误永久期限", false, 90), "永久码不能设置试用期限");
                    string publicOnlyPath = Path.Combine(temporaryDirectory, "public-key.xml");
                    File.WriteAllText(publicOnlyPath, publicKey);
                    Reject(() => LicenseSigner.Issue(publicOnlyPath, MachineCode, "签发器自检"), "公钥无法签发");
                    using (var otherSigner = new RSACryptoServiceProvider(2048))
                    {
                        otherSigner.PersistKeyInCsp = false;
                        string wrongKeyPath = Path.Combine(temporaryDirectory, "wrong-private.xml");
                        File.WriteAllText(wrongKeyPath, otherSigner.ToXmlString(true));
                        Reject(() => LicenseSigner.Issue(wrongKeyPath, MachineCode, "签发器自检"), "签发器拒绝不配对私钥");
                    }
                }

                if (args.Length >= 3)
                {
                    Assembly plugin = Assembly.LoadFrom(Path.GetFullPath(args[2]));
                    Check(plugin.GetType("SteelSectionProbe.LicenseSigner", false) == null,
                        "客户端不包含签发器");
                    using (Stream stream = plugin.GetManifestResourceStream("SteelSectionProbe.license_public_key.xml"))
                    using (var reader = new StreamReader(stream))
                    {
                        string embeddedKey = reader.ReadToEnd();
                        Check(embeddedKey == File.ReadAllText(args[1]), "客户端公钥与签发公钥一致");
                        Check(!embeddedKey.Contains("<D>") && !embeddedKey.Contains("<P>") &&
                            !embeddedKey.Contains("<Q>"), "客户端资源只含公钥");
                    }

                    Type service = plugin.GetType("SteelSectionProbe.LicenseService", true);
                    Check((bool)service.GetProperty("IsLicensingEnabled", BindingFlags.NonPublic | BindingFlags.Static)
                        .GetValue(null, null), "默认构建启用授权");
                    string actualMachineCode = (string)service.GetProperty("MachineCode",
                        BindingFlags.NonPublic | BindingFlags.Static).GetValue(null, null);
                    Check(actualMachineCode == MachineIdentity.ReadMachineCode(), "实际插件授权初始化读取本机身份");
                    Check(service.GetProperty("IsActivated", BindingFlags.NonPublic | BindingFlags.Static)
                        .GetValue(null, null) is bool, "实际插件授权状态能够读取");
                }

                if (args.Length >= 4)
                {
                    // LoadFile 允许检查同名程序集的另一种构建，避免复用授权版实例。
                    Assembly unlicensed = Assembly.LoadFile(Path.GetFullPath(args[3]));
                    Type service = unlicensed.GetType("SteelSectionProbe.LicenseService", true);
                    const BindingFlags flags = BindingFlags.NonPublic | BindingFlags.Static;
                    Check(!(bool)service.GetProperty("IsLicensingEnabled", flags).GetValue(null, null),
                        "无授权版编译开关关闭");
                    Check((bool)service.GetProperty("IsActivated", flags).GetValue(null, null),
                        "无授权版无需文件即可开放业务入口");
                    Check(!(bool)service.GetProperty("IsTrial", flags).GetValue(null, null),
                        "无授权版不会触发试用到期退出");
                    Check(service.GetProperty("MachineCode", flags) == null, "无授权版不读取机器码");
                    foreach (string name in new[] { "ActivationPage", "ActivationCodec", "LicenseRegistration",
                        "LicenseValidity", "MachineIdentity", "ActivationStore", "LicenseSigner" })
                    {
                        Check(unlicensed.GetType("SteelSectionProbe." + name, false) == null,
                            "无授权版不包含 " + name);
                    }

                    using (Stream stream = unlicensed.GetManifestResourceStream("SteelSectionProbe.license_public_key.xml"))
                    {
                        Check(stream == null, "无授权版不嵌入授权公钥");
                    }
                }

                Console.WriteLine("PASS: " + checks + " licensing checks.");
                return 0;
            }
            catch (Exception exception)
            {
                Console.Error.WriteLine(exception);
                return 1;
            }
            finally
            {
                Directory.Delete(temporaryDirectory, true);
            }
        }

        private static ActivationPayload NewPayload()
        {
            return new ActivationPayload
            {
                Version = 1,
                Product = ActivationCodec.ProductId,
                LicenseId = Guid.NewGuid().ToString("D"),
                MachineCode = MachineCode,
                UserName = "测试用户",
                IssuedUtc = DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture),
                Edition = ActivationCodec.PermanentEdition
            };
        }

        private static void CheckTrialLicenses(RSACryptoServiceProvider signer, string publicKey, string temporaryDirectory)
        {
            foreach (DateTimeOffset issuedUtc in new[]
            {
                new DateTimeOffset(2026, 10, 11, 12, 0, 0, TimeSpan.Zero),
                new DateTimeOffset(2026, 1, 31, 12, 0, 0, TimeSpan.Zero),
                new DateTimeOffset(2028, 1, 31, 12, 0, 0, TimeSpan.Zero),
                new DateTimeOffset(2026, 12, 31, 12, 0, 0, TimeSpan.Zero)
            })
            {
                ActivationPayload trial = NewTrial(issuedUtc);
                string code = Sign(signer, trial);
                Check(ActivationCodec.Verify(code, publicKey, MachineCode).Edition == ActivationCodec.TrialEdition,
                    "本机试用签名有效");
                Check(ActivationCodec.Verify(code, publicKey, OtherMachine).LicenseId == trial.LicenseId,
                    "同一试用码可用于不同电脑");
                Check(ActivationCodec.Verify(code, publicKey, string.Empty).LicenseId == trial.LicenseId,
                    "无机器码也能校验试用");
                Check(!LicenseValidity.IsActive(trial, issuedUtc.AddTicks(-1)), "签发前未启用");
                Check(LicenseValidity.IsActive(trial, issuedUtc), "签发瞬间生效");
                DateTimeOffset expires = issuedUtc.AddMonths(1);
                Check(LicenseValidity.IsActive(trial, expires.AddTicks(-1)), "到期前仍有效");
                Check(!LicenseValidity.IsActive(trial, expires), "到期瞬间失效");
                Check(!LicenseValidity.IsActive(trial, expires.AddDays(1)), "到期后失效");
                Check(LicenseValidity.ExpiresAt(trial) == expires, "月底闰年跨年按自然月计算");
            }

            DateTimeOffset signedAt = new DateTimeOffset(2026, 10, 11, 12, 0, 0, TimeSpan.Zero);
            DateTimeOffset clock = signedAt.AddDays(10);
            ActivationPayload payload = NewTrial(signedAt);
            string validCode = Sign(signer, payload);
            string path = Path.Combine(temporaryDirectory, "trial", "activation.txt");
            var store = new ActivationStore(path);
            var registration = new LicenseRegistration(publicKey, OtherMachine, store, () => clock);
            registration.Activate(validCode);
            Check(registration.IsActivated && registration.IsTrial, "导入通用试用码解锁全部功能");
            var restarted = new LicenseRegistration(publicKey, string.Empty, store, () => clock);
            restarted.Load();
            Check(restarted.IsActivated && restarted.IsTrial, "试用重启加载不要求机器码");
            clock = signedAt.AddMonths(1);
            Check(!registration.IsActivated && registration.StatusMessage.Contains("未激活"), "已缓存试用无需重启即可到期");
            Reject(() => registration.Activate(validCode), "重新导入旧码不能延长试用");
            restarted.Load();
            Check(!restarted.IsActivated && restarted.StatusMessage.Contains("到期"), "到期重启仍未激活");
            clock = signedAt.AddSeconds(-1);
            Reject(() => registration.Activate(validCode), "时钟早于签发时间拒绝导入");
            clock = signedAt.AddDays(10);
            ActivationPayload permanent = NewPayload();
            permanent.MachineCode = OtherMachine;
            registration.Activate(Sign(signer, permanent));
            Check(registration.IsActivated && !registration.IsTrial, "试用可升级为永久授权");
            Reject(() => registration.Activate(validCode), "试用码不能覆盖永久授权");
            clock = signedAt.AddYears(10);
            Check(registration.IsActivated && registration.License.LicenseId == permanent.LicenseId,
                "升级后的永久授权不受试用日期影响");

            AssertInvalidTrial(signer, publicKey, signedAt, trial => trial.ExpiresUtc = null, "缺少到期日");
            AssertInvalidTrial(signer, publicKey, signedAt, trial => trial.ExpiresUtc = "invalid", "到期日格式");
            AssertInvalidTrial(signer, publicKey, signedAt, trial => trial.ExpiresUtc = signedAt.AddDays(30).ToString("O"),
                "三十天不等于一个自然月");
            AssertInvalidTrial(signer, publicKey, signedAt, trial => trial.ExpiresUtc = signedAt.AddMonths(2).ToString("O"),
                "不能延长成两个月");
            AssertInvalidTrial(signer, publicKey, signedAt, trial => trial.Version = 1, "试用版本不匹配");
            AssertInvalidTrial(signer, publicKey, signedAt, trial => trial.MachineCode = MachineCode, "试用不能伪装机器绑定");
            AssertInvalidTrial(signer, publicKey, signedAt, trial => trial.Edition = ActivationCodec.PermanentEdition,
                "试用不能伪装永久授权");

            string legacyCode = Sign(signer, NewPayload());
            Check(!System.Text.Encoding.UTF8.GetString(Decode(legacyCode.Split('.')[1])).Contains("expiresUtc"),
                "永久码载荷保持原格式不增加到期字段");
        }

        private static void CheckNinetyDayTrial(RSACryptoServiceProvider signer, string publicKey,
            string temporaryDirectory)
        {
            var issuedUtc = new DateTimeOffset(2026, 10, 11, 12, 30, 0, TimeSpan.Zero);
            ActivationPayload trial = NewTrial(issuedUtc);
            trial.Version = 3;
            trial.TrialDays = 90;
            trial.ExpiresUtc = issuedUtc.AddDays(90).ToString("O", CultureInfo.InvariantCulture);
            string code = Sign(signer, trial);
            Check(ActivationCodec.Verify(code, publicKey, MachineCode).TrialDays == 90, "90 天码第一台机器可用");
            Check(ActivationCodec.Verify(code, publicKey, OtherMachine).TrialDays == 90, "90 天码另一台机器可用");
            Check(ActivationCodec.Verify(code, publicKey, string.Empty).TrialDays == 90, "90 天码不要求机器码");
            DateTimeOffset expiresUtc = LicenseValidity.ExpiresAt(trial);
            Check(expiresUtc - issuedUtc == TimeSpan.FromDays(90), "期限恰为 90 天");
            Check(expiresUtc != issuedUtc.AddMonths(3), "90 天不等于三个自然月");
            Check(!LicenseValidity.IsActive(trial, issuedUtc.AddTicks(-1)), "90 天码签发前不可用");
            Check(LicenseValidity.IsActive(trial, issuedUtc), "90 天码签发时刻可用");
            Check(LicenseValidity.IsActive(trial, expiresUtc.AddTicks(-1)), "90 天码到期前可用");
            Check(!LicenseValidity.IsActive(trial, expiresUtc), "90 天码到期时刻失效");

            DateTimeOffset now = issuedUtc.AddDays(20);
            var store = new ActivationStore(Path.Combine(temporaryDirectory, "ninety-day", "activation.txt"));
            var registration = new LicenseRegistration(publicKey, MachineCode, store, () => now);
            registration.Activate(code);
            var restarted = new LicenseRegistration(publicKey, OtherMachine, store, () => now);
            restarted.Load();
            Check(restarted.IsActivated && restarted.IsTrial, "90 天码跨机器重启加载");
            registration.Activate(code);
            Check(LicenseValidity.ExpiresAt(registration.License) == expiresUtc, "重新导入不延长 90 天期限");
            now = expiresUtc;
            Check(!registration.IsActivated && !restarted.IsActivated, "90 天码无需重启自动失效");
            Reject(() => registration.Activate(code), "过期 90 天码不可重新激活");
            restarted.Load();
            Check(!restarted.IsActivated, "过期 90 天码重启仍未激活");

            trial.ExpiresUtc = issuedUtc.AddDays(91).ToString("O", CultureInfo.InvariantCulture);
            Reject(() => ActivationCodec.Verify(Sign(signer, trial), publicKey, MachineCode), "拒绝延长 90 天期限");
            trial.ExpiresUtc = expiresUtc.ToString("O", CultureInfo.InvariantCulture);
            trial.TrialDays = 89;
            Reject(() => ActivationCodec.Verify(Sign(signer, trial), publicKey, MachineCode), "拒绝非法按天期限");
            trial.TrialDays = 90;
            trial.Version = 2;
            Reject(() => ActivationCodec.Verify(Sign(signer, trial), publicKey, MachineCode), "旧月试用版本不接受按天期限");
            AssertInvalidPayload(signer, publicKey, payload => payload.TrialDays = 90, "永久码附带试用期限");
        }

        private static void AssertInvalidTrial(RSACryptoServiceProvider signer, string publicKey,
            DateTimeOffset signedAt, Action<ActivationPayload> change, string name)
        {
            ActivationPayload payload = NewTrial(signedAt);
            change(payload);
            Reject(() => ActivationCodec.Verify(Sign(signer, payload), publicKey, OtherMachine), "拒绝无效试用：" + name);
        }

        private static ActivationPayload NewTrial(DateTimeOffset issuedUtc)
        {
            ActivationPayload trial = NewPayload();
            trial.Version = 2;
            trial.Edition = ActivationCodec.TrialEdition;
            trial.MachineCode = ActivationCodec.UnboundMachineCode;
            trial.IssuedUtc = issuedUtc.ToString("O", CultureInfo.InvariantCulture);
            trial.ExpiresUtc = issuedUtc.AddMonths(1).ToString("O", CultureInfo.InvariantCulture);
            return trial;
        }

        private static byte[] Decode(string encoded)
        {
            string value = encoded.Replace('-', '+').Replace('_', '/');
            return Convert.FromBase64String(value.PadRight((value.Length + 3) / 4 * 4, '='));
        }

        private static string Sign(RSACryptoServiceProvider rsa, ActivationPayload payload)
        {
            byte[] bytes = ActivationCodec.Serialize(payload);
            return ActivationCodec.Encode(bytes, rsa.SignData(bytes, CryptoConfig.MapNameToOID("SHA256")));
        }

        private static void AssertInvalidPayload(RSACryptoServiceProvider signer, string publicKey,
            Action<ActivationPayload> change, string name)
        {
            ActivationPayload payload = NewPayload();
            change(payload);
            Reject(() => ActivationCodec.Verify(Sign(signer, payload), publicKey, MachineCode), "拒绝无效" + name);
        }

        private static void Reject(Action action, string name)
        {
            try
            {
                action();
            }
            catch (Exception exception) when (exception is IOException || exception is InvalidDataException ||
                exception is System.Xml.XmlException || exception is CryptographicException ||
                exception is UnauthorizedAccessException)
            {
                checks++;
                return;
            }

            throw new Exception("FAIL: " + name);
        }

        private static void Check(bool condition, string name)
        {
            if (!condition)
            {
                throw new Exception("FAIL: " + name);
            }

            checks++;
        }
    }
}
