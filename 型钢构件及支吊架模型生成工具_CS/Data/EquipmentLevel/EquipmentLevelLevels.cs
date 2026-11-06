using System;
using System.Collections.Generic;
using Com = Bentley.Interop.MicroStationDGN;

namespace SteelSectionProbe
{
    /// <summary>
    /// 统一访问 OPM COM 图层集合。
    /// <para>
    /// <c>ModelReference.Levels</c> 是宿主装载图层表时的快照集合：在它建立之后新建、改名、
    /// 删除的图层不会自动出现，必须调用 <c>Levels.Refresh()</c> 重新装载；该集合默认还不含
    /// 隐藏图层（<c>IncludeHidden</c> 默认 false）。宿主实测：新建的图层在未刷新前按名查不到，
    /// 重启 OPM 后才变为可用。
    /// </para>
    /// <para>
    /// 因此这里每次使用前先刷新，并允许按层号回退查找；但无论走哪条路径都必须核对
    /// <c>Level.ID</c> 与 DGN 侧层号一致，绝不按名称直接认层。
    /// </para>
    /// </summary>
    internal static class EquipmentLevelLevels
    {
        /// <summary>取得已刷新的 COM 图层集合；取不到时返回 null 并给出原因。</summary>
        internal static Com.Levels Acquire(Com.ModelReference active, out string issue)
        {
            issue = null;
            if (active == null) { issue = "OPM COM 活动模型不可用"; return null; }
            Com.Levels levels;
            try { levels = active.Levels; }
            catch (Exception ex) { issue = "读取 COM 图层集合失败：" + ex.Message; return null; }
            if (levels == null) { issue = "OPM COM 图层集合不可用"; return null; }

            // 新层不可见的两类原因都要处理：快照过期、以及默认不包含隐藏层。
            var problems = new List<string>();
            try { levels.Refresh(); }
            catch (Exception ex) { problems.Add("Refresh：" + ex.Message); }
            try { levels.IncludeHidden = true; }
            catch (Exception ex) { problems.Add("IncludeHidden：" + ex.Message); }
            if (problems.Count > 0) issue = string.Join("；", problems);
            return levels;
        }

        /// <summary>
        /// 按层号核对查找目标图层：先按名，再按层号；两者都要求 <c>ID</c> 与层号一致。
        /// 找不到时返回 null，并通过 <paramref name="detail"/> 说明卡在哪一步。
        /// </summary>
        internal static Com.Level Find(Com.Levels levels, uint id, string name, out string detail)
        {
            detail = null;
            if (levels == null) { detail = "图层集合未取得"; return null; }

            Com.Level byName = null;
            string failure = null;
            try { byName = levels.Find(name); }
            catch (Exception ex) { failure = "按名查找异常：" + ex.Message; }
            if (byName != null && (uint)byName.ID == id) { detail = "按名命中"; return byName; }

            Com.Level byNumber = null;
            try { byNumber = levels.FindByNumber((int)id); }
            catch (Exception ex) { failure = Append(failure, "按层号查找异常：" + ex.Message); }
            if (byNumber != null && (uint)byNumber.ID == id) { detail = "按层号命中"; return byNumber; }

            if (byName != null) failure = Append(failure, "按名命中 ID=" + (uint)byName.ID + "，期望 " + id);
            if (byNumber != null) failure = Append(failure, "按层号命中 ID=" + (uint)byNumber.ID + "，期望 " + id);
            if (byName == null && byNumber == null)
                failure = Append(failure, "集合中既无同名层也无该层号（可能是快照未刷新或未包含隐藏层）");
            detail = failure;
            return null;
        }

        private static string Append(string current, string message)
        {
            return string.IsNullOrEmpty(current) ? message : current + "；" + message;
        }
    }
}
