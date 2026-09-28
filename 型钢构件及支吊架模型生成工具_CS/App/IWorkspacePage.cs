using System.Windows;

namespace SteelSectionProbe
{
    /// <summary>
    /// Contract for feature pages hosted by the add-in workspace.  Future pipe
    /// support modules can provide another implementation without changing the
    /// window shell or the steel-section feature.
    /// </summary>
    internal interface IWorkspacePage
    {
        string PageId { get; }
        string PageTitle { get; }
        string PageSubtitle { get; }
        FrameworkElement View { get; }
        void OnActivated();
        void OnDeactivated();
        void OnWorkspaceClosing();
    }
}
