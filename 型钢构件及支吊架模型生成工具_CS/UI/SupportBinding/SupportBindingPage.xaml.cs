using System;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using Bentley.DgnPlatformNET;
using Bentley.MstnPlatformNET;

namespace SteelSectionProbe
{
    internal partial class SupportBindingPage : UserControl, IWorkspacePage
    {
        private SupportBindingTarget target;
        private SupportBindingRecord draft;
        private bool active, pickingTarget;
        private int revision;
        public string PageId { get { return "support-binding"; } }
        public string PageTitle { get { return "支吊架组合绑定"; } }
        public string PageSubtitle { get { return "关联承重支架，生成多行ISO引注"; } }
        public FrameworkElement View { get { return this; } }
        internal SupportBindingPage() { InitializeComponent(); }
        public void OnActivated()
        {
            if (active) return;
            active = true; revision++;
            SupportBindingLocateTool.Picked += OnPicked;
            SupportBindingLocateTool.Ended += OnEnded;
            TransactionManager.OnUndoRedoFinished += UndoFinished;
            Display(null);
        }
        public void OnDeactivated()
        {
            if (!active) return;
            active = false; revision++;
            SupportBindingLocateTool.Picked -= OnPicked;
            SupportBindingLocateTool.Ended -= OnEnded;
            TransactionManager.OnUndoRedoFinished -= UndoFinished;
            SupportBindingLocateTool.End();
            Display(null);
        }
        public void OnWorkspaceClosing() { OnDeactivated(); }
        private void BeginPick(bool forTarget)
        {
            if (!active) return;
            if (SupportBindingLocateTool.IsActive && pickingTarget == forTarget)
            { Status("正在点取，可直接选择下一处。", false); return; }
            StopPicking(); pickingTarget = forTarget;
            SupportBindingLocateTool.Begin(); StopButton.IsEnabled = true;
            Status(forTarget ? "请选择已确认的原生管夹或耳轴。" : "请选择承重支架整组，可连续点取；右键结束。", false);
        }
        private void PickTarget_Click(object sender, RoutedEventArgs e)
        { try { BeginPick(true); } catch (Exception ex) { Status(ex.Message, true); } }
        private void AddMember_Click(object sender, RoutedEventArgs e)
        { try { if (target != null) BeginPick(false); } catch (Exception ex) { Status(ex.Message, true); } }
        private void Stop_Click(object sender, RoutedEventArgs e) { StopPicking(); Status("已结束点取，未保存的列表可继续编辑。", false); }
        private void StopPicking() { revision++; SupportBindingLocateTool.End(); StopButton.IsEnabled = false; }
        private void OnEnded() { revision++; StopButton.IsEnabled = false; }
        private void OnPicked(LocatedElement located)
        {
            if (!active || located == null) return;
            int request = revision; bool forTarget = pickingTarget;
            Dispatcher.BeginInvoke(new Action(() =>
            {
                if (!active || request != revision) return;
                try
                {
                    if (forTarget)
                    {
                        var value = SupportBindingReader.ReadTarget(located);
                        StopPicking(); Display(value);
                        Status("已读取管夹及现有关联，可添加承重支架。", false);
                    }
                    else if (target != null)
                    {
                        if (NativeSupportElements.ActiveModelToken() != target.ModelToken)
                            throw new InvalidOperationException("活动模型已改变，请重新选择管夹。");
                        var member = SupportBindingReader.ReadMember(located);
                        var updated = SupportBindingComposer.Copy(draft);
                        updated.Members.Add(member); SupportBindingComposer.Validate(updated);
                        draft = updated; RefreshList(draft.Members.Count - 1);
                        Status("已添加承重支架，点击保存绑定后生效。", false);
                    }
                }
                catch (Exception ex) { Status("读取失败：" + ex.Message, true); }
            }));
        }
        private void Reload_Click(object sender, RoutedEventArgs e)
        {
            if (!active || target == null) return;
            StopPicking();
            try
            {
                if (NativeSupportElements.ActiveModelToken() != target.ModelToken)
                    throw new InvalidOperationException("活动模型已改变，请重新点取管夹。");
                Display(SupportBindingReader.ReadTarget(new LocatedElement {
                    ModelRef = Session.Instance.GetActiveDgnModel(), ElementId = target.ElementId }));
                Status("已重新读取，未保存的列表修改已放弃。", false);
            }
            catch (Exception ex) { Display(null); Status(ex.Message, true); }
        }
        private void Save_Click(object sender, RoutedEventArgs e)
        {
            if (!active || target == null || draft == null) return;
            StopPicking();
            try
            {
                string elapsed;
                var updated = WriteDuration.Measure(() => SupportBindingEditor.Apply(target, draft), out elapsed);
                Display(updated);
                Status("组合绑定已保存，用时 " + elapsed + "；重新提取ISO可读取新引注。", false);
            }
            catch (Exception ex) { Status("保存失败：" + ex.Message, true); }
        }
        private void UndoFinished(object sender, OnUndoRedoFinishedEventArgs e)
        {
            if (!active) return;
            StopPicking(); Display(null);
            Status("模型已撤销或重做，请重新选择管夹以读取当前绑定。", false);
        }
        private void Display(SupportBindingTarget value)
        {
            target = value; draft = value == null ? null : SupportBindingComposer.Copy(value.Binding);
            TargetText.Text = value == null ? "尚未选择管夹或耳轴" : value.BaseTag + "\n元素 " + value.ElementId;
            AddMemberButton.IsEnabled = ReloadButton.IsEnabled = active && value != null;
            SyncMaterialsButton.IsEnabled = active;
            RefreshList(-1);
        }
        private void RefreshList(int selected)
        {
            MembersList.ItemsSource = draft == null ? null : draft.Members.Select((m, i) =>
                SupportBindingComposer.Prefix(i + 2) + m.Tag + "  ·  元素 " + m.ElementId).ToArray();
            MembersList.SelectedIndex = selected;
            RefreshState();
        }
        private void Member_Changed(object sender, SelectionChangedEventArgs e) { if (UpButton != null) RefreshState(); }
        private void RefreshState()
        {
            int index = MembersList.SelectedIndex, count = draft == null ? 0 : draft.Members.Count;
            UpButton.IsEnabled = active && index > 0;
            DownButton.IsEnabled = active && index >= 0 && index < count - 1;
            RemoveButton.IsEnabled = active && index >= 0;
            ClearButton.IsEnabled = active && count > 0;
            RefreshMembersButton.IsEnabled = active && count > 0;
            ConfirmButton.IsEnabled = false;
            if (draft == null)
            { PreviewText.Text = "选择管夹后显示引注"; EditStateText.Text = "尚未选择管夹"; return; }
            try
            {
                PreviewText.Text = SupportBindingComposer.Compose(draft, false);
                bool changed = SupportBindingStore.Encode(draft) != SupportBindingStore.Encode(target.Binding) ||
                    SupportBindingComposer.Compose(draft, true) != target.Alias;
                ConfirmButton.IsEnabled = active && (changed || count > 0);
                EditStateText.Text = changed ? "列表已修改，尚未保存。" : count > 0 ? "列表已保存；再次保存可核对最大管径计材归属。" : "当前列表已保存。";
            }
            catch (Exception ex) { EditStateText.Text = ex.Message; }
        }
        private void Move(int delta)
        {
            if (!active || draft == null) return;
            int index = MembersList.SelectedIndex, next = index + delta;
            if (index < 0 || next < 0 || next >= draft.Members.Count) return;
            StopPicking(); var item = draft.Members[index]; draft.Members.RemoveAt(index); draft.Members.Insert(next, item);
            RefreshList(next);
        }
        private void Up_Click(object sender, RoutedEventArgs e) { Move(-1); }
        private void Down_Click(object sender, RoutedEventArgs e) { Move(1); }
        private void Remove_Click(object sender, RoutedEventArgs e)
        {
            if (!active || draft == null || MembersList.SelectedIndex < 0) return;
            int index = MembersList.SelectedIndex; StopPicking(); draft.Members.RemoveAt(index);
            RefreshList(Math.Min(index, draft.Members.Count - 1));
            Save_Click(sender, e);
        }
        private void Clear_Click(object sender, RoutedEventArgs e)
        {
            if (!active || draft == null) return;
            StopPicking(); draft.Members.Clear(); RefreshList(-1);
            Save_Click(sender, e);
        }
        private void SyncMaterials_Click(object sender, RoutedEventArgs e)
        {
            if (!active) return;
            StopPicking();
            try
            {
                SupportBindingEditor.SynchronizeAllMaterials();
                Status("已删除本模型里遗留的组合材料附注。承重编号仍在管夹上，未保存的列表不参与。", false);
            }
            catch (Exception ex) { Status("材料同步失败：" + ex.Message, true); }
        }
        private void RefreshMembers_Click(object sender, RoutedEventArgs e)
        {
            if (!active || target == null || draft == null) return;
            StopPicking();
            try
            {
                if (NativeSupportElements.ActiveModelToken() != target.ModelToken)
                    throw new InvalidOperationException("活动模型已改变，请重新点取管夹。");
                string modelId = Session.Instance.GetActiveDgnModel().GetModelId().ToString();
                var updated = SupportBindingComposer.Copy(draft);
                for (int i = 0; i < updated.Members.Count; i++)
                {
                    var member = updated.Members[i];
                    if (member.ModelId != modelId) throw new InvalidOperationException("承重支架所属模型不一致，请移除后重新点取。");
                    try
                    {
                        var current = SupportBindingReader.ReadMember(new LocatedElement {
                            ModelRef = Session.Instance.GetActiveDgnModel(), ElementId = member.ElementId });
                        if (current.ItemType != member.ItemType) throw new InvalidOperationException("承重支架类型已改变，请移除后重新点取。");
                        updated.Members[i] = current;
                    }
                    catch (Exception ex) { throw new InvalidOperationException("元素 " + member.ElementId + "（" + member.Tag + "）：" + ex.Message, ex); }
                }
                draft = updated; RefreshList(-1);
                Status("已核对承重支架并读取当前编号，修改后须保存绑定。", false);
            }
            catch (Exception ex) { Status("核对失败：" + ex.Message, true); }
        }
        private static void Status(string text, bool error) { MainWindow.Current?.SetStatus(text, error); }
    }
}
