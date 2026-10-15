using System;
using System.Globalization;
using System.Windows;
using System.Windows.Controls;
using Bentley.DgnPlatformNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal partial class LineCoordinatesPage : UserControl, IWorkspacePage
    {
        private LineCoordinateSelection selection;
        private bool active, loading;
        private int revision;
        public string PageId { get { return "line-coordinates"; } }
        public string PageTitle { get { return "直线坐标修改"; } }
        public string PageSubtitle { get { return "点取直线并修改两端 XYZ 坐标"; } }
        public FrameworkElement View { get { return this; } }

        internal LineCoordinatesPage() { InitializeComponent(); }

        public void OnActivated()
        {
            if (active) return;
            active = true; revision++;
            LineCoordinateLocateTool.Picked += OnPicked;
            LineCoordinateLocateTool.Ended += OnEnded;
            TransactionManager.OnUndoRedoFinished += UndoFinished;
            ClearSelection();
        }
        public void OnDeactivated()
        {
            if (!active) return;
            active = false; revision++;
            LineCoordinateLocateTool.Picked -= OnPicked;
            LineCoordinateLocateTool.Ended -= OnEnded;
            TransactionManager.OnUndoRedoFinished -= UndoFinished;
            LineCoordinateLocateTool.End();
            ClearSelection();
        }
        public void OnWorkspaceClosing() { OnDeactivated(); }

        private void Pick_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                if (!active) return;
                if (Session.Instance.GetActiveDgnModel() == null) throw new InvalidOperationException("请先打开 DGN 模型。");
                if (!LineCoordinateLocateTool.IsActive) { revision++; ClearSelection(); }
                LineCoordinateLocateTool.Begin(); StopButton.IsEnabled = true;
                SetStatus("请选择活动模型中的一条独立直线段。", false);
            }
            catch (Exception ex) { SetStatus("无法开始点取：" + ex.Message, true); }
        }
        private void Stop_Click(object sender, RoutedEventArgs e)
        {
            revision++; LineCoordinateLocateTool.End(); StopButton.IsEnabled = false;
            SetStatus("已结束点取。", false);
        }
        private void OnEnded() { revision++; StopButton.IsEnabled = false; }

        private void OnPicked(LocatedElement located)
        {
            if (!active || located == null) return;
            int request = ++revision;
            ClearSelection();
            Dispatcher.BeginInvoke(new Action(delegate
            {
                if (!active || request != revision) return;
                try { Display(LineCoordinateReader.Read(located)); SetStatus("已读取两端坐标，编辑后点击“应用修改”。", false); }
                catch (Exception ex) { ClearSelection(); SetStatus("读取直线失败：" + ex.Message, true); }
            }));
        }
        private void Reload_Click(object sender, RoutedEventArgs e)
        {
            if (!active || selection == null) return;
            revision++;
            try
            {
                Display(LineCoordinateReader.Read(new LocatedElement { ModelRef = selection.Model, ElementId = selection.ElementId }));
                SetStatus("已重新读取原线段，未应用的输入已恢复。", false);
            }
            catch (Exception ex) { ClearSelection(); SetStatus("重新读取失败：" + ex.Message, true); }
        }
        private void Apply_Click(object sender, RoutedEventArgs e)
        {
            if (!active || selection == null) return;
            try
            {
                var target = ReadInput();
                LineCoordinateCalculator.Validate(target, selection.Is3d, 1.0 / selection.UorPerMm);
                string elapsed;
                var updated = WriteDuration.Measure(() => LineCoordinateEditor.Apply(selection, target), out elapsed);
                Display(updated);
                SetStatus("直线坐标已修改，写入耗时 " + elapsed + "；可使用 OPM 撤销/重做。", false);
            }
            catch (Exception ex) { SetStatus("修改失败：" + ex.Message, true); }
        }
        private void UndoFinished(object sender, OnUndoRedoFinishedEventArgs e)
        {
            if (!active) return;
            revision++; ClearSelection();
            SetStatus("模型已撤销或重做，请重新点取直线以读取当前坐标。", false);
        }

        private void Display(LineCoordinateSelection value)
        {
            loading = true;
            try
            {
                selection = value;
                SelectionText.Text = "元素 " + value.ElementId.ToString(CultureInfo.InvariantCulture) + " · " + (value.Is3d ? "三维直线" : "二维直线（Z=0）");
                StartFields.IsEnabled = EndFields.IsEnabled = true;
                StartZText.IsReadOnly = EndZText.IsReadOnly = !value.Is3d;
                StartXText.Text = LineCoordinateCalculator.Format(value.Coordinates.Start.X);
                StartYText.Text = LineCoordinateCalculator.Format(value.Coordinates.Start.Y);
                StartZText.Text = LineCoordinateCalculator.Format(value.Coordinates.Start.Z);
                EndXText.Text = LineCoordinateCalculator.Format(value.Coordinates.End.X);
                EndYText.Text = LineCoordinateCalculator.Format(value.Coordinates.End.Y);
                EndZText.Text = LineCoordinateCalculator.Format(value.Coordinates.End.Z);
                ReloadButton.IsEnabled = true;
            }
            finally { loading = false; }
            RefreshInput();
        }
        private void ClearSelection()
        {
            selection = null; loading = true;
            try
            {
                SelectionText.Text = "尚未点取直线";
                StartFields.IsEnabled = EndFields.IsEnabled = false;
                StartXText.Text = StartYText.Text = StartZText.Text = EndXText.Text = EndYText.Text = EndZText.Text = "";
                ReloadButton.IsEnabled = ApplyButton.IsEnabled = StopButton.IsEnabled = false;
                LengthText.Text = "线段长度：—";
                EditStateText.Text = "点取后可编辑；点击应用修改才会写入原线段。";
            }
            finally { loading = false; }
        }
        private LineCoordinates ReadInput()
        {
            return new LineCoordinates(new LineCoordinatePoint(
                LineCoordinateCalculator.Parse(StartXText.Text, "起点 X"), LineCoordinateCalculator.Parse(StartYText.Text, "起点 Y"), LineCoordinateCalculator.Parse(StartZText.Text, "起点 Z")),
                new LineCoordinatePoint(LineCoordinateCalculator.Parse(EndXText.Text, "终点 X"), LineCoordinateCalculator.Parse(EndYText.Text, "终点 Y"), LineCoordinateCalculator.Parse(EndZText.Text, "终点 Z")));
        }
        private void Coordinate_Changed(object sender, TextChangedEventArgs e) { if (!loading && ApplyButton != null) RefreshInput(); }
        private void RefreshInput()
        {
            ApplyButton.IsEnabled = false;
            if (selection == null) return;
            try
            {
                var input = ReadInput();
                LineCoordinateCalculator.Validate(input, selection.Is3d, 1.0 / selection.UorPerMm);
                LengthText.Text = "线段长度：" + LineCoordinateCalculator.Length(input).ToString("0.###", CultureInfo.CurrentCulture) + " mm";
                bool changed = !LineCoordinateCalculator.Same(input, selection.Coordinates, 0);
                ApplyButton.IsEnabled = active && changed;
                EditStateText.Text = changed ? "坐标已编辑，尚未应用到原线段。" : "当前坐标与原线段一致。";
            }
            catch (Exception ex) { LengthText.Text = "线段长度：—"; EditStateText.Text = ex.Message; }
        }
        private static void SetStatus(string text, bool error) { if (MainWindow.Current != null) MainWindow.Current.SetStatus(text, error); }
    }
}
