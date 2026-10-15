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
        // 界面只显示 2 位小数；未编辑字段在应用时沿用这里的精确值，避免整段坐标被舍入。
        private readonly double[] exactField = new double[6];
        private readonly string[] shownField = new string[6];
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
            LineCoordinatePipeTool.Picked += OnPipePicked;
            LineCoordinatePipeTool.Ended += OnEnded;
            TransactionManager.OnUndoRedoFinished += UndoFinished;
            ClearSelection();
        }
        public void OnDeactivated()
        {
            if (!active) return;
            active = false; revision++;
            LineCoordinateLocateTool.Picked -= OnPicked;
            LineCoordinateLocateTool.Ended -= OnEnded;
            LineCoordinatePipeTool.Picked -= OnPipePicked;
            LineCoordinatePipeTool.Ended -= OnEnded;
            TransactionManager.OnUndoRedoFinished -= UndoFinished;
            LineCoordinateLocateTool.End();
            LineCoordinatePipeTool.End();
            ClearSelection();
        }
        public void OnWorkspaceClosing() { OnDeactivated(); }

        private void Pick_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                if (!active) return;
                if (Session.Instance.GetActiveDgnModel() == null) throw new InvalidOperationException("请先打开 DGN 模型。");
                if (LineCoordinatePipeTool.IsActive) LineCoordinatePipeTool.End();
                if (!LineCoordinateLocateTool.IsActive) { revision++; ClearSelection(); }
                LineCoordinateLocateTool.Begin(); StopButton.IsEnabled = true;
                SetStatus("请选择活动模型中的一条独立直线段。", false);
            }
            catch (Exception ex) { SetStatus("无法开始点取：" + ex.Message, true); }
        }
        private void Stop_Click(object sender, RoutedEventArgs e)
        {
            revision++; LineCoordinateLocateTool.End(); LineCoordinatePipeTool.End(); StopButton.IsEnabled = false;
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
                try { Display(LineCoordinateReader.Read(located)); SetStatus("已读取两端坐标，编辑后点击“应用修改”。也可以用“快速对齐”按钮填充坐标。", false); }
                catch (Exception ex) { ClearSelection(); SetStatus("读取直线失败：" + ex.Message, true); }
            }));
        }

        private void OnPipePicked(LocatedElement located)
        {
            if (!active || located == null || selection == null) return;
            int request = ++revision;
            // 保留已点取的直线草稿；只按当前填写值推演目标坐标并重新填写。
            Dispatcher.BeginInvoke(new Action(delegate
            {
                if (!active || request != revision) return;
                try
                {
                    var draft = ReadInput();
                    var pipe = LineCoordinatePipeReader.Read(located);
                    string summary;
                    var target = LinePipeAlign.ToPipe(draft, pipe, selection.Is3d, out summary);
                    FillDraft(target);
                    SetStatus(summary + (string.IsNullOrEmpty(pipe.PipeNumber) ? "" : "（管道 " + pipe.PipeNumber + "）"), false);
                }
                catch (Exception ex) { SetStatus("对齐到管道失败：" + ex.Message, true); }
            }));
        }

        private void AlignVerticalStart_Click(object sender, RoutedEventArgs e) { OrthoAlign(true, true); }
        private void AlignVerticalEnd_Click(object sender, RoutedEventArgs e) { OrthoAlign(false, true); }
        private void AlignHorizontalStart_Click(object sender, RoutedEventArgs e) { OrthoAlign(true, false); }
        private void AlignHorizontalEnd_Click(object sender, RoutedEventArgs e) { OrthoAlign(false, false); }

        private void OrthoAlign(bool anchorStart, bool vertical)
        {
            if (!active || selection == null) { SetStatus("请先点取直线，再使用快速对齐。", true); return; }
            try
            {
                string summary;
                if (vertical)
                {
                    var aligned = LinePipeAlign.AlignVertical(ReadInput(), anchorStart);
                    FillDraft(aligned);
                    summary = anchorStart ? "已按起点对齐竖直线：终点 X/Y 与起点一致，终点 Z 保持。"
                        : "已按终点对齐竖直线：起点 X/Y 与终点一致，起点 Z 保持。";
                }
                else
                {
                    var aligned = LinePipeAlign.AlignHorizontal(ReadInput(), anchorStart);
                    FillDraft(aligned);
                    summary = anchorStart ? "已按起点对齐水平线：终点 Z 与起点一致，X/Y 保持。"
                        : "已按终点对齐水平线：起点 Z 与终点一致，X/Y 保持。";
                }
                SetStatus(summary, false);
            }
            catch (Exception ex) { SetStatus("对齐失败：" + ex.Message, true); }
        }

        private void AlignPipe_Click(object sender, RoutedEventArgs e)
        {
            if (!active || selection == null) { SetStatus("请先点取直线，再对齐到管道。", true); return; }
            try
            {
                if (Session.Instance.GetActiveDgnModel() == null) throw new InvalidOperationException("请先打开 DGN 模型。");
                if (LineCoordinateLocateTool.IsActive) LineCoordinateLocateTool.End();
                LineCoordinatePipeTool.Begin(); StopButton.IsEnabled = true;
                SetStatus("请选择一根活动模型中的 OpenPlant 管道；水平线将贴管底标高，竖直线将移到点取位置下方。", false);
            }
            catch (Exception ex) { SetStatus("无法开始点取管道：" + ex.Message, true); }
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
                FillFields(value.Coordinates);
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
                for (int i = 0; i < shownField.Length; i++) { exactField[i] = 0; shownField[i] = null; }
                ReloadButton.IsEnabled = ApplyButton.IsEnabled = StopButton.IsEnabled = false;
                LengthText.Text = "线段长度：—";
                EditStateText.Text = "点取后可编辑；点击应用修改才会写入原线段。";
            }
            finally { loading = false; }
        }
        // 快速对齐/管道对齐推演出的目标坐标：只重新填充六个草稿框，不触碰模型。
        private void FillDraft(LineCoordinates coordinates)
        {
            loading = true;
            try
            {
                FillFields(coordinates);
            }
            finally { loading = false; }
            RefreshInput();
        }
        // 显示 2 位小数；字段文本与显示值一致视为未改动，沿用精确值，避免只改一项时舍入其余五项。
        private void FillFields(LineCoordinates coordinates)
        {
            SetField(0, StartXText, coordinates.Start.X);
            SetField(1, StartYText, coordinates.Start.Y);
            SetField(2, StartZText, coordinates.Start.Z);
            SetField(3, EndXText, coordinates.End.X);
            SetField(4, EndYText, coordinates.End.Y);
            SetField(5, EndZText, coordinates.End.Z);
        }
        private void SetField(int index, TextBox box, double value)
        {
            exactField[index] = value;
            shownField[index] = LineCoordinateCalculator.Display(value);
            box.Text = shownField[index];
        }
        private double FieldValue(int index, TextBox box, string label)
        {
            return box.Text == shownField[index] ? exactField[index] : LineCoordinateCalculator.Parse(box.Text, label);
        }
        private LineCoordinates ReadInput()
        {
            return new LineCoordinates(
                new LineCoordinatePoint(FieldValue(0, StartXText, "起点 X"), FieldValue(1, StartYText, "起点 Y"), FieldValue(2, StartZText, "起点 Z")),
                new LineCoordinatePoint(FieldValue(3, EndXText, "终点 X"), FieldValue(4, EndYText, "终点 Y"), FieldValue(5, EndZText, "终点 Z")));
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
