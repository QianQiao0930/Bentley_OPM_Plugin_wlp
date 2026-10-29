namespace SteelSectionProbe {
 internal sealed class SteelSectionPage : TestPage { internal SteelSectionPage() : base("steel-sections") { } }
 internal sealed class ActivationPage : TestPage { internal ActivationPage() : base("activation") { } internal void RefreshStatus() { } }
 internal sealed class AboutPage : TestPage { internal AboutPage() : base("about") { } }
 internal sealed class HandrailPage : TestPage { internal HandrailPage() : base("steel-handrail") { } }
 internal sealed class SpiralStairPage : TestPage { internal SpiralStairPage() : base("tank-spiral-stair") { } }
 internal sealed class TankLadderPage : TestPage { internal TankLadderPage() : base("tank-ladder") { } }
 internal sealed class WallLadderPage : TestPage { internal WallLadderPage() : base("wall-ladder") { } }
 internal sealed class MagneticGaugePage : TestPage { internal MagneticGaugePage() : base("magnetic-level-gauge") { } }
 internal sealed class EquipmentLevelPage : TestPage, IWorkspaceBusyPage { internal EquipmentLevelPage() : base("equipment-level") { } public bool IsBusy { get; set; } }
 internal sealed class PipeAlignmentPage : TestPage { internal PipeAlignmentPage() : base("pipe-alignment") { } }
 internal sealed class ComponentPropertiesPage : TestPage { internal ComponentPropertiesPage() : base("component-properties") { } }
 internal sealed class LineCoordinatesPage : TestPage { internal LineCoordinatesPage() : base("line-coordinates") { } }
 internal sealed class SupportBindingPage : TestPage { internal SupportBindingPage() : base("support-binding") { } }
 internal sealed class ElbowTrunnionPage : TestPage { internal ElbowTrunnionPage() : base("elbow-trunnion") { } }
 internal sealed class SupportStatisticsPage : TestPage { internal SupportStatisticsPage() : base("support-statistics") { } }
 internal sealed class TankManholePage : TestPage { internal TankManholePage() : base("tank-manhole") { } }
 internal sealed class SquareManholePage : TestPage { internal SquareManholePage() : base("square-manhole") { } }
 internal sealed class NozzlePage : TestPage { internal NozzlePage() : base("solid-nozzle") { } }
 internal sealed class FireCabinetPage : TestPage { internal FireCabinetPage() : base("fire-cabinet") { } }
 internal sealed class HoseCabinetPage : TestPage { internal HoseCabinetPage() : base("hose-cabinet") { } }
 internal sealed class PipeClampPage : TestPage { internal PipeClampPage() : base("pipe-clamp") { } }
 internal sealed class Q1SupportPage : TestPage { internal Q1SupportPage() : base("q1-small-pipe-support") { } }
 internal sealed class G2AnchorPage : TestPage { internal G2AnchorPage() : base("g2-anchor-plate") { } }
 internal sealed class VerticalPipeSupportPage : TestPage { internal VerticalPipeSupportPage() : base("vertical-pipe-support") { } }
 internal sealed class ColdRiserGuidePage : TestPage { internal ColdRiserGuidePage() : base("cold-riser-guide") { } }
 internal sealed class N1CantileverPage : TestPage { internal N1CantileverPage() : base("n1-cantilever") { } }
 internal sealed class N2CantileverPage : TestPage { internal N2CantileverPage() : base("n2-cantilever") { } }
 internal sealed class N3Page : TestPage { internal N3Page() : base("n3-single-bracket") { } }
 internal sealed class N4Page : TestPage { internal N4Page() : base("n4-double-bracket") { } }
 internal sealed class D2CantileverPage : TestPage { internal D2CantileverPage() : base("d2-cantilever") { } }
 internal sealed class TriangleBracketPage : TestPage { internal TriangleBracketPage() : base("triangle-bracket") { } }
 internal sealed class LBracketPage : TestPage { internal LBracketPage() : base("l-bracket") { } }
 internal sealed class PortalFramePage : TestPage { internal PortalFramePage() : base("portal-frame") { } }
 internal sealed class TFramePage : TestPage { internal TFramePage() : base("t-frame") { } }
 internal sealed class PadPlatePage : TestPage { internal PadPlatePage() : base("pad-plate") { } }
 internal sealed class N8Page : TestPage { internal N8Page() : base("n8-connection-plate") { } }
}
