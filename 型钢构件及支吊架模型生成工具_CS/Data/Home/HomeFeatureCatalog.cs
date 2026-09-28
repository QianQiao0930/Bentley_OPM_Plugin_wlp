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
        /// <summary>出厂顺序 = 改造前 HomePage.xaml 的卡片顺序（每项 10 递增，留出插入余量）。</summary>
        internal static FeatureDescriptor[] All()
        {
            return new FeatureDescriptor[]
            {
                new FeatureDescriptor("steel-sections", "型钢生成",
                    "二维截面或沿路径生成三维型钢。", 10),
                new FeatureDescriptor("component-properties", "构件特性查询",
                    "点取构件，查看 EC 属性与几何特性。", 20),
                new FeatureDescriptor("elbow-trunnion", "弯头耳轴",
                    "竖直或水平弯头，搭配竖直或水平耳轴。", 30),
                new FeatureDescriptor("support-statistics", "支吊架统计",
                    "汇总当前 DGN 支吊架，导出 Excel 或 JSON。", 40),
                new FeatureDescriptor("tank-manhole", "罐壁人孔",
                    "DN450～DN600，吊杆或铰链开盖。", 50),
                new FeatureDescriptor("solid-nozzle", "实体管口",
                    "CL150 法兰与钢管，可选螺栓孔。", 60),
                new FeatureDescriptor("pipe-clamp", "放置管夹",
                    "A2、E1、K1、T4 管夹与管托。", 70),
                new FeatureDescriptor("vertical-pipe-support", "立管耳轴",
                    "F6、F7、F10；点取立管或竖直辅助线。", 80),
                new FeatureDescriptor("g2-anchor-plate", "混凝土锚板",
                    "G2 锚板与 4 根膨胀锚栓。", 90),
                new FeatureDescriptor("n3-single-bracket", "N3 单三角架",
                    "设备表面至横担末端辅助线定位。", 100),
                new FeatureDescriptor("n4-double-bracket", "N4 双三角架",
                    "设备中心至立管中心辅助线定位。", 110),
                new FeatureDescriptor("n8-connection-plate", "N8 连接板",
                    "选板型与安装面，点取设备表面。", 120),
                FeatureDescriptor.Placeholder("管道支吊架",
                    "标准支吊架选型、参数配置与组合模型生成。", 0),
                FeatureDescriptor.Placeholder("自定义构件",
                    "连接板、组合构件和企业标准件的扩展入口。", 1),
            };
        }
    }
}
