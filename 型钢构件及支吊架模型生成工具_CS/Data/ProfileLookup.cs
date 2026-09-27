using System;
using System.Linq;

namespace SteelSectionProbe
{
    /// <summary>
    /// 型钢目录（<c>Resources/profiles.bin</c> 载入的 <see cref="RuntimeData.Families"/>）的按名查找。
    /// 各支吊架功能共用这一份，不要在功能内部再写一套三连查找。
    /// 纯查表、不读文件，因此纯计算检查工程也能链接。
    /// </summary>
    internal static class ProfileLookup
    {
        internal static FamilyData Family(FamilyData[] families,string familyId)
        {
            if(families==null) return null;
            return families.FirstOrDefault(x=>x.Id==familyId);
        }

        internal static ProfileData Profile(FamilyData[] families,string familyId,
            string profileName)
        {
            var family=Family(families,familyId);
            return family==null?null:family.Profiles.FirstOrDefault(x=>x.Name==profileName);
        }

        /// <summary>按 族 / 规格 / 插入基准 取轮廓；找不到时抛中文错误。</summary>
        internal static ModeData Mode(FamilyData[] families,string familyId,string profileName,
            string modeId)
        {
            var profile=Profile(families,familyId,profileName);
            var mode=profile==null?null:profile.Modes.FirstOrDefault(x=>x.Id==modeId);
            if(mode==null)
                throw new InvalidOperationException("型钢目录缺少 "+profileName+" / "+modeId+"。");
            return mode;
        }
    }
}
