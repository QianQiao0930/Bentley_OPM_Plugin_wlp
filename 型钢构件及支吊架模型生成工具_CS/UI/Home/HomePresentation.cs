namespace SteelSectionProbe
{
    /// <summary>首页纯展示编号，不参与业务编号、选型、统计或模块注册。</summary>
    internal static class HomePresentation
    {
        internal static string Code(string id)
        {
            switch(id)
            {
                case "steel-sections":return "STL";case "steel-handrail":return "RAIL";
                case "tank-spiral-stair":return "STAIR";case "component-properties":return "EC";
                case "tank-ladder":return "TL";case "wall-ladder":return "WL";
                case "magnetic-level-gauge":return "MLG";
                case "pipe-alignment":return "ALIGN";case "elbow-trunnion":return "F2/F4/F5";
                case "support-statistics":return "MTO";case "tank-manhole":return "MH";
                case "solid-nozzle":return "NZ";case "square-manhole":return "SMH";
                case "fire-cabinet":return "FIRE";case "hose-cabinet":return "P380";
                case "pipe-clamp":return "A1…L2";case "q1-small-pipe-support":return "Q1/Q2";
                case "vertical-pipe-support":return "F6/F7/F10";case "cold-riser-guide":return "L7/L8";
                case "g2-anchor-plate":return "G2";case "n1-cantilever":return "N1";
                case "n2-cantilever":return "N2";case "n3-single-bracket":return "N3";
                case "n4-double-bracket":return "N4";case "d2-cantilever":return "D2/D3/G11";
                case "triangle-bracket":return "D5/D6/G12/D19";case "l-bracket":return "D7";
                case "portal-frame":return "D15/D16/D20";case "t-frame":return "D4/D8/D17";
                case "pad-plate":return "Y2";case "n8-connection-plate":return "N8";
                default:return "NEXT";
            }
        }
    }
}
