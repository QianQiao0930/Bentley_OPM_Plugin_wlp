using System;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.Elements;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal static class Statistics
    {
        private const string LibraryName="PipeSupportComponents";
        private static readonly string[] Names={ "RecordKind","SupportType","AssemblyTag",
            "ComponentName","Specification","DesignLengthMm","Quantity","Unit","PipeNumber" };
        private static readonly CustomProperty.TypeKind[] Kinds={
            CustomProperty.TypeKind.String,CustomProperty.TypeKind.String,CustomProperty.TypeKind.String,
            CustomProperty.TypeKind.String,CustomProperty.TypeKind.String,CustomProperty.TypeKind.Double,
            CustomProperty.TypeKind.Integer,CustomProperty.TypeKind.String,CustomProperty.TypeKind.String };
        private static string Hash10(string value)
        {
            using(var md5=MD5.Create())
            {
                byte[] bytes=md5.ComputeHash(Encoding.UTF8.GetBytes(value));
                var result=new StringBuilder();
                for(int i=0;i<5;i++) result.Append(bytes[i].ToString("x2",CultureInfo.InvariantCulture));
                return result.ToString();
            }
        }
        private static ItemType Ensure(string name,object[] defaults)
        {
            var file=Session.Instance.GetActiveDgnFile();
            ItemTypeLibrary library=ItemTypeLibrary.FindByName(LibraryName,file);
            bool changed=false;
            if(library==null) { library=ItemTypeLibrary.Create(LibraryName,file,false); changed=true; }
            ItemType type=library.GetItemTypeByName(name);
            if(type==null) { type=library.AddItemType(name,false); changed=true; }
            if(type==null) throw new InvalidOperationException("Cannot create ItemType "+name);
            for(int i=0;i<Names.Length;i++)
            {
                CustomProperty property=type.GetPropertyByName(Names[i]);
                if(property!=null) continue;
                property=type.AddProperty(Names[i],false);
                if(property==null) throw new InvalidOperationException("Cannot create property "+Names[i]);
                property.Type=Kinds[i];
                property.DefaultValue=defaults[i];
                changed=true;
            }
            if(changed && !library.Write()) throw new InvalidOperationException("Cannot persist ItemType library");
            library=ItemTypeLibrary.FindByName(LibraryName,file);
            return library.GetItemTypeByName(name);
        }
        internal static void Attach(Element element,FamilyData family,ProfileData profile,double lengthMm)
        {
            string assemblyName="PipeSupportAssembly_STEEL_SECTION_"+Hash10("|"+profile.Name);
            string lengthKey=lengthMm.ToString("F3",CultureInfo.InvariantCulture).Replace('.','_').Replace('-','N');
            string componentName="PipeSupportComponent_STEEL_SECTION_"+family.Id+"_L"+lengthKey;
            object[] assembly={"Assembly","型钢","","支吊架",profile.Name,0.0,1,"套",""};
            object[] component={"Component","型钢","",family.Label,profile.Name,lengthMm,1,"根",""};
            var host=new CustomItemHost(element,false);
            host.ApplyCustomItem(Ensure(assemblyName,assembly));
            host.ApplyCustomItem(Ensure(componentName,component));
        }
        internal static void AttachElbowTrunnion(Element element, ElbowTrunnionPlan plan,
            string componentName, string specification, double designLengthMm, bool includeAssembly)
        {
            if (element==null || plan==null) throw new ArgumentNullException("element");
            string feature=plan.SupportCode;                 // ASCII 代号，只用于 ItemType 命名
            string supportType=ElbowTrunnionCatalog.SupportType(feature);  // 属性值用中文类型名
            string key=Hash10(feature+"|"+plan.AssemblyTag+"|"+componentName+"|"+
                designLengthMm.ToString("F3",CultureInfo.InvariantCulture));
            var host=new CustomItemHost(element,false);
            if (includeAssembly)
            {
                object[] assembly={ "Assembly",supportType,plan.AssemblyTag,"支吊架",
                    plan.AssemblyTag,0.0,1,"套",plan.Selection.PipeNumber ?? "" };
                host.ApplyCustomItem(Ensure("PipeSupportAssembly_"+feature+"_"+key,assembly));
            }
            object[] component={ "Component",supportType,plan.AssemblyTag,componentName,
                specification,designLengthMm,1,"件",plan.Selection.PipeNumber ?? "" };
            host.ApplyCustomItem(Ensure("PipeSupportComponent_"+feature+"_"+key,component));
        }        internal static void AttachE1Guide(Element element,E1GuidePlan plan)
        {
            if(element==null || plan==null)throw new ArgumentNullException("element");
            string feature=E1GuideCatalog.SupportCode;   // ASCII 代号，只用于 ItemType 命名
            string supportType=E1GuideCatalog.SupportType;  // 属性值用中文类型名
            string prefix=feature+"|"+plan.Number+"|"+plan.SourceId.ToString(CultureInfo.InvariantCulture)+"|"+plan.Material+"|"+plan.PipeNumber;
            var host=new CustomItemHost(element,false);
            object[] assembly={"Assembly",supportType,plan.Number,"支吊架",
                "DN"+plan.Dn+" / "+plan.Item.Specification,0.0,1,"套",plan.PipeNumber};
            host.ApplyCustomItem(Ensure("PipeSupportAssembly_E1_"+Hash10(prefix),assembly));
            object[] member={"Component",supportType,plan.Number,"构件A",
                plan.Item.Specification+" / "+plan.Material,plan.HeightMm,2,"件",plan.PipeNumber};
            host.ApplyCustomItem(Ensure("PipeSupportComponent_E1_MEMBER_"+Hash10(prefix),member));
            if(plan.Stainless)
            {
                string spec="□"+plan.Item.LinerWidthMm.ToString("G",CultureInfo.InvariantCulture)+"×"+
                    plan.Item.LinerHeightMm.ToString("G",CultureInfo.InvariantCulture)+"×"+
                    plan.Item.LinerThicknessMm.ToString("G",CultureInfo.InvariantCulture)+" / 06Cr18Ni9";
                object[] liner={"Component",supportType,plan.Number,"不锈钢薄板",spec,
                    plan.Item.LinerHeightMm,2,"件",plan.PipeNumber};
                host.ApplyCustomItem(Ensure("PipeSupportComponent_E1_LINER_"+Hash10(prefix),liner));
            }
        }
        /// <summary>G2 混凝土锚板：1 条 Assembly + 锚板 + 膨胀锚栓×4。
        /// 属性值沿用 <c>模块/公共/支吊架公共库.py</c> 的契约：SupportType 存中文类型名、
        /// Assembly 的 ComponentName 固定为“支吊架”。</summary>
        internal static void AttachG2Anchor(Element element,G2AnchorPlan plan)
        {
            if(element==null || plan==null)throw new ArgumentNullException("element");
            string feature=G2AnchorCatalog.FeatureCode;
            string prefix=feature+"|"+plan.AssemblyTag+"|"+
                plan.SpacingMm.ToString("F3",CultureInfo.InvariantCulture)+"|"+
                ((int)plan.MountFace).ToString(CultureInfo.InvariantCulture)+"|"+
                plan.ActualEmbedmentMm.ToString("F3",CultureInfo.InvariantCulture);
            var host=new CustomItemHost(element,false);
            object[] assembly={"Assembly",G2AnchorCatalog.SupportType,plan.AssemblyTag,"支吊架",
                plan.AssemblySpecification,0.0,1,"套",""};
            host.ApplyCustomItem(Ensure("PipeSupportAssembly_G2_"+Hash10(prefix),assembly));
            object[] plate={"Component",G2AnchorCatalog.SupportType,plan.AssemblyTag,"锚板",
                plan.PlateSpecification,plan.PlateThicknessMm,1,"块",""};
            host.ApplyCustomItem(Ensure("PipeSupportComponent_G2_PLATE_"+Hash10(prefix),plate));
            object[] bolt={"Component",G2AnchorCatalog.SupportType,plan.AssemblyTag,"膨胀锚栓",
                plan.BoltSpecification,plan.BoltLengthMm,plan.BoltCount,"套",""};
            host.ApplyCustomItem(Ensure("PipeSupportComponent_G2_BOLT_"+Hash10(prefix),bolt));
        }
        /// <summary>A2 标准型 2 螺栓管夹：1 条 Assembly + 管架本体 + 螺栓 ×2。</summary>
        internal static void AttachA2Clamp(Element element,A2ClampPlan plan)
        {
            if(element==null || plan==null)throw new ArgumentNullException("element");
            string feature=A2ClampCatalog.SupportCode;
            string prefix=feature+"|"+plan.Dn.ToString(CultureInfo.InvariantCulture)+"|"+
                plan.InsulationMm.ToString("F3",CultureInfo.InvariantCulture);
            var host=new CustomItemHost(element,false);
            object[] assembly={"Assembly",A2ClampCatalog.SupportType,plan.AssemblyTag,"支吊架",
                plan.AssemblySpecification,0.0,1,"套",""};
            host.ApplyCustomItem(Ensure("PipeSupportAssembly_A2_"+Hash10(prefix),assembly));
            object[] body={"Component",A2ClampCatalog.SupportType,plan.AssemblyTag,"管架本体",
                plan.BodySpecification,plan.WidthMm,1,"件",""};
            host.ApplyCustomItem(Ensure("PipeSupportComponent_A2_BODY_"+Hash10(prefix),body));
            object[] bolt={"Component",A2ClampCatalog.SupportType,plan.AssemblyTag,"螺栓",
                plan.BoltSpecification,0.0,2,"套",""};
            host.ApplyCustomItem(Ensure("PipeSupportComponent_A2_BOLT_"+Hash10(prefix),bolt));
        }
        /// <summary>K1 不保温管限位架：1 条 Assembly + 限位块 ×2 + 可选底板 ×2。</summary>
        internal static void AttachK1Limit(Element element,K1LimitPlan plan)
        {
            if(element==null || plan==null)throw new ArgumentNullException("element");
            string feature=K1LimitCatalog.SupportCode;
            string prefix=feature+"|"+plan.Number+"|"+plan.Dn.ToString(CultureInfo.InvariantCulture)+
                "|"+plan.ExistingWidthMm.ToString("F3",CultureInfo.InvariantCulture);
            var host=new CustomItemHost(element,false);
            object[] assembly={"Assembly",K1LimitCatalog.SupportType,plan.Number,"支吊架",
                plan.Specification,0.0,1,"套",""};
            host.ApplyCustomItem(Ensure("PipeSupportAssembly_K1_"+Hash10(prefix),assembly));
            object[] block={"Component",K1LimitCatalog.SupportType,plan.Number,"限位块（型钢）",
                plan.Specification,plan.SizeMm,2,"件",""};
            host.ApplyCustomItem(Ensure("PipeSupportComponent_K1_BLOCK_"+Hash10(prefix),block));
            if(plan.Plate!=null)
            {
                string spec=plan.Plate[0].ToString("0",CultureInfo.InvariantCulture)+"×"+
                    plan.Plate[1].ToString("0",CultureInfo.InvariantCulture)+"×"+
                    plan.Plate[2].ToString("0",CultureInfo.InvariantCulture);
                object[] plate={"Component",K1LimitCatalog.SupportType,plan.Number,"底板",
                    spec,plan.Plate[2],2,"块",""};
                host.ApplyCustomItem(Ensure("PipeSupportComponent_K1_PLATE_"+Hash10(prefix),plate));
            }
        }
        /// <summary>T4 高温隔热限位管托：1 条 Assembly + 承重板 / 底座 / 耳板 / 螺栓
        /// （可选管道与保温层）。</summary>
        internal static void AttachT4Shoe(Element element,T4ShoeLayout layout,
            T4ShoeBooleanLayout boolean,bool builtPipe,bool builtInsulation)
        {
            if(element==null || layout==null)throw new ArgumentNullException("element");
            string feature=T4ShoeCatalog.SupportCode;
            string prefix=feature+"|"+layout.Number+"|"+layout.Dn.ToString(CultureInfo.InvariantCulture)+
                "|"+layout.InsulationMm.ToString("F3",CultureInfo.InvariantCulture)+"|"+
                layout.ShoeLengthMm.ToString("F3",CultureInfo.InvariantCulture)+"|"+
                (boolean!=null?boolean.HoleDiameterMm.ToString("F3",CultureInfo.InvariantCulture):"0");
            var host=new CustomItemHost(element,false);
            object[] assembly={"Assembly",T4ShoeCatalog.SupportType,layout.Number,"支吊架",
                "DN"+layout.Dn.ToString(CultureInfo.InvariantCulture),0.0,1,"套",""};
            host.ApplyCustomItem(Ensure("PipeSupportAssembly_T4_"+Hash10(prefix),assembly));
            var items=T4ShoeCalculator.ComponentItems(layout,boolean,builtPipe,builtInsulation);
            foreach(var item in items)
            {
                double length;double.TryParse(item[3],NumberStyles.Float,
                    CultureInfo.InvariantCulture,out length);
                int quantity;int.TryParse(item[4],NumberStyles.Integer,
                    CultureInfo.InvariantCulture,out quantity);
                object[] component={"Component",T4ShoeCatalog.SupportType,layout.Number,item[1],
                    item[2],length,quantity,item[5],""};
                host.ApplyCustomItem(Ensure("PipeSupportComponent_T4_"+item[0]+"_"+Hash10(prefix),
                    component));
            }
        }
    }
}

