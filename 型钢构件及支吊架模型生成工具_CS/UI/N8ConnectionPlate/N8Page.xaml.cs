using System;
using System.Globalization;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using Bentley.GeometryNET;

namespace SteelSectionProbe
{
    internal partial class N8Page:UserControl,IWorkspacePage
    {
        private readonly N8PreviewSession preview=new N8PreviewSession();
        private readonly N8LastChoice.Data lastChoice=N8LastChoice.Load();
        private DPoint3d? point;
        private bool active,ready,locating;
        public string PageId {get{return "n8-connection-plate";}}
        public string PageTitle {get{return "N8 设备预焊件连接板";}}
        public string PageSubtitle {get{return "六种连接板 · 三种工况";}}
        public FrameworkElement View {get{return this;}}
        internal N8Page()
        {
            InitializeComponent();
            TypeCombo.ItemsSource=Enumerable.Range(0,6).Select(n=>"类型 "+n).ToArray();
            ModeCombo.ItemsSource=new[]{"H 保温","C 保冷","N 无保温"};
            MountCombo.ItemsSource=new[]{"竖直设备表面","水平设备顶面","水平设备底面"};
            TypeCombo.SelectedIndex=0;ModeCombo.SelectedIndex=0;MountCombo.SelectedIndex=0;
            RestoreLastChoice();   // 必须在 ready=true 之前，否则赋值会触发 Changed 类逻辑
            ready=true;Refresh();
        }
        /// <summary>恢复上次选择。必须在 <c>ready=true</c> 之前调用：
        /// 给 Combo / TextBox 赋值会触发 <c>Parameter_Changed</c>，ready 时它会去刷新预览。</summary>
        private void RestoreLastChoice()
        {
            try
            {
                TypeCombo.SelectedIndex=Math.Max(0,Math.Min(TypeCombo.Items.Count-1,lastChoice.TypeIndex));
                ModeCombo.SelectedIndex=Math.Max(0,Math.Min(ModeCombo.Items.Count-1,lastChoice.ModeIndex));
                MountCombo.SelectedIndex=Math.Max(0,Math.Min(MountCombo.Items.Count-1,lastChoice.MountIndex));
                HeadingText.Text=string.IsNullOrEmpty(lastChoice.Heading)?"0":lastChoice.Heading;
            }
            catch { /* 恢复失败就用当前默认值，不要挡住页面 */ }
        }
        private void SaveLastChoice()
        {
            try
            {
                lastChoice.TypeIndex=Math.Max(0,TypeCombo.SelectedIndex);
                lastChoice.ModeIndex=Math.Max(0,ModeCombo.SelectedIndex);
                lastChoice.MountIndex=Math.Max(0,MountCombo.SelectedIndex);
                lastChoice.Heading=HeadingText.Text??"0";
                N8LastChoice.Save(lastChoice);
            }
            catch { }
        }
        public void OnActivated()
        {
            active=true;G2AnchorLocateTool.Picked+=OnPicked;G2AnchorLocateTool.Ended+=OnEnded;
        }
        public void OnDeactivated() {Close();}
        public void OnWorkspaceClosing() {Close();}
        private void Close()
        {
            active=false;G2AnchorLocateTool.Picked-=OnPicked;G2AnchorLocateTool.Ended-=OnEnded;
            if(locating)G2AnchorLocateTool.End();locating=false;
            try {preview.Cancel();}catch(Exception ex){Status(ex.Message,true);}
            point=null;ConfirmButton.IsEnabled=false;
        }
        private N8Plan Plan()
        {
            double heading;
            if(!double.TryParse(HeadingText.Text,NumberStyles.Float,CultureInfo.CurrentCulture,out heading)&&
                !double.TryParse(HeadingText.Text,NumberStyles.Float,CultureInfo.InvariantCulture,out heading))
                throw new InvalidOperationException("朝向角必须是数字。");
            return N8Catalog.Resolve(Math.Max(0,TypeCombo.SelectedIndex),
                new[]{"H","C","N"}[Math.Max(0,ModeCombo.SelectedIndex)],heading,
                (G2MountFace)Math.Max(0,MountCombo.SelectedIndex));
        }
        private void Refresh()
        {
            try{SpecText.Text=Plan().Number+"；"+Plan().Specification;}
            catch(Exception ex){SpecText.Text=ex.Message;}
        }
        private void Parameter_Changed(object sender,RoutedEventArgs e)
        {
            if(!ready)return;Refresh();SaveLastChoice();
            if(point.HasValue)Regenerate();
        }
        private void Regenerate()
        {
            if(!point.HasValue)return;
            try
            {
                var plan=Plan();preview.Show(plan,point.Value);
                PreviewText.Text="预览："+plan.Number+"；"+plan.Specification;
                ConfirmButton.IsEnabled=true;Status("N8 预览已生成。",false);
            }
            catch(Exception ex){ConfirmButton.IsEnabled=false;Status(ex.Message,true);}
        }
        private void OnPicked(DPoint3d picked)
        {
            if(!active||!locating)return;
            Dispatcher.BeginInvoke(new Action(delegate{
                if(!active||!locating)return;
                point=picked;Regenerate();
            }));
        }
        private void OnEnded()
        {
            locating=false;try{preview.Cancel();}catch(Exception ex){Status(ex.Message,true);}
            point=null;ConfirmButton.IsEnabled=false;PreviewText.Text="已结束点取。";
        }
        private void Pick_Click(object sender,RoutedEventArgs e)
        {try{G2AnchorLocateTool.Begin();locating=true;}catch(Exception ex){Status(ex.Message,true);}}
        private void End_Click(object sender,RoutedEventArgs e){G2AnchorLocateTool.End();}
        private void Update_Click(object sender,RoutedEventArgs e){Regenerate();}
        private void Cancel_Click(object sender,RoutedEventArgs e)
        {try{preview.Cancel();point=null;ConfirmButton.IsEnabled=false;}catch(Exception ex){Status(ex.Message,true);}}
        private void Confirm_Click(object sender,RoutedEventArgs e)
        {try{preview.Confirm();point=null;ConfirmButton.IsEnabled=false;Status("N8 已生成。",false);}
         catch(Exception ex){Status(ex.Message,true);}}
        private static void Status(string value,bool error)
        {if(MainWindow.Current!=null)MainWindow.Current.SetStatus(value,error);}
    }
}
