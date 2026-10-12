using System.Runtime.Serialization;

namespace SteelSectionProbe
{
    /// <summary>
    /// 授权的签名载荷。新增可选字段必须兼容已签发的永久激活码。
    /// </summary>
    [DataContract]
    internal sealed class ActivationPayload
    {
        [DataMember(Name = "version", Order = 0, IsRequired = true)]
        public int Version { get; set; }

        [DataMember(Name = "product", Order = 1, IsRequired = true)]
        public string Product { get; set; }

        [DataMember(Name = "licenseId", Order = 2, IsRequired = true)]
        public string LicenseId { get; set; }

        [DataMember(Name = "machineCode", Order = 3, IsRequired = true)]
        public string MachineCode { get; set; }

        [DataMember(Name = "userName", Order = 4, IsRequired = true)]
        public string UserName { get; set; }

        [DataMember(Name = "issuedUtc", Order = 5, IsRequired = true)]
        public string IssuedUtc { get; set; }

        [DataMember(Name = "edition", Order = 6, IsRequired = true)]
        public string Edition { get; set; }

        [DataMember(Name = "expiresUtc", Order = 7, EmitDefaultValue = false)]
        public string ExpiresUtc { get; set; }

        // 旧版自然月试用码省略此字段；新版按天试用码将期限纳入签名。
        [DataMember(Name = "trialDays", Order = 8, EmitDefaultValue = false)]
        public int TrialDays { get; set; }
    }
}
