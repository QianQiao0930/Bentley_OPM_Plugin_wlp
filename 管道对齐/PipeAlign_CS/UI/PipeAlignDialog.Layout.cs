using System;
using System.Drawing;
using System.Windows.Forms;

namespace PipeAlign
{
    internal sealed partial class PipeAlignDialog
    {
        private static readonly Color PageColor=Color.FromArgb(245,246,248);
        private static readonly Color BorderColor=Color.FromArgb(226,231,238);
        private static readonly Color InkColor=Color.FromArgb(31,42,61);
        private static readonly Color PrimaryColor=Color.FromArgb(42,54,68);
        private ListBox _pipeCards;
        private readonly ToolTip _detailTips=new ToolTip { AutoPopDelay=15000 };
        private readonly Font _numberFont=new Font("Consolas",9F);

        private void BuildUi()
        {
            AutoScaleMode=AutoScaleMode.Dpi;
            Font=new Font("Microsoft YaHei UI",9F);
            BackColor=PageColor;
            ClientSize=new Size(480,960);
            MinimumSize=SizeFromClientSize(new Size(480,960));
            MaximizeBox=false;
            var root=new TableLayoutPanel { Dock=DockStyle.Fill,ColumnCount=1,RowCount=8,Padding=new Padding(10),BackColor=PageColor };
            root.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));
            foreach(float h in new[]{104F,260F,110F,78F})root.RowStyles.Add(new RowStyle(SizeType.Absolute,h));
            root.RowStyles.Add(new RowStyle(SizeType.Percent,100));
            root.RowStyles.Add(new RowStyle(SizeType.Absolute,100));
            root.RowStyles.Add(new RowStyle(SizeType.Absolute,44));
            root.RowStyles.Add(new RowStyle(SizeType.Absolute,46));

            var reference=Card("01  基准管 · 目标标高来源");
            _pickReferenceButton=ActionButton("选择基准管",PickReference_Click);
            _pickReferenceButton.Dock=DockStyle.Top;
            _referenceLabel=new Label { Dock=DockStyle.Fill,AutoEllipsis=true,Font=_numberFont,Text="尚未选择基准管" };
            var referenceBody=new TableLayoutPanel { Dock=DockStyle.Fill,ColumnCount=2,RowCount=1 };
            referenceBody.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));referenceBody.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,110));
            referenceBody.Controls.Add(_referenceLabel,0,0);referenceBody.Controls.Add(_pickReferenceButton,1,0);reference.Controls.Add(referenceBody);
            root.Controls.Add(reference,0,0);

            var parameters=Card("02  对齐方式与表面模式");
            var fields=new TableLayoutPanel { Dock=DockStyle.Fill,ColumnCount=2,RowCount=4 };
            fields.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,76));fields.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));
            for(int i=0;i<3;i++)fields.RowStyles.Add(new RowStyle(SizeType.Absolute,34));fields.RowStyles.Add(new RowStyle(SizeType.Percent,100));
            _bottomRadio=Segment("管底",Mode_Changed);_centerRadio=Segment("管中心",Mode_Changed);_topRadio=Segment("管顶",Mode_Changed);
            _surfacePipeRadio=Segment("管道外表面",Surface_Changed);_surfaceInsulationRadio=Segment("保温层外表面",Surface_Changed);
            fields.Controls.Add(FieldLabel("对齐基准"),0,0);fields.Controls.Add(Segments(_bottomRadio,_centerRadio,_topRadio),1,0);
            fields.Controls.Add(FieldLabel("表面模式"),0,1);fields.Controls.Add(Segments(_surfacePipeRadio,_surfaceInsulationRadio),1,1);
            _toleranceInput=new NumericUpDown { Dock=DockStyle.Fill,DecimalPlaces=3,Increment=0.5M,Maximum=1000,Font=_numberFont,TextAlign=HorizontalAlignment.Right };
            _toleranceInput.ValueChanged+=Tolerance_Changed;
            fields.Controls.Add(FieldLabel("水平容差"),0,2);fields.Controls.Add(_toleranceInput,1,2);
            _detailTips.SetToolTip(_toleranceInput,"水平容差，单位 mm");
            _scopeSingleRadio=new RadioButton { Text="只移动选中的管道",Dock=DockStyle.Fill };
            _scopeGroupRadio=new RadioButton { Text="连同连通对象一起移动",Dock=DockStyle.Fill };
            _scopeZRadio=new RadioButton { Text="锁 Z 轴 · 立管伸缩，远端固定",Dock=DockStyle.Fill };
            var scope=new TableLayoutPanel { Dock=DockStyle.Fill,ColumnCount=1,RowCount=3,BackColor=PageColor,Padding=new Padding(5) };
            foreach(var radio in new[]{_scopeSingleRadio,_scopeGroupRadio,_scopeZRadio}){
                radio.CheckedChanged+=Scope_Changed;scope.RowStyles.Add(new RowStyle(SizeType.Percent,33.33F));scope.Controls.Add(radio);}
            fields.Controls.Add(FieldLabel("移动范围"),0,3);fields.Controls.Add(scope,1,3);parameters.Controls.Add(fields);root.Controls.Add(parameters,0,1);
            // 不显示死控件；保留内部字段兼容计算结果刷新。
            _zDeltaInput=new NumericUpDown { Minimum=decimal.MinValue,Maximum=decimal.MaxValue,DecimalPlaces=2,Visible=false };

            var targets=Card("03  目标管");
            _targetCountLabel=new Label { Location=new Point(340,7),Size=new Size(100,20),Anchor=AnchorStyles.Top|AnchorStyles.Right,TextAlign=ContentAlignment.MiddleRight };
            _pickTargetsButton=ActionButton("选择目标管",PickTargets_Click);_selectionSetButton=ActionButton("从选择集添加",SelectionSet_Click);
            _removeTargetButton=ActionButton("移除选中管",RemoveTarget_Click);_clearTargetsButton=ActionButton("清空目标管",ClearTargets_Click);
            var grid=new TableLayoutPanel { Dock=DockStyle.Fill,ColumnCount=2,RowCount=2 };
            grid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,50));grid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,50));
            grid.RowStyles.Add(new RowStyle(SizeType.Percent,50));grid.RowStyles.Add(new RowStyle(SizeType.Percent,50));
            grid.Controls.Add(_pickTargetsButton,0,0);grid.Controls.Add(_selectionSetButton,1,0);grid.Controls.Add(_removeTargetButton,0,1);grid.Controls.Add(_clearTargetsButton,1,1);
            targets.Controls.Add(grid);targets.Controls.Add(_targetCountLabel);root.Controls.Add(targets,0,2);

            var preview=Card("04  预览 · 临时线，不改管道");
            var previewRow=new FlowLayoutPanel { Dock=DockStyle.Fill,WrapContents=false };
            _showCurrentCheck=new CheckBox { Text="当前（蓝）",AutoSize=true,Checked=true };
            _showTargetCheck=new CheckBox { Text="对齐后（红）",AutoSize=true,Checked=true };
            _showCurrentCheck.CheckedChanged+=PreviewOption_Changed;_showTargetCheck.CheckedChanged+=PreviewOption_Changed;
            _refreshPreviewButton=ActionButton("刷新",RefreshPreview_Click);_refreshPreviewButton.Width=58;
            _clearPreviewButton=ActionButton("清除",ClearPreview_Click);_clearPreviewButton.Width=58;
            previewRow.Controls.AddRange(new Control[]{_showCurrentCheck,_showTargetCheck,_refreshPreviewButton,_clearPreviewButton});
            preview.Controls.Add(previewRow);root.Controls.Add(preview,0,3);

            var details=Card("05  管道明细 · 可多选移除");
            BuildPlanList(); // 保留原始行数据，不再显示宽表。
            _pipeCards=new ListBox { Dock=DockStyle.Fill,DrawMode=DrawMode.OwnerDrawFixed,ItemHeight=112,SelectionMode=SelectionMode.MultiExtended,
                IntegralHeight=false,BorderStyle=BorderStyle.None,BackColor=PageColor };
            _pipeCards.DrawItem+=DrawPipeCard;
            _pipeCards.MouseMove+=delegate(object sender,MouseEventArgs e){int i=_pipeCards.IndexFromPoint(e.Location);
                string tip=i<0?string.Empty:CardDetails((ListViewItem)_pipeCards.Items[i]);
                if(_detailTips.GetToolTip(_pipeCards)!=tip)_detailTips.SetToolTip(_pipeCards,tip);};
            details.Controls.Add(_pipeCards);root.Controls.Add(details,0,4);
            var readings=new Panel { Dock=DockStyle.Fill,BackColor=Color.White,Padding=new Padding(8) };
            _summaryLabel=new Label { Dock=DockStyle.Top,Height=35,AutoEllipsis=true,ForeColor=InkColor };
            _readoutLabel=new Label { Dock=DockStyle.Fill,AutoEllipsis=true,Font=_numberFont,ForeColor=Color.FromArgb(91,100,114) };
            readings.Controls.Add(_readoutLabel);readings.Controls.Add(_summaryLabel);root.Controls.Add(readings,0,5);
            var footer=new TableLayoutPanel { Dock=DockStyle.Fill,ColumnCount=3,RowCount=1 };
            footer.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,50));footer.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,20));footer.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,30));
            _applyButton=ActionButton("应用",Apply_Click);_applyButton.BackColor=PrimaryColor;_applyButton.ForeColor=Color.White;
            _resetButton=ActionButton("重置",Reset_Click);_saveOptionsButton=ActionButton("保存参数",SaveOptions_Click);
            footer.Controls.Add(_applyButton,0,0);footer.Controls.Add(_resetButton,1,0);footer.Controls.Add(_saveOptionsButton,2,0);root.Controls.Add(footer,0,6);
            _closeButton=new Button { Visible=false };_closeButton.Click+=Close_Click;
            _statusLabel=new Label { Dock=DockStyle.Fill,ForeColor=Color.FromArgb(69,122,171),AutoEllipsis=true,Text="选择基准管和目标管 → 自动预览 → 应用",Padding=new Padding(3) };
            root.Controls.Add(_statusLabel,0,7);Controls.Add(root);
        }

        private Panel Card(string title)
        {
            var panel=new Panel { Dock=DockStyle.Fill,BackColor=Color.White,Padding=new Padding(10,32,10,8),Margin=new Padding(0,0,0,7) };
            panel.Paint+=delegate(object sender,PaintEventArgs e){using(var pen=new Pen(BorderColor))e.Graphics.DrawRectangle(pen,0,0,panel.Width-1,panel.Height-1);
                TextRenderer.DrawText(e.Graphics,title,Font,new Point(10,9),InkColor);};return panel;
        }
        private Button ActionButton(string text,EventHandler action)
        {
            var b=new Button { Text=text,Dock=DockStyle.Fill,Height=30,FlatStyle=FlatStyle.Flat,BackColor=Color.White,ForeColor=InkColor,Margin=new Padding(3),UseVisualStyleBackColor=false };
            b.FlatAppearance.BorderColor=Color.FromArgb(201,211,224);b.FlatAppearance.MouseOverBackColor=PageColor;b.Click+=action;return b;
        }
        private Label FieldLabel(string text){return new Label { Text=text,Dock=DockStyle.Fill,TextAlign=ContentAlignment.MiddleLeft,ForeColor=Color.FromArgb(91,100,114) };}
        private RadioButton Segment(string text,EventHandler action)
        {
            var radio=new RadioButton { Text=text,Appearance=Appearance.Button,TextAlign=ContentAlignment.MiddleCenter,Dock=DockStyle.Fill,FlatStyle=FlatStyle.Flat,Margin=new Padding(1) };
            radio.FlatAppearance.BorderSize=0;radio.FlatAppearance.CheckedBackColor=PrimaryColor;radio.CheckedChanged+=action;radio.CheckedChanged+=delegate{
                radio.BackColor=radio.Checked?PrimaryColor:PageColor;radio.ForeColor=radio.Checked?Color.White:InkColor;};return radio;
        }
        private Control Segments(params RadioButton[] radios)
        {
            var row=new TableLayoutPanel { Dock=DockStyle.Fill,ColumnCount=radios.Length,RowCount=1,BackColor=PageColor };
            foreach(var radio in radios){row.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100F/radios.Length));row.Controls.Add(radio);}return row;
        }
        private static string CardDetails(ListViewItem row)
        {string text=row.Text;for(int i=1;i<row.SubItems.Count;i++)text+="\n"+row.SubItems[i].Text;return text;}
        private void RefreshCards()
        {
            if(_pipeCards==null)return;
            _pipeCards.BeginUpdate();_pipeCards.Items.Clear();foreach(ListViewItem row in _planList.Items)_pipeCards.Items.Add(row);_pipeCards.EndUpdate();
            _detailTips.SetToolTip(_readoutLabel,_readoutLabel.Text);_detailTips.SetToolTip(_summaryLabel,_summaryLabel.Text);
        }
        private void DrawPipeCard(object sender,DrawItemEventArgs e)
        {
            if(e.Index<0)return;var row=(ListViewItem)_pipeCards.Items[e.Index];bool selected=(e.State&DrawItemState.Selected)!=0;
            var box=new Rectangle(e.Bounds.X+2,e.Bounds.Y+3,e.Bounds.Width-5,e.Bounds.Height-6);
            using(var brush=new SolidBrush(selected?Color.FromArgb(227,233,242):Color.White))e.Graphics.FillRectangle(brush,box);
            using(var pen=new Pen(selected?PrimaryColor:BorderColor))e.Graphics.DrawRectangle(pen,box);
            TextRenderer.DrawText(e.Graphics,row.Text,_numberFont,new Rectangle(box.X+8,box.Y+7,box.Width-16,20),InkColor,TextFormatFlags.EndEllipsis);
            TextRenderer.DrawText(e.Graphics,row.SubItems[1].Text+" · "+row.SubItems[6].Text,Font,new Rectangle(box.X+8,box.Y+29,box.Width-16,18),Color.FromArgb(91,100,114),TextFormatFlags.EndEllipsis);
            int col=(box.Width-16)/3;
            string[] values={"当前 "+row.SubItems[3].Text,"目标 "+row.SubItems[4].Text,"ΔZ "+row.SubItems[5].Text};
            for(int i=0;i<3;i++)TextRenderer.DrawText(e.Graphics,values[i],_numberFont,new Rectangle(box.X+8+i*col,box.Y+50,col-3,20),InkColor,TextFormatFlags.Right|TextFormatFlags.EndEllipsis);
            string status=row.SubItems[7].Text;Color ink=status.StartsWith("已对齐")?Color.FromArgb(61,122,55):Color.FromArgb(154,111,20);
            TextRenderer.DrawText(e.Graphics,"外径 "+row.SubItems[2].Text+" mm · "+status,Font,new Rectangle(box.X+8,box.Y+76,box.Width-16,24),ink,TextFormatFlags.EndEllipsis);
            if(selected)e.DrawFocusRectangle();
        }
    }
}
