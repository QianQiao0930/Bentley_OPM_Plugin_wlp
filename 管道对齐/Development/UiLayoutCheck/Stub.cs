using System;using System.Drawing;using System.Windows.Forms;namespace PipeAlign { internal sealed partial class PipeAlignDialog:Form {        // ---- 控件 ----
        private Label _referenceLabel;
        private Button _pickReferenceButton;
        private RadioButton _bottomRadio;
        private RadioButton _centerRadio;
        private RadioButton _topRadio;
        private RadioButton _surfacePipeRadio;
        private RadioButton _surfaceInsulationRadio;
        private RadioButton _scopeSingleRadio;
        private RadioButton _scopeGroupRadio;
        private RadioButton _scopeZRadio;
        private NumericUpDown _zDeltaInput;
        private NumericUpDown _toleranceInput;
        private Button _pickTargetsButton;
        private Button _selectionSetButton;
        private Button _removeTargetButton;
        private Button _clearTargetsButton;
        private Label _targetCountLabel;
        private CheckBox _showCurrentCheck;
        private CheckBox _showTargetCheck;
        private Button _refreshPreviewButton;
        private Button _clearPreviewButton;
        private ListView _planList;
        private Label _summaryLabel;
        private Label _readoutLabel;
        private Button _applyButton;
        private Button _resetButton;
        private Button _saveOptionsButton;
        private Button _closeButton;
        private Label _statusLabel;

private void PickReference_Click(object sender,EventArgs e){}private void PickTargets_Click(object sender,EventArgs e){}private void SelectionSet_Click(object sender,EventArgs e){}private void RemoveTarget_Click(object sender,EventArgs e){}private void ClearTargets_Click(object sender,EventArgs e){}private void RefreshPreview_Click(object sender,EventArgs e){}private void ClearPreview_Click(object sender,EventArgs e){}private void Apply_Click(object sender,EventArgs e){}private void Reset_Click(object sender,EventArgs e){}private void SaveOptions_Click(object sender,EventArgs e){}private void Close_Click(object sender,EventArgs e){}private void Mode_Changed(object sender,EventArgs e){}private void Surface_Changed(object sender,EventArgs e){}private void Scope_Changed(object sender,EventArgs e){}private void Tolerance_Changed(object sender,EventArgs e){}private void PreviewOption_Changed(object sender,EventArgs e){}private Control BuildPlanList(){_planList=new ListView();return _planList;} [STAThread] static void Main(){Application.EnableVisualStyles();using(var f=new PipeAlignDialog()){f.BuildUi();f._referenceLabel.Text="4002-MP-FLW-0020-A1B-150-NI\nPIPE · 外径168.3 mm · 保温0.0 mm";f._scopeZRadio.Checked=true;f._bottomRadio.Checked=true;f._surfacePipeRadio.Checked=true;f._summaryLabel.Text="基准标高 984.63 mm · 将移动 1，已对齐 1，跳过 1";f._readoutLabel.Text="基准中心 1068.78 mm\n管底 / 管道外表面\n水平容差 1 mm · 连接校验严格";for(int i=0;i<6;i++){var row=new ListViewItem("4002-MP-FLW-0020-A1B-150-NI");row.SubItems.AddRange(new[]{"PIPE","114.3","984.63","1068.78","+84.15","两端连接 LONG_RADIUS_ELBOW","将移动"});f._planList.Items.Add(row);}f.RefreshCards();f.Show();Application.DoEvents();f.PerformLayout();using(var bmp=new Bitmap(f.ClientSize.Width,f.ClientSize.Height)){f.DrawToBitmap(bmp,new Rectangle(Point.Empty,f.Size));bmp.Save("layout.png");}}}}}