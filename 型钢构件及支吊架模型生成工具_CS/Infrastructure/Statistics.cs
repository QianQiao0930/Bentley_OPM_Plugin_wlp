using System;
using System.Globalization;
using System.Collections.Generic;
using Bentley.DgnPlatformNET;
using Bentley.DgnPlatformNET.DgnEC;
using Bentley.DgnPlatformNET.Elements;
using Bentley.ECObjects.Instance;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    /// <summary>把支吊架记录写进 DGN 的公共 ItemType 库 <c>PipeSupportComponents</c>。</summary>
    /// <remarks>
    /// ⚠️ 写入约定（详见 <c>AGENTS.md</c> 清单契约一节）：
    /// <list type="bullet">
    /// <item>ItemType 名<b>固定</b>，不得编入长度、编号、角度等随实例变化的值；
    /// 同一元素上多条记录用<b>构件角色</b>后缀区分（<c>_PLATE</c> / <c>_BOLT</c> / <c>_TRUNNION</c> …）。</item>
    /// <item>每条记录的差异（规格、长度、数量、管道号…）<b>写进元素上的 EC 实例属性</b>，
    /// 而不是类型默认值。可用 API：<c>ApplyCustomItem</c> 返回 <c>IDgnECInstance</c>，
    /// 改完后调 <c>WriteChanges()</c>。</item>
    /// </list>
    /// 原因：新建 ItemType 要触发一次 <c>library.Write()</c> 全库写盘，其成本约为
    /// “数十毫秒 + 2 ms × 库内类型数”（537 个类型时实测 1.16~1.32 秒）。把尺寸编进类型名会让
    /// 每个新规格都新建类型，于是每次确认都要付一次写盘 —— 这正是“点确认很慢”的根因。
    /// 类型名固定后库规模恒定，首次之后每次确认都命中，实测 <b>1447.6 ms → 1.2 ms</b>。
    /// </remarks>
    internal static class Statistics
    {
        private const string LibraryName="PipeSupportComponents";
        private static readonly string[] Names={ "RecordKind","SupportType","AssemblyTag",
            "ComponentName","Specification","DesignLengthMm","Quantity","Unit","PipeNumber" };
        private static readonly CustomProperty.TypeKind[] Kinds={
            CustomProperty.TypeKind.String,CustomProperty.TypeKind.String,CustomProperty.TypeKind.String,
            CustomProperty.TypeKind.String,CustomProperty.TypeKind.String,CustomProperty.TypeKind.Double,
            CustomProperty.TypeKind.Integer,CustomProperty.TypeKind.String,CustomProperty.TypeKind.String };
        private static ItemType Ensure(string name,object[] defaults)
        {
            var file=Session.Instance.GetActiveDgnFile();
            ItemTypeLibrary library=null;
            using(StatisticsTrace.Section("FindByName")) { library=ItemTypeLibrary.FindByName(LibraryName,file); }
            bool changed=false;
            if(library==null) { library=ItemTypeLibrary.Create(LibraryName,file,false); changed=true; }
            ItemType type=library.GetItemTypeByName(name);
            if(type==null) { type=library.AddItemType(name,false); changed=true; }
            if(type==null) throw new InvalidOperationException("无法创建 ItemType："+name);
            for(int i=0;i<Names.Length;i++)
            {
                CustomProperty property=type.GetPropertyByName(Names[i]);
                if(property!=null) continue;
                property=type.AddProperty(Names[i],false);
                if(property==null) throw new InvalidOperationException("无法创建 ItemType 属性："+Names[i]);
                property.Type=Kinds[i];
                property.DefaultValue=defaults[i];
                changed=true;
            }
            if(changed)
            {
                bool saved;
                using(StatisticsTrace.Section("Write")) { saved=library.Write(); }
                if(!saved) throw new InvalidOperationException("无法保存 ItemType 库");
            }
            using(StatisticsTrace.Section("FindByName")) { library=ItemTypeLibrary.FindByName(LibraryName,file); }
            StatisticsTrace.Note("库类型数",library.ItemTypeCount.ToString(CultureInfo.InvariantCulture));
            StatisticsTrace.Increment(changed?"新建类型":"命中类型",1);
            return library.GetItemTypeByName(name);
        }
        /// <summary>把所有类型定义一次性补齐（最多一次写盘），返回与 <paramref name="entries"/> 同序的类型。</summary>
        private static IList<ItemType> EnsureBatch(IList<KeyValuePair<string,object[]>> entries)
        {
            var file=Session.Instance.GetActiveDgnFile();
            ItemTypeLibrary library=null;
            using(StatisticsTrace.Section("FindByName")) { library=ItemTypeLibrary.FindByName(LibraryName,file); }
            bool changed=false;
            if(library==null){library=ItemTypeLibrary.Create(LibraryName,file,false);changed=true;}
            foreach(var entry in entries)
            {
                var type=library.GetItemTypeByName(entry.Key);
                if(type==null){type=library.AddItemType(entry.Key,false);changed=true;}
                if(type==null)throw new InvalidOperationException("无法创建 ItemType："+entry.Key);
                for(int i=0;i<Names.Length;i++)
                {
                    if(type.GetPropertyByName(Names[i])!=null)continue;
                    var property=type.AddProperty(Names[i],false);
                    if(property==null)throw new InvalidOperationException("无法创建 ItemType 属性："+Names[i]);
                    property.Type=Kinds[i];property.DefaultValue=entry.Value[i];changed=true;
                }
            }
            if(changed)
            {
                using(StatisticsTrace.Section("Write")) {
                    if(!library.Write())throw new InvalidOperationException("无法保存 ItemType 库"); }
                using(StatisticsTrace.Section("FindByName")) { library=ItemTypeLibrary.FindByName(LibraryName,file); }
            }
            StatisticsTrace.Note("库类型数",library.ItemTypeCount.ToString(CultureInfo.InvariantCulture));
            StatisticsTrace.Increment(changed?"新建类型":"命中类型",entries.Count);
            var result=new List<ItemType>();
            foreach(var entry in entries)result.Add(library.GetItemTypeByName(entry.Key));
            return result;
        }
        /// <summary>把一个元素上的全部记录一次性写入：先统一补齐类型定义，再逐条附加并写实例值。</summary>
        private static void WriteRecords(Element element,IList<KeyValuePair<string,object[]>> entries)
        {
            if(element==null||entries==null||entries.Count==0) return;
            // 同一元素上一个 ItemType 只能挂一条记录：撞名会让后一条静默覆盖前一条（丢记录）。
            // 多条记录必须用构件角色后缀区分，不能靠编入尺寸的旧办法。
            var seen=new HashSet<string>(StringComparer.Ordinal);
            foreach(var entry in entries)
            {
                if(seen.Contains(entry.Key))
                    throw new InvalidOperationException("同一元素上有两条记录使用了同一个附加项类型名“"+
                        entry.Key+"”。多条记录请改用构件角色后缀区分（如 _PLATE / _BOLT）。");
                seen.Add(entry.Key);
            }
            IList<ItemType> types;
            using(StatisticsTrace.Section("EnsureBatch")) { types=EnsureBatch(entries); }
            var host=new CustomItemHost(element,false);
            for(int i=0;i<types.Count;i++)
            {
                string name=entries[i].Key;
                if(types[i]==null) throw new InvalidOperationException("无法取得附加项类型："+name);
                IDgnECInstance instance;
                using(StatisticsTrace.Section("ApplyCustomItem")) { instance=host.ApplyCustomItem(types[i]); }
                if(instance==null) throw new InvalidOperationException("无法把附加项附加到元素上："+name);
                using(StatisticsTrace.Section("实例写值")) { WriteValues(instance,name,entries[i].Value); }
            }
        }
        /// <summary>把本条记录的 9 个属性值真正写进元素上的 EC 实例并提交。</summary>
        private static void WriteValues(IDgnECInstance instance,string name,object[] values)
        {
            for(int i=0;i<Names.Length;i++)
            {
                IECPropertyValue property=null;
                try { property=instance[Names[i]]; } catch { }
                if(property==null) throw new InvalidOperationException("附加项“"+name+"”缺少属性："+Names[i]);
                if(Kinds[i]==CustomProperty.TypeKind.Double)
                    property.DoubleValue=Convert.ToDouble(values[i],CultureInfo.InvariantCulture);
                else if(Kinds[i]==CustomProperty.TypeKind.Integer)
                    property.IntValue=Convert.ToInt32(values[i],CultureInfo.InvariantCulture);
                else
                    property.StringValue=values[i]==null?""
                        :Convert.ToString(values[i],CultureInfo.InvariantCulture);
            }
            StatusInt status;
            using(StatisticsTrace.Section("WriteChanges")) { status=instance.WriteChanges(); }
            if(status!=StatusInt.Success)
                throw new InvalidOperationException("无法写入附加项“"+name+"”的属性值："+status);
            if(StatisticsTrace.Enabled)
            {
                // 临时校验：确认值真的落在实例上，而不是留在类型默认值里（取数后可删）。
                string readBack;
                try
                {
                    var probe=instance["DesignLengthMm"];
                    readBack=probe==null?"<无属性>"
                        :probe.DoubleValue.ToString("F3",CultureInfo.InvariantCulture);
                }
                catch { readBack="<回读失败>"; }
                StatisticsTrace.Note(name+" 回读长度",readBack);
            }
        }
        private static void AddEntry(IList<KeyValuePair<string,object[]>> entries,string name,
            string kind,string supportType,string assemblyTag,string componentName,string spec,
            double length,int quantity,string unit,string pipeNumber)
        {
            entries.Add(new KeyValuePair<string,object[]>(name,
                new object[]{kind,supportType,assemblyTag,componentName,spec,length,quantity,unit,
                    pipeNumber??""}));
        }
        internal static void Attach(Element element,FamilyData family,ProfileData profile,double lengthMm)
        {
            using(StatisticsTrace.Scope("型钢生成 Attach")) {
                var entries=new List<KeyValuePair<string,object[]>>();
                AddEntry(entries,"PipeSupportAssembly_STEEL_SECTION","Assembly","型钢","",
                    "支吊架",profile.Name,0.0,1,"套","");
                AddEntry(entries,"PipeSupportComponent_STEEL_SECTION","Component","型钢","",
                    family.Label,profile.Name,lengthMm,1,"根","");
                WriteRecords(element,entries);
            }
        }
        /// <summary>弯头耳轴的一条构件记录。<paramref name="role"/> 是<b>构件角色码</b>
        /// （TRUNNION / PLATE / LINER），用于固定 ItemType 名 —— 同一元素上三条记录的角色必须互不相同，
        /// 不能用随实例变化的中文构件名（竖直耳轴 / 水平耳轴 / 底板 / 端板 会随选项而变）。</summary>
        internal static void AttachElbowTrunnion(Element element,ElbowTrunnionPlan plan,string role,
            string componentName,string specification,double designLengthMm,bool includeAssembly)
        {
            if(element==null||plan==null)throw new ArgumentNullException("element");
            using(StatisticsTrace.Scope("弯头耳轴 AttachElbowTrunnion")) {
                string feature=plan.SupportCode;          // ASCII 代号，只用于 ItemType 命名
                string supportType=ElbowTrunnionCatalog.SupportType(feature);  // 属性值用中文类型名
                string tag=plan.AssemblyTag;
                string pipe=plan.Selection.PipeNumber??"";
                var entries=new List<KeyValuePair<string,object[]>>();
                if(includeAssembly)
                    AddEntry(entries,"PipeSupportAssembly_"+feature,"Assembly",supportType,tag,
                        "支吊架",tag,0.0,1,"套",pipe);
                AddEntry(entries,"PipeSupportComponent_"+feature+"_"+role,"Component",supportType,
                    tag,componentName,specification,designLengthMm,1,"件",pipe);
                WriteRecords(element,entries);
            }
        }
        internal static void AttachE1Guide(Element element,E1GuidePlan plan)
        {
            if(element==null||plan==null)throw new ArgumentNullException("element");
            using(StatisticsTrace.Scope("E1 导向架 AttachE1Guide")) {
                string supportType=E1GuideCatalog.SupportType;      // 属性值用中文类型名
                string pipe=plan.PipeNumber??"";
                var entries=new List<KeyValuePair<string,object[]>>();
                AddEntry(entries,"PipeSupportAssembly_E1","Assembly",supportType,plan.Number,
                    "支吊架","DN"+plan.Dn+" / "+plan.Item.Specification,0.0,1,"套",pipe);
                AddEntry(entries,"PipeSupportComponent_E1_MEMBER","Component",supportType,
                    plan.Number,"构件A",plan.Item.Specification+" / "+plan.Material,
                    plan.HeightMm,2,"件",pipe);
                if(plan.Stainless)
                {
                    string spec="□"+plan.Item.LinerWidthMm.ToString("G",CultureInfo.InvariantCulture)+"×"+
                        plan.Item.LinerHeightMm.ToString("G",CultureInfo.InvariantCulture)+"×"+
                        plan.Item.LinerThicknessMm.ToString("G",CultureInfo.InvariantCulture)+" / 06Cr18Ni9";
                    AddEntry(entries,"PipeSupportComponent_E1_LINER","Component",supportType,
                        plan.Number,"不锈钢薄板",spec,plan.Item.LinerHeightMm,2,"件",pipe);
                }
                WriteRecords(element,entries);
            }
        }
        /// <summary>G2 混凝土锚板：1 条 Assembly + 锚板 + 膨胀锚栓。</summary>
        internal static void AttachG2Anchor(Element element,G2AnchorPlan plan)
        {
            if(element==null||plan==null)throw new ArgumentNullException("element");
            using(StatisticsTrace.Scope("G2 锚板 AttachG2Anchor")) {
                string supportType=G2AnchorCatalog.SupportType;
                var entries=new List<KeyValuePair<string,object[]>>();
                AddEntry(entries,"PipeSupportAssembly_G2","Assembly",supportType,plan.AssemblyTag,
                    "支吊架",plan.AssemblySpecification,0.0,1,"套","");
                AddEntry(entries,"PipeSupportComponent_G2_PLATE","Component",supportType,
                    plan.AssemblyTag,"锚板",plan.PlateSpecification,plan.PlateThicknessMm,1,"块","");
                AddEntry(entries,"PipeSupportComponent_G2_BOLT","Component",supportType,
                    plan.AssemblyTag,"膨胀锚栓",plan.BoltSpecification,plan.BoltLengthMm,
                    plan.BoltCount,"套","");
                WriteRecords(element,entries);
            }
        }
        /// <summary>A1 U 型管卡：整组、U 型螺栓和四颗螺母；通板没有建模也不入清单。</summary>
        internal static void AttachA1Clamp(Element element,A1ClampPlan plan)
        {
            if(element==null||plan==null)throw new ArgumentNullException("element");
            using(StatisticsTrace.Scope("A1 管卡 AttachA1Clamp")) {
                var entries=new List<KeyValuePair<string,object[]>>();
                AddEntry(entries,"PipeSupportAssembly_A1","Assembly",A1ClampCatalog.SupportType,
                    plan.AssemblyTag,"支吊架",plan.AssemblySpecification,0,1,"套",plan.PipeNumber);
                AddEntry(entries,"PipeSupportComponent_A1_U_BOLT","Component",A1ClampCatalog.SupportType,
                    plan.AssemblyTag,"U型螺栓",plan.BoltSpecification,plan.BoltLengthMm,1,"件",plan.PipeNumber);
                AddEntry(entries,"PipeSupportComponent_A1_NUT","Component",A1ClampCatalog.SupportType,
                    plan.AssemblyTag,"螺母",plan.NutSpecification,0,4,"件",plan.PipeNumber);
                WriteRecords(element,entries);
            }
        }
        /// <summary>A2 标准型 2 螺栓管夹：1 条 Assembly + 管架本体 + 螺栓 ×2。</summary>
        internal static void AttachA2Clamp(Element element,A2ClampPlan plan)
        {
            if(element==null||plan==null)throw new ArgumentNullException("element");
            using(StatisticsTrace.Scope("A2 管夹 AttachA2Clamp")) {
                string supportType=A2ClampCatalog.SupportType;
                var entries=new List<KeyValuePair<string,object[]>>();
                AddEntry(entries,"PipeSupportAssembly_A2","Assembly",supportType,plan.AssemblyTag,
                    "支吊架",plan.AssemblySpecification,0.0,1,"套","");
                AddEntry(entries,"PipeSupportComponent_A2_BODY","Component",supportType,
                    plan.AssemblyTag,"管架本体",plan.BodySpecification,plan.WidthMm,1,"件","");
                AddEntry(entries,"PipeSupportComponent_A2_BOLT","Component",supportType,
                    plan.AssemblyTag,"螺栓",plan.BoltSpecification,0.0,2,"套","");
                WriteRecords(element,entries);
            }
        }
        /// <summary>A22 保冷管用 2 螺栓管夹：总成、两片本体和两套紧固件。</summary>
        internal static void AttachA22Clamp(Element element,A22ClampPlan plan)
        {
            if(element==null||plan==null) throw new ArgumentNullException("element");
            using(StatisticsTrace.Scope("A22 管夹 AttachA22Clamp")) {
                var entries=new List<KeyValuePair<string,object[]>>();
                AddEntry(entries,"PipeSupportAssembly_A22","Assembly",A22ClampCatalog.SupportType,
                    plan.Number,"支吊架",plan.Specification,0.0,1,"套","");
                AddEntry(entries,"PipeSupportComponent_A22_BODY","Component",A22ClampCatalog.SupportType,
                    plan.Number,"管夹本体（上、下半）",plan.Specification,plan.W,2,"件","");
                AddEntry(entries,"PipeSupportComponent_A22_BOLT","Component",A22ClampCatalog.SupportType,
                    plan.Number,"螺栓及螺母", "M"+plan.BoltDiameterMm,0.0,2,"套","");
                AddEntry(entries,"PipeSupportComponent_A22_WASHER","Component",A22ClampCatalog.SupportType,
                    plan.Number,"垫圈","M"+plan.BoltDiameterMm,0.0,4,"件","");
                WriteRecords(element,entries);
            }
        }
        /// <summary>A24 总成、两片本体、四套紧固件和八只垫圈。</summary>
        internal static void AttachA24Clamp(Element element,A22ClampPlan plan)
        {
            if(element==null||plan==null) throw new ArgumentNullException("element");
            using(StatisticsTrace.Scope("A24 管夹 AttachA24Clamp")) {
                var entries=new List<KeyValuePair<string,object[]>>();
                AddEntry(entries,"PipeSupportAssembly_A24","Assembly",A24ClampCatalog.SupportType,
                    plan.Number,"支吊架",plan.Specification,0.0,1,"套","");
                AddEntry(entries,"PipeSupportComponent_A24_BODY","Component",A24ClampCatalog.SupportType,
                    plan.Number,"管夹本体（上、下半）",plan.Specification,plan.W,2,"件","");
                AddEntry(entries,"PipeSupportComponent_A24_BOLT","Component",A24ClampCatalog.SupportType,
                    plan.Number,"螺栓及螺母","M"+plan.BoltDiameterMm,0.0,4,"套","");
                AddEntry(entries,"PipeSupportComponent_A24_WASHER","Component",A24ClampCatalog.SupportType,
                    plan.Number,"垫圈","M"+plan.BoltDiameterMm,0.0,8,"件","");
                WriteRecords(element,entries);
            }
        }
        /// <summary>K1 不保温管限位架：1 条 Assembly + 限位块 ×2 + 可选底板 ×2。</summary>
        internal static void AttachK1Limit(Element element,K1LimitPlan plan)
        {
            if(element==null||plan==null)throw new ArgumentNullException("element");
            using(StatisticsTrace.Scope("K1 限位架 AttachK1Limit")) {
                string supportType=K1LimitCatalog.SupportType;
                var entries=new List<KeyValuePair<string,object[]>>();
                AddEntry(entries,"PipeSupportAssembly_K1","Assembly",supportType,plan.Number,
                    "支吊架",plan.Specification,0.0,1,"套","");
                AddEntry(entries,"PipeSupportComponent_K1_BLOCK","Component",supportType,
                    plan.Number,"限位块（型钢）",plan.Specification,plan.SizeMm,2,"件","");
                if(plan.Plate!=null)
                {
                    string spec=plan.Plate[0].ToString("0",CultureInfo.InvariantCulture)+"×"+
                        plan.Plate[1].ToString("0",CultureInfo.InvariantCulture)+"×"+
                        plan.Plate[2].ToString("0",CultureInfo.InvariantCulture);
                    AddEntry(entries,"PipeSupportComponent_K1_PLATE","Component",supportType,
                        plan.Number,"底板",spec,plan.Plate[2],2,"块","");
                }
                WriteRecords(element,entries);
            }
        }
        /// <summary>T4 高温隔热限位管托：1 条 Assembly + 承重板 / 底座 / 耳板 / 螺栓
        /// （可选管道与保温层）。构件角色码由 <c>T4ShoeCalculator.ComponentItems</c> 给出
        /// （Pipe / Insulation / ClampUpper / ClampLower / Base / Ear / Bolt），同一元素内互不重复。</summary>
        internal static void AttachT4Shoe(Element element,T4ShoeLayout layout,
            T4ShoeBooleanLayout boolean,bool builtPipe,bool builtInsulation)
        {
            if(element==null||layout==null)throw new ArgumentNullException("element");
            using(StatisticsTrace.Scope("T4 管托 AttachT4Shoe")) {
                string supportType=T4ShoeCatalog.SupportType;
                var entries=new List<KeyValuePair<string,object[]>>();
                AddEntry(entries,"PipeSupportAssembly_T4","Assembly",supportType,layout.Number,
                    "支吊架","DN"+layout.Dn.ToString(CultureInfo.InvariantCulture),0.0,1,"套","");
                foreach(var item in T4ShoeCalculator.ComponentItems(layout,boolean,builtPipe,builtInsulation))
                {
                    double length;double.TryParse(item[3],NumberStyles.Float,
                        CultureInfo.InvariantCulture,out length);
                    int quantity;int.TryParse(item[4],NumberStyles.Integer,
                        CultureInfo.InvariantCulture,out quantity);
                    AddEntry(entries,"PipeSupportComponent_T4_"+item[0],"Component",supportType,
                        layout.Number,item[1],item[2],length,quantity,item[5],"");
                }
                WriteRecords(element,entries);
            }
        }
        internal static void AttachL2Shoe(Element element,T4ShoeLayout layout,
            T4ShoeBooleanLayout boolean,bool builtPipe,bool builtInsulation)
        {
            if(element==null||layout==null)throw new ArgumentNullException("element");
            using(StatisticsTrace.Scope("L2 管托 AttachL2Shoe")) {
                var entries=new List<KeyValuePair<string,object[]>>();
                AddEntry(entries,"PipeSupportAssembly_L2","Assembly",L2ShoeCatalog.SupportType,
                    layout.Number,"支吊架",L2ShoeCalculator.Describe(layout,boolean),
                    0.0,1,"套","");
                foreach(var item in T4ShoeCalculator.ComponentItems(layout,boolean,builtPipe,builtInsulation))
                {
                    double length;double.TryParse(item[3],NumberStyles.Float,
                        CultureInfo.InvariantCulture,out length);
                    int quantity;int.TryParse(item[4],NumberStyles.Integer,
                        CultureInfo.InvariantCulture,out quantity);
                    string name=item[0]=="Insulation"?"保冷层":item[1];
                    AddEntry(entries,"PipeSupportComponent_L2_"+item[0],"Component",
                        L2ShoeCatalog.SupportType,layout.Number,name,item[2],length,
                        quantity,item[5],"");
                }
                WriteRecords(element,entries);
            }
        }
        internal static void AttachVerticalPipeSupport(Element element,VerticalPipeSupportPlan plan)
        {
            if(element==null||plan==null)throw new ArgumentNullException("element");
            using(StatisticsTrace.Scope("立管耳轴 AttachVerticalPipeSupport")) {
                string feature=plan.Kind==VerticalPipeSupportKind.F10?"VP_EAR_PLATE":"VP_TRUNNION";
                string supportType=VerticalPipeSupportCatalog.SupportType(plan.Kind);
                string pipe=plan.PipeNumber??"";
                var entries=new List<KeyValuePair<string,object[]>>();
                AddEntry(entries,"PipeSupportAssembly_"+feature,"Assembly",supportType,plan.Number,
                    "支吊架",plan.Specification,0.0,1,"套",pipe);
                if(plan.Kind==VerticalPipeSupportKind.F10)
                {
                    AddVertical(entries,feature,supportType,plan,pipe,"EAR","耳板",
                        "耳板 "+plan.EarWidthMm+"×"+plan.EarHeightMm+"×10 "+plan.Material,
                        plan.EarWidthMm,2,"块");
                    AddVertical(entries,feature,supportType,plan,pipe,"BASE","底板",
                        "70×120×10 Q235B",120,2,"块");
                    if(plan.Fixed) AddVertical(entries,feature,supportType,plan,pipe,"BOLT","螺栓",
                        "M12×40 单头螺栓",40,4,"套");
                }
                else
                {
                    AddVertical(entries,feature,supportType,plan,pipe,"TRUNNION","耳轴",
                        "耳轴 "+VerticalPipeSupportCatalog.Nps(plan.TrunnionDn)+" Φ"+
                        plan.TrunnionOd+"×"+plan.WallMm+" "+plan.Material,
                        plan.LengthMm,plan.Count,"件");
                    if(plan.EndPlateThicknessMm>0) AddVertical(entries,feature,supportType,plan,
                        pipe,"END","端板","端板 "+plan.EndType+" Φ"+(plan.TrunnionOd+12)+
                        "×"+plan.EndPlateThicknessMm,plan.TrunnionOd+12,plan.Count,"块");
                    if(plan.PadThicknessMm>0) AddVertical(entries,feature,supportType,plan,
                        pipe,"PAD","补强板","补强板 Φ"+(plan.TrunnionOd+2*plan.PadWidthMm)+
                        "×"+plan.PadThicknessMm,plan.TrunnionOd+2*plan.PadWidthMm,plan.Count,"块");
                }
                WriteRecords(element,entries);
            }
        }
        private static void AddVertical(IList<KeyValuePair<string,object[]>> entries,string feature,
            string supportType,VerticalPipeSupportPlan plan,string pipe,string code,string name,
            string spec,double length,int quantity,string unit)
        {
            AddEntry(entries,"PipeSupportComponent_"+feature+"_"+code,"Component",supportType,
                plan.Number,name,spec,length,quantity,unit,pipe);
        }
        internal static void AttachN8(Element element,N8Plan plan)
        {
            if(element==null||plan==null)throw new ArgumentNullException("element");
            using(StatisticsTrace.Scope("N8 AttachN8")) {
                string supportType=N8Catalog.SupportType;
                var entries=new List<KeyValuePair<string,object[]>>();
                AddEntry(entries,"PipeSupportAssembly_N8","Assembly",supportType,plan.Number,
                    "支吊架",plan.Specification,0.0,1,"套","");
                AddEntry(entries,"PipeSupportComponent_N8_PLATE","Component",supportType,
                    plan.Number,"连接板",plan.E+"×"+plan.E+"×"+plan.T,plan.T,1,"件","");
                AddEntry(entries,"PipeSupportComponent_N8_BOLT","Component",supportType,plan.Number,
                    "连接板螺栓","M"+plan.BoltDiameter+"×"+plan.BoltLength,plan.BoltLength,
                    plan.BoltCount,"件","");
                WriteRecords(element,entries);
            }
        }
        /// <summary>N3 单三角架 / N4 双三角架：1 条 Assembly + 横担 / 斜撑 /（连接横担）+ 连接板 /
        /// 螺栓 / 筋板。构件角色后缀 A / B / C / PLATE / BOLT / STIFFENER 在同一元素内互不重复。</summary>
        internal static void AttachBracket(Element element,BracketPlan plan)
        {
            if(element==null||plan==null)throw new ArgumentNullException("element");
            using(StatisticsTrace.Scope("三角架 AttachBracket")) {
                string code=BracketCatalog.SupportCode(plan.Double);
                string type=BracketCatalog.SupportType(plan.Double);
                var entries=new List<KeyValuePair<string,object[]>>();
                AddEntry(entries,"PipeSupportAssembly_"+code,"Assembly",type,plan.Number,
                    "支吊架",plan.Specification,0.0,1,"套","");
                AddBracketPart(entries,code,type,plan,"A","构件A（横担）",plan.SectionA,
                    plan.BeamLength,plan.Double?2:1,"件");
                AddBracketPart(entries,code,type,plan,"B","构件B（斜撑）",plan.SectionB,
                    Math.Sqrt(2)*plan.BraceRun,plan.Double?2:1,"件");
                if(plan.Double)AddBracketPart(entries,code,type,plan,"C",
                    "构件C（连接横担）",plan.SectionC,plan.ConnectorSpan,2,"件");
                var plate=N8Catalog.Resolve(plan.PlateType,"N",0,G2MountFace.Wall);
                int count=plan.Double?4:2;
                AddBracketPart(entries,code,type,plan,"PLATE","连接板",
                    plate.E+"×"+plate.E+"×"+plate.T,plate.T,count,"件");
                AddBracketPart(entries,code,type,plan,"BOLT","连接板螺栓",
                    "M"+plate.BoltDiameter+"×"+plate.BoltLength,plate.BoltLength,
                    count*plate.BoltCount,"件");
                AddBracketPart(entries,code,type,plan,"STIFFENER","筋板",
                    "10 厚",10,plan.Double?6:1,"件");
                WriteRecords(element,entries);
            }
        }
        /// <summary>D5/D6/G12/D19：固定角色名，全部实例值一次 EnsureBatch 后写入。</summary>
        internal static void AttachLBracket(Element element,LBracketPlan plan)
        {
            if(element==null||plan==null)throw new ArgumentNullException("element");
            using(StatisticsTrace.Scope("D7 L 型架 AttachLBracket")) {
                var entries=new List<KeyValuePair<string,object[]>>();
                string type=LBracketCatalog.SupportType,tag=plan.Number;
                AddEntry(entries,LBracketCatalog.AssemblyItemName,"Assembly",type,tag,
                    "支吊架",plan.Specification,0,1,"套","");
                AddEntry(entries,LBracketCatalog.ComponentItemName("Post"),"Component",type,tag,
                    "立杆",plan.Variant.Specification,plan.PostCutLengthMm,1,"件","");
                AddEntry(entries,LBracketCatalog.ComponentItemName("Arm"),"Component",type,tag,
                    "横担",plan.Variant.Specification,plan.ArmCutLengthMm,1,"件","");
                WriteRecords(element,entries);
            }
        }
        internal static void AttachTriangleBracket(Element element,TriangleBracketPlan plan)
        {
            if(element==null||plan==null)throw new ArgumentNullException("element");
            using(StatisticsTrace.Scope("D5/D6/G12/D19 三角架 AttachTriangleBracket")) {
                string type=plan.SupportType,tag=plan.Number;
                var entries=new List<KeyValuePair<string,object[]>>();
                AddEntry(entries,TriangleBracketCatalog.AssemblyItemName(plan.Parameters.Kind),"Assembly",type,tag,
                    "支吊架",plan.AssemblySpecification,0.0,1,"套","");
                AddTrianglePart(entries,plan.Parameters.Kind,type,tag,"A","构件A（横担）",plan.Variant.SectionA,
                    plan.BeamLengthMm,plan.QuantityA);
                AddTrianglePart(entries,plan.Parameters.Kind,type,tag,"B","构件B（斜撑）",
                    plan.Variant.SectionB+"（45°）",plan.BraceLengthMm,plan.QuantityB);
                if(plan.Parameters.Kind=="D19")
                {
                    var v=plan.Variant;
                    string spec=v.ConnectorLength+"×"+v.ConnectorHeight+"×"+
                        v.ConnectorThickness+" 钢板（S="+v.WebGap+"）";
                    AddTrianglePart(entries,plan.Parameters.Kind,type,tag,"C","构件C（端部连接板）",
                        spec,v.ConnectorThickness,1);
                }
                if(plan.Parameters.Kind=="G12")
                {
                    var item=G2AnchorCatalog.Require(plan.Variant.BoltSubtype);
                    string spec="M"+item.BoltDiameterMm+"×"+item.BoltLengthMm+
                        "（横担 2 + 斜撑 2，S="+plan.Variant.BoltSpacing+
                        "，C="+plan.Variant.BoltEdge+"）";
                    AddTrianglePart(entries,plan.Parameters.Kind,type,tag,"C","构件C（膨胀锚栓）",
                        spec,item.BoltLengthMm,4);
                }
                if(plan.Plate!=null)
                {
                    AddTrianglePart(entries,plan.Parameters.Kind,type,tag,"PLATE_A","G2 端板（横担）",
                        plan.Plate.PlateSpecification,plan.Plate.PlateThicknessMm,1);
                    AddTrianglePart(entries,plan.Parameters.Kind,type,tag,"PLATE_B","G2 端板（斜撑）",
                        plan.Plate.PlateSpecification,plan.Plate.PlateThicknessMm,1);
                    AddTrianglePart(entries,plan.Parameters.Kind,type,tag,"BOLT_A","G2 膨胀锚栓（横担）",
                        plan.Plate.BoltSpecification,plan.Plate.BoltLengthMm,4);
                    AddTrianglePart(entries,plan.Parameters.Kind,type,tag,"BOLT_B","G2 膨胀锚栓（斜撑）",
                        plan.Plate.BoltSpecification,plan.Plate.BoltLengthMm,4);
                }
                WriteRecords(element,entries);
            }
        }
        /// <summary>D8/D13/G5/G6 门型架：每种架型使用固定附加项名，规格与编号只写实例值。</summary>
        internal static void AttachPortalFrame(Element element,PortalFramePlan plan)
        {
            if(element==null||plan==null)throw new ArgumentNullException("element");
            using(StatisticsTrace.Scope("门型架 AttachPortalFrame")) {
                string kind=plan.Parameters.Kind,type=plan.SupportType,tag=plan.Number;
                var v=plan.Variant;
                var entries=new List<KeyValuePair<string,object[]>>();
                AddEntry(entries,PortalFrameCatalog.AssemblyItemName(kind),"Assembly",type,tag,
                    "支吊架",plan.AssemblySpecification,0,1,"套","");
                AddPortalPart(entries,kind,type,tag,"Post","立柱",v.PostSpecification,
                    plan.PostLengthMm,2,"件");
                AddPortalPart(entries,kind,type,tag,"Arm","横担",v.ArmSpecification,
                    kind=="G6"?plan.SpanMm:plan.ArmLengthMm,plan.ArmQuantity,"件");
                if(v.Ground!=null)
                {
                    var g=v.Ground;
                    string plate=g.PlateSide+"×"+g.PlateSide+"×"+g.PlateThickness;
                    AddPortalPart(entries,kind,type,tag,"AnchorPlate","锚板",plate,
                        g.PlateThickness,2,"块");
                    AddPortalPart(entries,kind,type,tag,"AnchorBolt","膨胀锚栓",
                        "M"+g.BoltDiameter+"×"+g.BoltLength,g.BoltLength,8,"根");
                    AddPortalPart(entries,kind,type,tag,"Nut","螺母","M"+g.BoltDiameter,
                        0,8,"个");
                    AddPortalPart(entries,kind,type,tag,"GroundGrout","现场灌浆",
                        "高 25（底面向外扩 20 的梯台）",25,2,"处");
                }
                WriteRecords(element,entries);
            }
        }
        /// <summary>D12/G4/D15 T 型架：固定组合代号与角色，预览期间不触碰公共库。</summary>
        internal static void AttachTFrame(Element element,TFramePlan plan)
        {
            if(element==null||plan==null)throw new ArgumentNullException("element");
            using(StatisticsTrace.Scope("T 型架 AttachTFrame")) {
                string kind=plan.Parameters.Kind,type=plan.SupportType,tag=plan.Number;
                var v=plan.Variant;
                var entries=new List<KeyValuePair<string,object[]>>();
                AddEntry(entries,TFrameCatalog.AssemblyItemName(kind),"Assembly",type,tag,
                    "支吊架",plan.AssemblySpecification,0,1,"套","");
                bool horizontal=kind=="D15";
                AddTPart(entries,kind,type,tag,horizontal?"MemberA":"Post",
                    horizontal?"构件A":"立柱",v.SpecA,plan.PostLengthMm,1,"根");
                AddTPart(entries,kind,type,tag,horizontal?"MemberB":"Arm",
                    horizontal?"构件B":"横担",v.SpecB,plan.L2Mm,1,"根");
                if(v.Ground!=null)
                {
                    var g=v.Ground;
                    AddTPart(entries,kind,type,tag,"AnchorPlate","锚板",
                        "E×E×T="+g.PlateSide+"×"+g.PlateSide+"×"+g.PlateThickness+
                        "，4-φ"+g.HoleDiameter+" 孔（F="+g.HoleSpacing+"）",
                        g.PlateThickness,1,"块");
                    AddTPart(entries,kind,type,tag,"AnchorBolt","膨胀锚栓",
                        "M"+g.BoltDiameter+"×"+g.BoltLength+"（h_ef="+g.Embedment+"）",
                        g.BoltLength,4,"套");
                    AddTPart(entries,kind,type,tag,"AnchorNut","螺母",
                        "M"+g.BoltDiameter,0,4,"个");
                    AddTPart(entries,kind,type,tag,"Grout","现场灌浆",
                        "高 25，每边斜向外扩 20（梯台）",25,1,"处");
                }
                WriteRecords(element,entries);
            }
        }
        /// <summary>Y2 / 弯头垫板各一套固定 ItemType，实例尺寸仅写在字段中。</summary>
        internal static void AttachPadPlate(Element element,PadPlatePlan plan)
        {
            if(element==null||plan==null)throw new ArgumentNullException("element");
            using(StatisticsTrace.Scope("垫板 AttachPadPlate")) {
                var entries=new List<KeyValuePair<string,object[]>>();
                AddEntry(entries,PadPlateCatalog.AssemblyItemName(plan.Kind),"Assembly",
                    plan.SupportType,plan.Number,"支吊架",plan.Specification,0,1,"套",plan.PipeNumber);
                AddEntry(entries,PadPlateCatalog.ComponentItemName(plan.Kind),"Component",
                    plan.SupportType,plan.Number,plan.Kind==PadPlateKind.Y2?"弧形垫板":"弯头垫板",
                    plan.Specification,plan.ComponentLengthMm,1,"件",plan.PipeNumber);
                WriteRecords(element,entries);
            }
        }
        private static void AddTPart(IList<KeyValuePair<string,object[]>> entries,
            string kind,string type,string tag,string role,string name,string spec,
            double length,int quantity,string unit)
        {
            AddEntry(entries,TFrameCatalog.ComponentItemName(kind,role),"Component",type,tag,
                name,spec,length,quantity,unit,"");
        }
        private static void AddPortalPart(IList<KeyValuePair<string,object[]>> entries,
            string kind,string type,string tag,string role,string name,string spec,
            double length,int quantity,string unit)
        {
            AddEntry(entries,PortalFrameCatalog.ComponentItemName(kind,role),"Component",type,tag,
                name,spec,length,quantity,unit,"");
        }
        private static void AddTrianglePart(IList<KeyValuePair<string,object[]>> entries,
            string kind,string type,string tag,string role,string name,string spec,
            double length,int quantity)
        {
            AddEntry(entries,TriangleBracketCatalog.ComponentItemName(kind,role),"Component",type,tag,
                name,spec,length,quantity,"件","");
        }
        private static void AddBracketPart(IList<KeyValuePair<string,object[]>> entries,string code,
            string type,BracketPlan plan,string suffix,string name,string spec,double length,
            int quantity,string unit)
        {
            AddEntry(entries,"PipeSupportComponent_"+code+"_"+suffix,"Component",type,plan.Number,
                name,spec,length,quantity,unit,"");
        }
    }
}
