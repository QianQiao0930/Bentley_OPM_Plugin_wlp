namespace SteelSectionProbe
{
    /// <summary>
    /// 首页功能清单（唯一来源）。改造前这些卡片是手写在 <c>UI/HomePage.xaml</c> 里的，
    /// 现在改成数据驱动：首页只负责渲染，新增功能时在这里加一项即可。
    /// <para>
    /// ⚠️ <c>PageId</c> 必须与各功能页 <see cref="IWorkspacePage.PageId"/> 逐字一致 ——
    /// 不一致时 <c>WorkspaceView.OpenPage</c> 找不到页面（已在那一侧改为写状态栏报错，
    /// 并由 <c>Development/HomeCheck</c> 断言本清单本身的一致性）。
    /// </para>
    /// </summary>
    internal static class HomeFeatureCatalog
    {
        /// <summary>
        /// 出厂顺序 = 改造前 HomePage.xaml 的卡片顺序（每项 10 递增，留出插入余量）。
        /// 分区口径（2026-09-28 用户确认）：「HGT21629 支吊架」收纳全部支吊架类功能
        /// （耳轴、管夹、锚板、三角架、连接板——对应 HG/T 21629 标准图集各系列）；
        /// 建模类只留通用建模（型钢、人孔、管口）。
        /// </summary>
        internal static FeatureDescriptor[] All()
        {
            return new FeatureDescriptor[]
            {
                new FeatureDescriptor("steel-sections", "型钢生成",
                    "二维截面或沿路径生成三维型钢。", 10, HomeCategories.Modeling, "steel"),
                new FeatureDescriptor("steel-handrail", "普通钢结构围栏",
                    "沿水平或坡段路径生成立柱、扶手和踢脚板。", 15, HomeCategories.Modeling, "handrail"),
                new FeatureDescriptor("component-properties", "构件特性查询",
                    "点取构件，查看 EC 属性与几何特性。", 20, HomeCategories.Stats, "inspect"),
                new FeatureDescriptor("elbow-trunnion", "弯头耳轴",
                    "竖直或水平弯头，搭配竖直或水平耳轴。", 30, HomeCategories.Support, "elbow"),
                new FeatureDescriptor("support-statistics", "支吊架统计",
                    "汇总当前 DGN 支吊架，导出 Excel 或 JSON。", 40, HomeCategories.Stats, "chart"),
                new FeatureDescriptor("tank-manhole", "罐壁人孔",
                    "DN450～DN600，吊杆或铰链开盖。", 50, HomeCategories.Modeling, "manhole"),
                new FeatureDescriptor("solid-nozzle", "实体管口",
                    "CL150 法兰与钢管，可选螺栓孔。", 60, HomeCategories.Modeling, "nozzle"),
                new FeatureDescriptor("pipe-clamp", "放置管夹",
                    "A1、A2、A22、A24、E1、K1、T4、L2 管夹与管托。", 70, HomeCategories.Support, "clamp"),
                new FeatureDescriptor("vertical-pipe-support", "立管耳轴",
                    "F6、F7、F10；点取立管或竖直辅助线。", 80, HomeCategories.Support, "riser"),
                new FeatureDescriptor("cold-riser-guide", "保冷立管导向架",
                    "L7 / L8 类型 1/2：点取立管并旋转安装方向。", 85, HomeCategories.Support, "riser"),
                new FeatureDescriptor("g2-anchor-plate", "混凝土锚板",
                    "G2 锚板与 4 根膨胀锚栓。", 90, HomeCategories.Support, "anchor"),
                new FeatureDescriptor("n3-single-bracket", "N3 单三角架",
                    "设备表面至横担末端辅助线定位。", 100, HomeCategories.Support, "triangle"),
                new FeatureDescriptor("n4-double-bracket", "N4 双三角架",
                    "设备中心至立管中心辅助线定位。", 110, HomeCategories.Support, "triangle"),
                new FeatureDescriptor("triangle-bracket", "三角架",
                    "D5_D6_G12_D19：端焊、侧焊、锚固、双槽钢。", 115, HomeCategories.Support, "triangle"),
                new FeatureDescriptor("l-bracket", "L 型架",
                    "D7：L 形与倒 L 形管架。", 116, HomeCategories.Support, "triangle"),
                new FeatureDescriptor("portal-frame", "门型架",
                    "D8_D13_G5_G6_D16_D20：竖直与水平门型架。", 117, HomeCategories.Support, "triangle"),
                new FeatureDescriptor("t-frame", "T 型架",
                    "D12_G4_D15：正 T、倒 T 与水平 T。", 118, HomeCategories.Support, "triangle"),
                new FeatureDescriptor("pad-plate", "垫板",
                    "Y2 弧形垫板与弯头垫板。", 119, HomeCategories.Support, "clamp"),
                new FeatureDescriptor("n8-connection-plate", "N8 连接板",
                    "选板型与安装面，点取设备表面。", 120, HomeCategories.Support, "link"),
                FeatureDescriptor.Placeholder("自定义构件",
                    "连接板、组合构件和企业标准件的扩展入口，持续开发中。", 1, HomeCategories.Planned, "puzzle"),
            };
        }
    }
}
