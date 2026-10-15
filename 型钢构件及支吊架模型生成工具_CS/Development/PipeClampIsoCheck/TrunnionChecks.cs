using System;
using System.Linq;
using Bentley.DgnPlatformNET.Elements;
using Bentley.GeometryNET;
using Bentley.OpenPlant.Modeler.Api;

namespace SteelSectionProbe
{
    internal static partial class Program
    {
        private static VerticalPipeSupportPreviewSession VerticalPreview(VerticalPipeSupportKind kind = VerticalPipeSupportKind.F6,
            double scale = 1000, bool native = true, double angle = 37)
        {
            World.Reset(); Statistics.TrunnionAttachments = 0;
            Bentley.MstnPlatformNET.Session.Instance.Model.Scale = scale;
            World.Pipe.SourceUorPerMm = scale; World.Pipe.IsPipe = native;
            World.Pipe.EndX = World.Pipe.StartX; World.Pipe.EndZ = World.Pipe.StartZ + 2000;
            int dn = kind == VerticalPipeSupportKind.F10 ? 25 : 100;
            World.Pipe.NominalMm = dn; World.Source["NOMINAL_DIAMETER"].DoubleValue = dn;
            var plan = VerticalPipeSupportCalculator.Calculate(new VerticalPipeSupportParameters {
                Kind = kind, PipeDn = dn, TrunnionDn = 50, LengthMm = 500, AzimuthDegrees = angle,
                BuildPad = true, PadThicknessMm = 5, F10Fixed = true }, true, dn, "PIPE-X");
            var session = new VerticalPipeSupportPreviewSession();
            session.Show(plan, new DPoint3d(1000*scale,2000*scale,3600*scale), new DVector3d(0,0,2000), World.Pipe);
            Check(World.Elements.Count == 1 && World.Displays.Count == 1, "立管预览仅暂态，无模型根");
            return session;
        }

        private static ElbowTrunnionPlan ElbowPlan(ElbowOrientation elbow, TrunnionOrientation orientation,
            double scale, bool native = true, bool ptfe = false, bool bottom = false, bool outlet = false)
        {
            World.Reset(); Statistics.TrunnionAttachments = 0;
            Bentley.MstnPlatformNET.Session.Instance.Model.Scale = scale;
            World.Source.ClassDefinition.Name = "LONG_RADIUS_90_DEGREE_ELBOW";
            double c = Math.Cos(.6), s = Math.Sin(.6);
            var m = elbow == ElbowOrientation.Vertical
                ? new[] { c,-s,0,1000*scale, s,c,0,2000*scale, 0d,0,1,3000*scale }
                : new[] { c,0,-s,1000*scale, s,0,c,2000*scale, 0d,-1,0,3000*scale };
            var frame = ElbowTrunnionCalculator.Frame(m, scale, 150, 150, elbow, true);
            var source = new ElbowTrunnionSelection { ElementId = 1, MainDn = 100, OutsideDiameterMm = 114.3,
                ClassName = "OpenPlant_3D.LONG_RADIUS_90_DEGREE_ELBOW", NativeParentInstanceId = World.Source.InstanceId,
                NativeModelToken = 1, SourceUorPerMm = scale, Frame = frame, IsNativePipingElbow = native, PipeNumber = "PIPE-X" };
            ElbowTrunnionReader.Current = source;
            return ElbowTrunnionCalculator.Calculate(source, new ElbowTrunnionParameters { Elbow = elbow,
                Trunnion = orientation, ExtentMm = 650, Ptfe = ptfe, BottomFlat = bottom, OutletSide = outlet,
                NamingUnit = PipeNamingUnit.Imperial, WallOverrideMm = 4.2 });
        }

        private static NativePipeSupportRecipe CheckTrunnionResult(string code, int attachments)
        {
            var created = World.Created;
            string expectedClass = NativePipeSupportDefinition.StockTrunnionClass(code);
            Check(created != null && created.IsParametric && created.Instance.ClassDefinition.Name == expectedClass,
                "耳轴落自带类且参数化外形 " + expectedClass);
            Check(created.Instance.Parent == World.Source, "父构件关联");
            Check(World.Elements.Count == 2 && World.Displays.Count == 0, "确认仅一根，暂态释放");
            Check(Statistics.TrunnionAttachments == attachments, "原材料组件只写一次");
            Check(created.Instance["STATE"].StringValue == "Design" && created.Instance["SHOP_FIELD"].StringValue == "SHOP", "耳轴出图状态");
            string json = created.Instance["SSP_RECIPE"].StringValue;
            var recipe = NativePipeSupportRecipeCodec.Decode(json);
            Check(recipe.Code == code && NativePipeSupportRecipeCodec.Encode(recipe) == json, "耳轴枚举/字符/只读向量完整往返");
            string tag = recipe.Vertical != null ? recipe.Vertical.Number : recipe.Elbow.AssemblyTag;
            Check(created.Instance["ALIAS"].StringValue == tag && World.Find(created.Instance).MaterialTag == tag, "ISO与原材料编号一致");
            for (int i = 0; i < 3; i++) Check(Math.Abs(created.GetDoubleValueInMM("SUPPORT_POINT_"+"XYZ"[i])-recipe.CenterMm[i]) < 1e-6, "ISO点毫米保存");
            var cell = World.Find(created.Instance);
            using (var local = NativePipeSupportRecipeGraphics.BuildLocal(recipe))
                SameGeometry(cell.Geometry, local.Geometry.Select(created.Transform3d.Apply).ToArray());
            var moved = created.Transform3d;
            moved.Translation = new DPoint3d(moved.Translation.X+400, moved.Translation.Y-200, moved.Translation.Z+700);
            created.Transform3d = moved;
            using (var a = NativePipeSupportRecipeGraphics.BuildLocal(recipe))
            using (var b = NativePipeSupportRecipeGraphics.BuildLocal(NativePipeSupportRecipeCodec.Decode(json)))
                SameGeometry(a.Geometry.Select(moved.Apply).ToArray(), b.Geometry.Select(moved.Apply).ToArray());
            Check(created.Instance["SSP_RECIPE"].StringValue == json, "编辑不追写初始世界定位配方");
            var script = new NativePipeSupportComponent {
                BMECObject = new ParametricSetupValues { Source = created.Instance, ParentReady = true } };
            script.PrepareGraphics();
            if (recipe.Elbow != null)
            {
                Check(!recipe.AllowManualEditHandles && script.LengthCalls == 0 && script.HostCalls == 1,
                    "弯头耳轴关闭手动操作柄：不设操作长度，仍初始化父端口");
            }
            else
            {
                Check(recipe.AllowManualEditHandles && script.LengthCalls == 1 && script.HostCalls == 1,
                    "立管耳轴保留操作长度与父端口初始化");
                // 自带耳轴：局部 X=管轴，局部 −Z=方位伸出。Z 若沿管，旋转柄会落在立管上。
                DTransform3d expected, unused;
                NativePipeSupportSource.PlacementFrame(recipe, Bentley.MstnPlatformNET.Session.Instance.Model.Scale, out expected, out unused);
                var x = created.Transform3d.Matrix.X;
                var z = created.Transform3d.Matrix.Z;
                Check(Math.Abs(x.X - expected.Matrix.X.X) < 1e-9 && Math.Abs(x.Y - expected.Matrix.X.Y) < 1e-9
                    && Math.Abs(x.Z - expected.Matrix.X.Z) < 1e-9, "立管耳轴局部X沿管轴");
                Check(Math.Abs(z.X - expected.Matrix.Z.X) < 1e-9 && Math.Abs(z.Y - expected.Matrix.Z.Y) < 1e-9
                    && Math.Abs(z.Z - expected.Matrix.Z.Z) < 1e-9, "立管耳轴局部Z为耳轴反向");
                if (Math.Abs(recipe.Vertical.AzimuthDegrees) < 1e-9 && recipe.Vertical.Kind != VerticalPipeSupportKind.F10)
                {
                    Check(Math.Abs(x.X) < 1e-9 && Math.Abs(x.Y) < 1e-9 && Math.Abs(x.Z - 1) < 1e-9, "F6/F7方位0°局部X=+管轴");
                    Check(Math.Abs(z.X) < 1e-9 && Math.Abs(z.Y + 1) < 1e-9 && Math.Abs(z.Z) < 1e-9, "F6/F7方位0°局部Z=−Y");
                }
            }
            return recipe;
        }

        private static void CheckTrunnions()
        {
            // 自带耳轴类 Init→Setup 时可能尚无 SSP_RECIPE；不得抛错弹 FATAL。
            var bare = new NativePipeSupportComponent {
                BMECObject = new ParametricSetupValues {
                    Source = new Bentley.ECObjects.Instance.IECInstance("SINGLE_PIPE_TRUNNION", "bare-trunnion") } };
            bare.Setup();
            Reject(() => bare.PrepareGraphics(), "无配方时几何阶段仍明确拒绝");

            foreach (var kind in new[] { VerticalPipeSupportKind.F6, VerticalPipeSupportKind.F7, VerticalPipeSupportKind.F10 })
            foreach (double scale in new[] { 1.0, 1000, 10000 })
            foreach (double angle in new[] { 0.0, 37, 270 })
            {
                var session = VerticalPreview(kind, scale, true, angle);
                session.Confirm(); var recipe = CheckTrunnionResult(kind.ToString(), 1);
                Check(recipe.Vertical.Kind == kind && recipe.Vertical.AzimuthDegrees == angle && session.LastConfirmedNative, "立管类型/方位/关联结果保持");
            }
            foreach (var elbow in new[] { ElbowOrientation.Vertical, ElbowOrientation.Horizontal })
            foreach (var orientation in new[] { TrunnionOrientation.Vertical, TrunnionOrientation.Horizontal })
            foreach (double scale in new[] { 1.0, 1000, 10000 })
            foreach (bool option in new[] { false, true })
            {
                var plan = ElbowPlan(elbow, orientation, scale, true, option && orientation == TrunnionOrientation.Vertical,
                    option && orientation == TrunnionOrientation.Horizontal, option && elbow == ElbowOrientation.Horizontal && orientation == TrunnionOrientation.Horizontal);
                var session = new ElbowTrunnionPreviewSession(); session.Regenerate(plan);
                Check(World.Elements.Count == 1 && World.Displays.Count == 1, "弯头预览仅暂态");
                string tag = plan.AssemblyTag;
                plan.Parameters.Material = "MUTATED";
                session.Confirm(); var recipe = CheckTrunnionResult(NativePipeSupportRecipe.TrunnionCode(plan.Parameters), option && orientation == TrunnionOrientation.Vertical ? 3 : 2);
                Check(recipe.Elbow.Parameters.Material == "C1" && recipe.Elbow.AssemblyTag == tag && recipe.Elbow.Parameters.Plate == 'A', "弯头冻结计划与char保持");
                Check(recipe.Elbow.Parameters.WallOverrideMm == 4.2 && recipe.Elbow.Parameters.NamingUnit == PipeNamingUnit.Imperial, "可空壁厚/英制编号保持");
                Check(recipe.Elbow.Parameters.Ptfe == (option && orientation == TrunnionOrientation.Vertical), "PTFE覆面选项保持");
                Check(session.LastConfirmedNative, "原生弯头确认结果");
                var frame = recipe.Elbow.Selection.Frame;
                var point = new VectorMm(recipe.CenterMm[0], recipe.CenterMm[1], recipe.CenterMm[2]);
                Check(Math.Abs((point-frame.ArcCenter).Length-150) < 1e-6, "ISO点在弯头圆弧中心线上");
            }
            foreach (bool elbow in new[] { false, true })
            foreach (string fault in new[] { "SchemaMissing", "Create", "Serialize", "Relationship", "Statistics", "Metadata", "Cache", "IsoPointWrite", "IsoPointDropped", "StateDropped", "WrongOrigin", "Parametric", "Transform", "AliasDropped", "RecipeDropped", "ReadbackRecipeDropped", "DisplayClose" })
            {
                Action confirm; Action cancel;
                if (elbow) { var s = new ElbowTrunnionPreviewSession(); s.Regenerate(ElbowPlan(ElbowOrientation.Vertical,TrunnionOrientation.Horizontal,1000)); confirm=s.Confirm; cancel=s.Cancel; }
                else { var s=VerticalPreview(); confirm=s.Confirm; cancel=s.Cancel; }
                World.Fault=fault; BMECApi.Instance.DeferCommits=true; Reject(confirm,"耳轴注入失败拒绝 "+fault);
                Check(BMECApi.Instance.DeferCommits,"耳轴失败恢复延迟提交开关");
                Check(World.Elements.Count==1 && World.Displays.Count==1,"耳轴失败无新根，预览仍可管理 "+fault);
                World.Fault=""; cancel(); Check(World.Displays.Count==0,"失败后取消清理");
            }
            foreach (string change in new[] { "position", "dn", "unit", "model", "locked", "identity", "deleted" })
            {
                var s=new ElbowTrunnionPreviewSession(); s.Regenerate(ElbowPlan(ElbowOrientation.Horizontal,TrunnionOrientation.Vertical,1000));
                switch(change) {
                    case "position": ElbowTrunnionReader.Current.Frame.Origin=new VectorMm(9000,2000,3000);break;
                    case "dn":ElbowTrunnionReader.Current.MainDn=200;break;
                    case "unit":Bentley.MstnPlatformNET.Session.Instance.Model.Scale=5;break;
                    case "model":Bentley.MstnPlatformNET.Session.Instance.Model.Handle=3;break;
                    case "locked":World.Elements[1].Locked=true;break;
                    case "identity":World.Source.ClassDefinition.Name="PIPE";break;
                    case "deleted":World.Elements.Clear();break;
                }
                Reject(s.Confirm,"预览后源弯头变化拒绝 "+change);
                Check(World.Created==null,"源弯头变化时尚未创建支架");s.Cancel();
            }
            foreach (bool elbow in new[] { false, true })
            {
                if(elbow) {var p=ElbowPlan(ElbowOrientation.Vertical,TrunnionOrientation.Vertical,1000,false);var s=new ElbowTrunnionPreviewSession();s.Regenerate(p);s.Confirm();Check(!s.LastConfirmedNative,"风管来源普通Cell");}
                else {var s=VerticalPreview(native:false);s.Confirm();Check(!s.LastConfirmedNative,"辅助线来源普通Cell");}
                Check(World.Created==null && World.Elements.Count==2 && World.Displays.Count==0,"非原生来源不建虚假关联");
            }
            var referencePlan=ElbowPlan(ElbowOrientation.Vertical,TrunnionOrientation.Vertical,1000);
            referencePlan.Selection.IsFromReference=true;
            var reference=new ElbowTrunnionPreviewSession();reference.Regenerate(referencePlan);reference.Confirm();
            Check(!reference.LastConfirmedNative && World.Created==null,"参考弯头不写源/关系");
            var changedPipe=VerticalPreview();World.Pipe.EndZ+=10;Reject(changedPipe.Confirm,"立管源变化拒绝");changedPipe.Cancel();
        }
    }
}
