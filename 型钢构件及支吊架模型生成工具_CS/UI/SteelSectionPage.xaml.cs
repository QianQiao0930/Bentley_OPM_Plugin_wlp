using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text.RegularExpressions;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using Bentley.MstnPlatformNET;
using App = Bentley.Interop.MicroStationDGN.Application;

namespace SteelSectionProbe
{
    internal sealed class DimensionDisplay
    {
        public string Name { get; set; }
        public string Value { get; set; }
    }

    internal partial class SteelSectionPage : UserControl, IWorkspacePage
    {
        private static readonly Regex RotationInput = new Regex("^[0-9.\\-]+$");
        private bool updating;
        private bool sweepModeSelected;

        internal static SteelSectionPage Current;

        internal ModeData Mode { get { return ModeCombo.SelectedItem as ModeData; } }
        internal FamilyData Family { get { return FamilyCombo.SelectedItem as FamilyData; } }
        internal ProfileData Profile { get { return ProfileCombo.SelectedItem as ProfileData; } }
        internal double Rotation
        {
            get
            {
                double value;
                return TryReadRotation(out value) ? value : 0.0;
            }
        }

        public string PageId { get { return "steel-sections"; } }
        public string PageTitle { get { return "型钢生成"; } }
        public string PageSubtitle { get { return "截面放置与路径扫掠"; } }
        public FrameworkElement View { get { return this; } }

        internal SteelSectionPage()
        {
            InitializeComponent();
            Current = this;
            updating = true;
            FamilyCombo.ItemsSource = RuntimeData.Families;
            if (FamilyCombo.Items.Count > 0) FamilyCombo.SelectedIndex = 0;
            updating = false;
            SelectFamily();
            PageLastInput.Restore(this,PageId,"FamilyCombo","ProfileCombo","ModeCombo",
                "RotationTextBox","DeletePathCheckBox");
            RefreshActionState();
        }

        private void FamilyCombo_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            if (!updating) SelectFamily();
        }

        private void ProfileCombo_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            if (!updating) SelectProfile();
        }

        private void ModeCombo_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            if (updating) return;
            ProfilePreview.Mode = Mode;
            Restart();
        }

        private void SelectFamily()
        {
            FamilyData family = Family;
            updating = true;
            try
            {
                ProfileCombo.ItemsSource = family == null ? null : family.Profiles;
                if (family == null || family.Profiles == null || family.Profiles.Length == 0) return;
                int defaultIndex = 0;
                for (int i = 0; i < family.Profiles.Length; i++)
                {
                    string name = family.Profiles[i].Name;
                    if (name == "20a" ||
                        (family.Id == "equal_angle" && name == "L50x50x5") ||
                        (family.Id == "unequal_angle" && name == "L63x40x5") ||
                        (family.Id == "hot_rolled_h" && name == "H200x200x8x12xr13") ||
                        (family.Id == "hk_section" && name.StartsWith("HK100x100", StringComparison.Ordinal)))
                    {
                        defaultIndex = i;
                        break;
                    }
                }
                ProfileCombo.SelectedIndex = defaultIndex;
            }
            finally { updating = false; }
            SelectProfile();
        }

        private void SelectProfile()
        {
            ProfileData profile = Profile;
            updating = true;
            try
            {
                ModeCombo.ItemsSource = profile == null ? null : profile.Modes;
                if (profile != null && profile.Modes != null && profile.Modes.Length > 0)
                    ModeCombo.SelectedIndex = 0;
            }
            finally { updating = false; }

            if (profile == null)
            {
                ProfileSummaryText.Text = string.Empty;
                DimensionItems.ItemsSource = null;
                ProfilePreview.Mode = null;
                return;
            }

            ProfileSummaryText.Text = Family.Label + "  /  " + profile.Name;
            // 只显示 SteelSectionCatalog 登记过的字段（中文名 + 单位），界面不出现英文键。
            var rows = new List<DimensionDisplay>();
            SectionField[] fields = SteelSectionCatalog.FieldsFor(Family == null ? null : Family.Id);
            foreach (SectionField field in fields)
            {
                double value;
                if (!profile.Dimensions.TryGetValue(field.Key, out value)) continue;
                rows.Add(new DimensionDisplay
                {
                    Name = field.Label,
                    Value = value.ToString("G", CultureInfo.InvariantCulture) + " " + field.Unit
                });
            }
            DimensionItems.ItemsSource = rows;
            ProfilePreview.Mode = Mode;
            Restart();
        }

        private void RotationTextBox_PreviewTextInput(object sender, TextCompositionEventArgs e)
        {
            e.Handled = !RotationInput.IsMatch(e.Text);
        }

        private void RotationTextBox_TextChanged(object sender, TextChangedEventArgs e)
        {
            if (updating) return;
            double value;
            if (TryReadRotation(out value)) Restart();
        }

        private void RotationTextBox_LostFocus(object sender, RoutedEventArgs e)
        {
            double value;
            if (!TryReadRotation(out value)) value = 0.0;
            value = Math.Max(-360.0, Math.Min(360.0, value));
            updating = true;
            RotationTextBox.Text = value.ToString("0.0", CultureInfo.InvariantCulture);
            updating = false;
            Restart();
        }

        private bool TryReadRotation(out double value)
        {
            return double.TryParse(RotationTextBox.Text, NumberStyles.Float,
                       CultureInfo.InvariantCulture, out value) ||
                   double.TryParse(RotationTextBox.Text, NumberStyles.Float,
                       CultureInfo.CurrentCulture, out value);
        }

        private void Restart()
        {
            if (Profile == null || Mode == null) return;
            ProfilePreview.Mode = Mode;
            if (Placement.IsActive)
                Place();
            else if (SweepPlacement.HasPreview)
            {
                try { SweepPlacement.Regenerate(); }
                catch (Exception ex) { SetStatus("重建预览失败：" + ex.Message, true); }
            }
        }

        internal void Place()
        {
            App app = Bentley.MstnPlatformNET.InteropServices.Utilities.ComApp;
            if (app == null || !app.HasActiveModelReference)
            {
                SetStatus("请先打开 DGN 模型。", true);
                return;
            }
            if (Family == null || Profile == null || Mode == null) return;
            try
            {
                SweepPlacement.Cancel();
                Placement.Begin(app, Family, Profile, Mode);
                sweepModeSelected = false;
                SetStatus("正在放置 " + Profile.Name + "：移动鼠标查看预览，单击放置，右键重置结束。", false);
                RefreshActionState();
            }
            catch (Exception ex) { SetStatus(ex.Message, true); }
        }

        private void SelectSweepPath()
        {
            App app = Bentley.MstnPlatformNET.InteropServices.Utilities.ComApp;
            if (app == null || !app.HasActiveModelReference)
            {
                SetStatus("请先打开 DGN 模型。", true);
                return;
            }
            try
            {
                SweepPlacement.SelectPath(app);
                sweepModeSelected = true;
                SetStatus("请在模型中左键确认一条开放路径；悬停高亮仅表示路径合法。", false);
                RefreshActionState();
            }
            catch (Exception ex) { SetStatus(ex.Message, true); }
        }

        private void ConfirmSweep()
        {
            if (!SweepPlacement.HasPreview)
            {
                SetStatus("尚无可确认的扫掠预览。", true);
                return;
            }
            try
            {
                SweepPlacement.Confirm(DeletePathCheckBox.IsChecked == true);
                SetStatus("扫掠实体已保留并写入统计信息。", false);
                RefreshActionState();
            }
            catch (Exception ex) { SetStatus(ex.Message, true); }
        }

        private void CancelSweep()
        {
            SweepPlacement.Cancel();
            SetStatus("已取消扫掠预览。", false);
            RefreshActionState();
        }

        internal void NotifyPreviewState()
        {
            if (!Dispatcher.CheckAccess())
            {
                Dispatcher.BeginInvoke(new Action(RefreshActionState));
                return;
            }
            RefreshActionState();
        }

        private void RefreshActionState()
        {
            bool hasPreview = SweepPlacement.HasPreview;
            ConfirmButton.IsEnabled = hasPreview;
            CancelButton.IsEnabled = hasPreview;
            PlaceButton.Style = (Style)FindResource(sweepModeSelected ? "SecondaryButtonStyle" : "PrimaryButtonStyle");
            SweepButton.Style = (Style)FindResource(sweepModeSelected ? "PrimaryButtonStyle" : "SecondaryButtonStyle");
        }

        internal void SetStatus(string message, bool isError)
        {
            if (MainWindow.Current != null) MainWindow.Current.SetStatus(message, isError);
        }

        public void OnActivated()
        {
            SetStatus("选择规格与插入基准，然后放置截面或选取扫掠路径。", false);
        }

        public void OnDeactivated()
        {
            PageLastInput.Save(this,PageId,"FamilyCombo","ProfileCombo","ModeCombo",
                "RotationTextBox","DeletePathCheckBox");
            Placement.End();
            SweepPlacement.Cancel();
        }

        public void OnWorkspaceClosing()
        {
            PageLastInput.Save(this,PageId,"FamilyCombo","ProfileCombo","ModeCombo",
                "RotationTextBox","DeletePathCheckBox");
            Placement.End();
            SweepPlacement.Cancel();
            if (ReferenceEquals(Current, this)) Current = null;
        }

        private void PlaceButton_Click(object sender, RoutedEventArgs e) { Place(); }
        private void SweepButton_Click(object sender, RoutedEventArgs e) { SelectSweepPath(); }
        private void ConfirmButton_Click(object sender, RoutedEventArgs e) { ConfirmSweep(); }
        private void CancelButton_Click(object sender, RoutedEventArgs e) { CancelSweep(); }
    }
}
