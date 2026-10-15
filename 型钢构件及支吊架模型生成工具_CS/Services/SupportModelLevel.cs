using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>普通支吊架实体使用 user_support。没有该图层就创建，并设为活动图层。</summary>
    internal static class SupportModelLevel
    {
        internal const string Name = "user_support";

        internal static void Use(Element element)
        {
            if (element == null) throw new InvalidOperationException("没有可放入支吊架图层的实体。");
            var model = Session.Instance.GetActiveDgnModel();
            if (model == null) throw new InvalidOperationException("没有活动模型，不能设置支吊架图层。");
            var cache = model.GetDgnFile().GetLevelCache() as FileLevelCache;
            if (cache == null) throw new InvalidOperationException("无法读取模型图层。");
            LevelHandle level = cache.GetLevelByName(Name);
            if (!level.IsValid) level = cache.CreateLevel(Name);
            if (!level.IsValid) throw new InvalidOperationException("无法创建图层 user_support。");
            SettingsActivator.SetActiveLevel((uint)level.LevelId);
            using (var setter = new ElementPropertiesSetter())
            {
                setter.SetLevel(level.LevelId);
                if (!setter.Apply(element)) throw new InvalidOperationException("无法把支吊架放到图层 user_support。");
            }
        }
    }
}
