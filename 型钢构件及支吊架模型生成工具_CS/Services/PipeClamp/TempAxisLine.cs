using System;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 临时辅助线：点选**参考文件（reference）**里的管道时，把读到的管轴"物化"成活动文件里
    /// 的一条普通直线，之后完全走已验证的"按线生成"路径，生成 / 取消后再把这条线删掉。
    /// <para>
    /// 这样做把"参考元素"的影响面收敛成**一次轴线读取**：生成路径本身不再接触参考文件，
    /// 也就不会碰到"参考元素在活动模型里删不掉 / 写不进 / 几何读不稳"这类问题。
    /// 参考元素读到的管道属性（公称直径 / 保温 / 管道号）由调用方并到这条线上。
    /// </para>
    /// </summary>
    internal static class TempAxisLine
    {
        /// <summary>按轴线两端点（UOR）在活动模型里建一条直线，返回元素 id。</summary>
        internal static ulong Create(DPoint3d start,DPoint3d end)
        {
            var model=Session.Instance.GetActiveDgnModel();
            if(model==null) throw new InvalidOperationException("没有活动模型，无法生成临时辅助线。");
            double dx=start.X-end.X,dy=start.Y-end.Y,dz=start.Z-end.Z;
            if(Math.Sqrt(dx*dx+dy*dy+dz*dz)<=1.0e-9)
                throw new InvalidOperationException("管轴长度为零，无法生成临时辅助线。");
            var line=new LineElement(model,null,new DSegment3d(start,end));
            var status=line.AddToModel();
            if(status!=StatusInt.Success)
                throw new InvalidOperationException("临时辅助线写入失败："+status);
            return (ulong)line.ElementId;
        }

        /// <summary>按 id 删除临时辅助线（只认活动模型）。元素已不在时静默返回。</summary>
        internal static void Delete(ulong id)
        {
            if(id==0) return;
            var model=Session.Instance.GetActiveDgnModel();
            var element=model==null?null:model.FindElementById(new ElementId(ref id));
            if(element==null || !element.IsValid) return;
            var status=element.DeleteFromModel();
            if(status!=StatusInt.Success)
                throw new InvalidOperationException("临时辅助线删除失败："+status);
        }
    }
}
