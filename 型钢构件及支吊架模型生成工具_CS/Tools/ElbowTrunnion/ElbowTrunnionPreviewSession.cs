using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>Owns only elements created by the elbow trunnion feature.</summary>
    internal sealed class ElbowTrunnionPreviewSession
    {
        private List<Element> preview=new List<Element>();
        private ElbowTrunnionPlan currentPlan;
        internal bool HasPreview { get { return preview.Count>0; } }
        internal ElbowTrunnionPlan CurrentPlan { get { return currentPlan; } }

        internal void Regenerate(ElbowTrunnionPlan plan)
        {
            if (HasPreview && currentPlan==null)
                throw new InvalidOperationException("上次清理预览失败，请先取消预览后重试。");
            var parts=ElbowTrunnionBuilder.Build(plan);
            var model=Session.Instance.GetActiveDgnModel();
            if (model==null) throw new InvalidOperationException("没有活动模型。");
            var cell=new CellHeaderElement(model,plan.SupportCode,DPoint3d.Zero,
                DMatrix3d.Identity,parts);
            var replacement=new List<Element> { cell };
            var added=new List<Element>();
            try
            {
                foreach(var element in replacement)
                {
                    var status=element.AddToModel();
                    if (status!=StatusInt.Success)
                        throw new InvalidOperationException("耳轴预览写入模型失败："+status);
                    added.Add(element);
                }
            }
            catch
            {
                foreach(var element in added) DeleteOwned(element);
                throw;
            }
            var old=preview;
            var failed=new List<Element>();
            foreach(var element in old)
            {
                try { DeleteOwned(element); }
                catch { failed.Add(element); }
            }
            preview=replacement;
            currentPlan=plan;
            if (failed.Count>0)
            {
                preview.AddRange(failed);
                currentPlan=null;
                throw new InvalidOperationException("旧预览清理失败；请取消预览并重试。");
            }
        }

        internal void Confirm()
        {
            if (!HasPreview || currentPlan==null)
                throw new InvalidOperationException("当前没有可确认的耳轴预览。");
            var p=currentPlan;
            string pipeSpec="DN"+p.TrunnionDn+" Ø"+p.TrunnionOdMm.ToString("G")+" × "+
                p.WallMm.ToString("G")+" mm，"+p.Parameters.Material;
            Statistics.AttachElbowTrunnion(preview[0],p,"TRUNNION",
                p.Parameters.Trunnion==TrunnionOrientation.Vertical ? "竖直耳轴" : "水平耳轴",
                pipeSpec,p.TubeLengthMm,true);
            if (p.PlateThicknessMm>0)
                Statistics.AttachElbowTrunnion(preview[0],p,"PLATE",
                    p.Parameters.Trunnion==TrunnionOrientation.Vertical ? "底板" : "端板",
                    p.Parameters.Plate+" 型，"+p.PlateThicknessMm.ToString("G")+" mm",
                    p.PlateThicknessMm,false);
            if (p.LinerThicknessMm>0)
                Statistics.AttachElbowTrunnion(preview[0],p,"LINER","镜面不锈钢覆面",
                    "3 mm",p.LinerThicknessMm,false);
            preview=new List<Element>();
            currentPlan=null;
        }
        internal void Cancel()
        {
            var failed=new List<Element>();
            foreach(var element in preview)
            {
                try { DeleteOwned(element); }
                catch { failed.Add(element); }
            }
            preview=failed;
            currentPlan=null;
            if (failed.Count>0)
                throw new InvalidOperationException("有 "+failed.Count+" 个耳轴预览元素未能删除，请重试取消或检查模型状态。");
        }
        private static void DeleteOwned(Element element)
        {
            if (element==null || !element.IsValid) return;
            var status=element.DeleteFromModel();
            if (status!=StatusInt.Success)
                throw new InvalidOperationException("删除耳轴预览元素失败："+status);
        }
    }
}


