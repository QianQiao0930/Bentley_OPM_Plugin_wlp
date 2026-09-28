using System;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>
    /// 四种管夹共用的预览生命周期：重建时先写入新版预览、成功后再删除旧版；
    /// 确认时按当前种类写入 <c>PipeSupportComponents</c> ItemType；取消与离开页面都清理未确认元素。
    /// </summary>
    internal sealed class PipeClampPreviewSession
    {
        private Element preview;
        private PipeClampKind kind;

        private A2ClampPlan a2Plan;
        private E1GuidePlan e1Plan;
        private K1LimitPlan k1Plan;
        private T4ShoeLayout t4Layout;
        private T4ShoeBooleanLayout t4Boolean;
        private bool t4BuildPipe,t4BuildInsulation;

        internal bool HasPreview { get { return preview!=null; } }
        internal PipeClampKind Kind { get { return kind; } }
        internal T4ShoeLayout T4Layout { get { return t4Layout; } }
        internal T4ShoeBooleanLayout T4Boolean { get { return t4Boolean; } }

        internal void ShowA2(A2ClampPlan plan,DPoint3d center,DVector3d axis)
        {
            Replace(A2ClampBuilder.Build(plan,center,axis),A2ClampCatalog.CellName,
                PipeClampKind.A2StandardTwoBolt);
            a2Plan=plan;
        }

        internal void ShowE1(E1GuidePlan plan)
        {
            Replace(E1GuideBuilder.Build(plan),E1GuideCatalog.SupportCode,
                PipeClampKind.E1Guide);
            e1Plan=plan;
        }

        internal void ShowK1(K1LimitPlan plan,DPoint3d center,DVector3d axis)
        {
            Replace(K1LimitBuilder.Build(plan,center,axis),K1LimitCatalog.CellName,
                PipeClampKind.K1Limit);
            k1Plan=plan;
        }

        internal void ShowT4(T4ShoeLayout layout,T4ShoeBooleanLayout boolean,DPoint3d center,
            DVector3d axis,bool buildPipe,bool buildInsulation)
        {
            var parts=T4ShoeBuilder.Build(layout,boolean,center,axis,buildPipe,buildInsulation);
            Replace(parts,T4ShoeCatalog.CellName,PipeClampKind.T4Insulated);
            t4Layout=layout;
            t4Boolean=boolean;
            t4BuildPipe=buildPipe;
            t4BuildInsulation=buildInsulation;
        }

        /// <summary>写入新版预览，成功后再删除旧版；删除失败则回滚新版，保证不残留。</summary>
        private void Replace(IList<Element> parts,string cellName,PipeClampKind newKind)
        {
            if(parts==null || parts.Count==0)
                throw new InvalidOperationException("管夹实体创建失败（无子元素）。");
            var model=Session.Instance.GetActiveDgnModel();
            var replacement=new CellHeaderElement(model,cellName,DPoint3d.Zero,DMatrix3d.Identity,parts);
            var status=replacement.AddToModel();
            if(status!=StatusInt.Success)
                throw new InvalidOperationException("管夹预览写入失败："+status);
            try { DeleteOwned(preview); }
            catch
            {
                try { DeleteOwned(replacement); }
                catch { preview=replacement; kind=newKind; ClearPlans(); }
                throw;
            }
            preview=replacement;
            kind=newKind;
        }

        internal void Confirm()
        {
            if(preview==null) throw new InvalidOperationException("当前没有可确认的管夹预览。");
            var element=preview;
            switch(kind)
            {
                case PipeClampKind.A2StandardTwoBolt:
                    Statistics.AttachA2Clamp(element,a2Plan); break;
                case PipeClampKind.E1Guide:
                    Statistics.AttachE1Guide(element,e1Plan); break;
                case PipeClampKind.K1Limit:
                    Statistics.AttachK1Limit(element,k1Plan); break;
                case PipeClampKind.T4Insulated:
                    Statistics.AttachT4Shoe(element,t4Layout,t4Boolean,t4BuildPipe,
                        t4BuildInsulation); break;
                default:
                    throw new InvalidOperationException("未知的管夹种类。");
            }
            preview=null;
            ClearPlans();
        }

        internal void Cancel()
        {
            DeleteOwned(preview);
            preview=null;
            ClearPlans();
        }

        private void ClearPlans()
        {
            a2Plan=null; e1Plan=null; k1Plan=null; t4Layout=null; t4Boolean=null;
            t4BuildPipe=false; t4BuildInsulation=false;
        }

        private static void DeleteOwned(Element element)
        {
            if(element==null || !element.IsValid) return;
            var status=element.DeleteFromModel();
            if(status!=StatusInt.Success)
                throw new InvalidOperationException("删除管夹预览失败："+status);
        }
    }
}
