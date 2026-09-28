using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using Microsoft.Win32;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal partial class SupportStatisticsPage : UserControl, IWorkspacePage
    {
        private SupportStatisticsSnapshot current;
        private bool active;
        public string PageId { get { return "support-statistics"; } }
        public string PageTitle { get { return "支吊架统计"; } }
        public string PageSubtitle { get { return "当前 DGN 的支吊架、材料汇总与清单导出"; } }
        public FrameworkElement View { get { return this; } }
        internal SupportStatisticsPage() { InitializeComponent(); }
        public void OnActivated()
        {
            active=true;
            Dispatcher.BeginInvoke(new Action(delegate { if (active) Refresh(); }));
        }
        public void OnDeactivated() { active=false; }
        public void OnWorkspaceClosing() { active=false; }
        private void ReportScrollViewer_SizeChanged(object sender,SizeChangedEventArgs e)
        {
            UpdateReportGridWidth();
        }
        private void ReportScrollViewer_ScrollChanged(object sender,ScrollChangedEventArgs e)
        {
            if (e.ViewportWidthChange!=0) UpdateReportGridWidth();
        }
        private void UpdateReportGridWidth()
        {
            double available=ReportScrollViewer.ViewportWidth;
            if (available<=0) available=ReportScrollViewer.ActualWidth;
            if (available<=0) return;
            double gridWidth=Math.Max(180,available-36);
            if (Math.Abs(TypeGrid.Width-gridWidth)<0.5) return;
            TypeGrid.Width=gridWidth;
            SupportGrid.Width=gridWidth;
            MaterialGrid.Width=gridWidth;
        }
        private void Refresh_Click(object sender,RoutedEventArgs e) { Refresh(); }
        private bool Refresh()
        {
            try
            {
                var next=SupportStatisticsReader.Read();
                current=next;
                TotalText.Text=next.AssemblyCount.ToString(CultureInfo.InvariantCulture)+" 套";
                int assemblies=next.Records.Count(r=>string.Equals(r.RecordKind,"Assembly",
                    StringComparison.OrdinalIgnoreCase));
                CountText.Text="整组 "+assemblies+" 条 · 构件 "+next.ComponentRecordCount+
                    " 条 · 材料 "+next.Materials.Count+" 项";
                FileText.Text=Session.Instance.GetActiveDgnFile().GetFileName()+
                    " · 读取时间 "+next.ReadAt.ToString("yyyy-MM-dd HH:mm:ss");
                TypeGrid.ItemsSource=next.SupportsByType.Select(t=>new TypeRow {
                    SupportType=t.SupportType,AssemblyCount=t.AssemblyCount,
                    AssemblyTags=string.Join("、",t.AssemblyTags)
                }).ToList();
                var detail=new Dictionary<ulong,List<string>>();
                foreach(var record in next.Records.Where(r=>!string.Equals(r.RecordKind,
                    "Assembly",StringComparison.OrdinalIgnoreCase)))
                {
                    List<string> parts;
                    if (!detail.TryGetValue(record.ElementId,out parts))
                    { parts=new List<string>(); detail.Add(record.ElementId,parts); }
                    parts.Add(record.ComponentName+"("+record.Specification+")"+
                        (record.Quantity!=1?"×"+record.Quantity:""));
                }
                SupportGrid.ItemsSource=next.Records.Where(r=>string.Equals(r.RecordKind,
                    "Assembly",StringComparison.OrdinalIgnoreCase)).Select(r=>{
                    List<string> parts;
                    detail.TryGetValue(r.ElementId,out parts);
                    return new SupportRow { SupportType=r.SupportType,AssemblyTag=r.AssemblyTag,
                        PipeNumber=r.PipeNumber,Specification=r.Specification,
                        Details=parts==null?"":string.Join("；",parts),
                        ElementId=r.ElementId.ToString(CultureInfo.InvariantCulture) };
                }).ToList();
                MaterialGrid.ItemsSource=next.Materials.Select(m=>new MaterialRow {
                    SupportType=m.SupportType,ComponentName=m.ComponentName,
                    Specification=m.Specification,Unit=m.Unit,Quantity=m.Quantity,
                    TotalDesignLengthMm=m.TotalDesignLengthMm.ToString("F3",CultureInfo.InvariantCulture)
                }).ToList();
                ExcelButton.IsEnabled=JsonButton.IsEnabled=next.Records.Count>0;
                SetStatus(next.Records.Count>0
                    ? "统计完成：共 "+next.AssemblyCount+" 套支吊架。"
                    : "当前活动 DGN 没有 PipeSupportComponents 支吊架记录。",false);
                return true;
            }
            catch(Exception ex)
            {
                current=null;
                ExcelButton.IsEnabled=JsonButton.IsEnabled=false;
                SetStatus("支吊架统计读取失败："+ex.Message,true);
                return false;
            }
        }
        private void Excel_Click(object sender,RoutedEventArgs e) { Export(true); }
        private void Json_Click(object sender,RoutedEventArgs e) { Export(false); }
        private void Export(bool excel)
        {
            if (!Refresh() || current==null || current.Records.Count==0)
            { SetStatus("没有可导出的支吊架记录。",true); return; }
            var dialog=new SaveFileDialog {
                Title=excel?"导出支吊架 Excel 清单":"导出支吊架 JSON 清单",
                FileName=SupportExportName.Suggest(
                    Session.Instance.GetActiveDgnFile().GetFileName(),DateTime.Now)+
                    (excel?".xlsx":".json"),
                DefaultExt=excel?".xlsx":".json",
                Filter=excel?"Excel 工作簿 (*.xlsx)|*.xlsx":"JSON 文件 (*.json)|*.json",
                AddExtension=true,OverwritePrompt=true
            };
            if (dialog.ShowDialog()!=true) return;
            try
            {
                if (excel) SupportStatisticsExporter.WriteExcel(dialog.FileName,current);
                else SupportStatisticsExporter.WriteJson(dialog.FileName,current);
                SetStatus((excel?"Excel":"JSON")+" 清单已导出："+dialog.FileName,false);
            }
            catch(Exception ex) { SetStatus("导出失败："+ex.Message,true); }
        }
        private static void SetStatus(string message,bool error)
        {
            if (MainWindow.Current!=null) MainWindow.Current.SetStatus(message,error);
        }
        private sealed class TypeRow
        {
            public string SupportType { get; set; }
            public int AssemblyCount { get; set; }
            public string AssemblyTags { get; set; }
        }
        private sealed class SupportRow
        {
            public string SupportType { get; set; }
            public string AssemblyTag { get; set; }
            public string PipeNumber { get; set; }
            public string Specification { get; set; }
            public string Details { get; set; }
            public string ElementId { get; set; }
        }
        private sealed class MaterialRow
        {
            public string SupportType { get; set; }
            public string ComponentName { get; set; }
            public string Specification { get; set; }
            public string Unit { get; set; }
            public int Quantity { get; set; }
            public string TotalDesignLengthMm { get; set; }
        }
    }
}
