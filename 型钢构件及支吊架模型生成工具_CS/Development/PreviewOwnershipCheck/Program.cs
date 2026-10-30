using System;
using System.Linq;
using System.Reflection;
using System.Runtime.ExceptionServices;
using Bentley.DgnPlatformNET.Elements;
using SteelSectionProbe;

internal static class Program
{
    private static int checks;
    private static int scenarios;

    private static void Main()
    {
        var types = new[]
        {
            typeof(BracketPreviewSession), typeof(PadPlatePreviewSession), typeof(PortalFramePreviewSession),
            typeof(LBracketPreviewSession), typeof(HandrailPreviewSession), typeof(SquareManholePreviewSession),
            typeof(TFramePreviewSession), typeof(TriangleBracketPreviewSession)
        };
        foreach (var type in types)
        {
            Run(type, "成功确认后取消保留正式件", session =>
            {
                session.Show();
                var formal = Host.Active.Single();
                True(session.HasPreview, "新预览应受会话管理");
                session.Confirm();
                True(!session.HasPreview, "确认应解除所有权");
                True(Host.StatisticsWrites == (session.RecordsStatistics ? 1 : 0), "统计只在确认写入");
                if (session.RecordsStatistics) True(ReferenceEquals(Host.LastPlan, session.LastPlan), "统计使用当前计划");
                session.Cancel();session.Cancel();
                True(Host.Active.Single() == formal && formal.DeleteAttempts == 0, "取消不得误删正式件");
            });
            Run(type, "正常更新先写新件再删除旧件", session =>
            {
                session.Show();var old = Host.Active.Single();
                session.Show();var current = Host.Active.Single();
                True(old != current && !old.IsValid, "成功更新应仅留下新预览");
                True(old.ActiveCountAtDelete == 2, "旧预览删除前新预览必须已写入");
                session.Confirm();session.Cancel();
                True(Host.Active.Single() == current, "更新确认不得保留旧件或误删新件");
            });
            Run(type, "构建失败保留旧件但禁止确认", session =>
            {
                session.Show();var old = Host.Active.Single();
                Host.FailNextBuild = true;
                Fails(session.Show);
                True(Host.Active.Single() == old && session.HasPreview, "构建失败不删除旧预览");
                RejectConfirmation(session);
                session.Cancel();True(Host.Active.Length == 0 && !session.HasPreview, "取消应清理旧件");
            });
            Run(type, "AddToModel返回失败", session =>
            {
                session.Show();var old = Host.Active.Single();
                Host.FailNextAdd = true;
                Fails(session.Show);
                True(Host.Active.Single() == old && old.DeleteAttempts == 0, "写入失败不删除旧件");
                RejectConfirmation(session);
                session.Cancel();True(Host.Active.Length == 0, "旧件仍可取消");
            });
            Run(type, "AddToModel抛出异常", session =>
            {
                session.Show();var old = Host.Active.Single();
                Host.ThrowNextAdd = true;
                Fails(session.Show);
                True(Host.Active.Single() == old && session.HasPreview, "写入异常不能丢旧件所有权");
                RejectConfirmation(session);
                session.Cancel();True(Host.Active.Length == 0, "写入异常后可以取消");
            });
            Run(type, "旧删除失败新回收成功", session =>
            {
                session.Show();var old = Host.Active.Single();old.DeleteFailures = 1;
                Fails(session.Show);
                True(Host.Active.Single() == old && session.HasPreview, "回收成功后仍持有旧件");
                RejectConfirmation(session);
                session.Cancel();True(Host.Active.Length == 0 && !session.HasPreview, "失败后取消可清理旧件");
            });
            Run(type, "旧新删除同时失败且取消继续清理其他件", session =>
            {
                session.Show();var old = Host.Active.Single();old.DeleteFailures = 2;
                Host.NextDeleteFailures = 1;
                var error = Fails(session.Show);
                var replacement = Host.Active.Single(element => element != old);
                True(error.Message.Contains("新预览清理失败"), "错误应保留新件回收失败信息");
                True(Host.Active.Length == 2 && session.HasPreview, "双失败后全部元素仍受管理");
                RejectConfirmation(session);
                Fails(session.Cancel);
                True(Host.Active.Single() == old && replacement.DeleteAttempts == 2, "取消遇到旧件失败仍须尝试新件");
                RejectConfirmation(session);
                session.Cancel();session.Cancel();
                True(Host.Active.Length == 0 && !session.HasPreview, "再次取消应清空全部残留");
            });
            Run(type, "双删除异常后可以重新更新并确认", session =>
            {
                session.Show();var old = Host.Active.Single();old.DeleteExceptions = 1;
                Host.NextDeleteExceptions = 1;
                Fails(session.Show);
                True(Host.Active.Length == 2, "双删除异常不得遗失任何件");
                RejectConfirmation(session);
                session.Show();var current = Host.Active.Single();
                True(current != old && Host.Created.Count == 3, "重新更新应清完此前两个残留");
                session.Confirm();session.Cancel();
                True(Host.Active.Single() == current, "只有更新成功的新件能成为正式件");
            });
            Run(type, "取消失败使原候选失效", session =>
            {
                session.Show();var old = Host.Active.Single();old.DeleteFailures = 1;
                Fails(session.Cancel);
                True(session.HasPreview && Host.Active.Single() == old, "取消失败应保持清理所有权");
                RejectConfirmation(session);
                session.Cancel();True(!session.HasPreview && Host.Active.Length == 0, "再次取消应成功");
            });
            Run(type, "宿主已删除的预览不能确认", session =>
            {
                session.Show();Host.Active.Single().DeleteFromModel();
                RejectConfirmation(session);
                session.Cancel();True(!session.HasPreview, "失效预览可解除清理所有权");
            });
            Run(type, "宿主已删除旧件后可更新", session =>
            {
                session.Show();Host.Active.Single().DeleteFromModel();
                session.Show();session.Confirm();session.Cancel();
                True(Host.Active.Length == 1 && !session.HasPreview, "更新应忽略宿主已删除旧件");
            });
            Run(type, "多残留后写入失败仍可全部取消", session =>
            {
                session.Show();Host.Active.Single().DeleteFailures = 1;Host.NextDeleteFailures = 1;
                Fails(session.Show);Host.FailNextAdd = true;Fails(session.Show);
                True(Host.Active.Length == 2 && session.HasPreview, "后续写入失败不得遗失原残留");
                RejectConfirmation(session);
                session.Cancel();True(Host.Active.Length == 0 && !session.HasPreview, "取消应遍历全部原残留");
            });
            Run(type, "首次构建失败不创建预览", session =>
            {
                Host.FailNextBuild = true;Fails(session.Show);RejectConfirmation(session);
                session.Cancel();True(!session.HasPreview && Host.Active.Length == 0, "首次失败不能持有虚假预览");
            });
            if (type != typeof(SquareManholePreviewSession))
                Run(type, "统计失败保留预览所有权", session =>
                {
                    session.Show();Host.FailNextStatistics = true;Fails(session.Confirm);
                    True(session.HasPreview && Host.Active.Length == 1 && Host.StatisticsWrites == 0, "统计失败不能释放所有权");
                    session.Cancel();True(!session.HasPreview && Host.Active.Length == 0, "统计失败后可以取消");
                });
        }
        Run(typeof(TFramePreviewSession), "T架筋板编号只更新有效候选", session =>
        {
            session.Show();
            True((string)session.Call("UpdateStiffener", "A") == "D15-A", "D15保留编号更新能力");
            Host.FailNextBuild = true;Fails(session.Show);
            True(session.Call("UpdateStiffener", "B") == null, "失败旧预览不能更新筋板编号");
            session.Cancel();
        });
        Run(typeof(SquareManholePreviewSession), "人孔只记录最新成功写入耗时", session =>
        {
            session.Show();var elapsed = session.Property("WriteElapsed");
            Host.FailNextAdd = true;Fails(session.Show);
            True(Equals(session.Property("WriteElapsed"), elapsed), "失败更新不能覆盖上次成功写入耗时");
            session.Cancel();
        });
        Console.WriteLine("PASS PreviewOwnershipCheck: " + scenarios + " scenarios, " + checks + " assertions across 8 real preview sessions.");
    }

    private static void Run(Type type, string name, Action<SessionCase> test)
    {
        Host.Reset();
        try { test(new SessionCase(type));scenarios++; }
        catch (Exception error) { throw new InvalidOperationException(type.Name + " / " + name, error); }
    }
    private static void RejectConfirmation(SessionCase session)
    {
        var before = Host.StatisticsWrites;
        Fails(session.Confirm);
        True(Host.StatisticsWrites == before, "失效或多残留预览不得写入正式统计");
        True(Host.Active.All(element => !element.Confirmed), "残留元素不得变成正式件");
    }
    private static InvalidOperationException Fails(Action action)
    {
        try { action(); }
        catch (InvalidOperationException error) { checks++;return error; }
        throw new Exception("预期操作失败，但实际成功。");
    }
    private static void True(bool condition, string message)
    {
        if (!condition) throw new Exception(message);
        checks++;
    }

    private sealed class SessionCase
    {
        private readonly Type type;
        private readonly object session;
        internal object LastPlan;
        internal SessionCase(Type type) { this.type = type;session = Activator.CreateInstance(type, true); }
        internal bool RecordsStatistics { get { return type != typeof(SquareManholePreviewSession); } }
        internal bool HasPreview { get { return (bool)Property("HasPreview"); } }
        internal void Show()
        {
            var method = type.GetMethod("Show", BindingFlags.Instance | BindingFlags.NonPublic)
                ?? type.GetMethod("Regenerate", BindingFlags.Instance | BindingFlags.NonPublic);
            var args = method.GetParameters().Select(parameter => Activator.CreateInstance(parameter.ParameterType, true)).ToArray();
            LastPlan = args[0];
            Invoke(method, args);
        }
        internal void Confirm() { Call("Confirm"); }
        internal void Cancel() { Call("Cancel"); }
        internal object Property(string name) { return type.GetProperty(name, BindingFlags.Instance | BindingFlags.NonPublic).GetValue(session); }
        internal object Call(string name, params object[] args)
        { return Invoke(type.GetMethod(name, BindingFlags.Instance | BindingFlags.NonPublic), args); }
        private object Invoke(MethodInfo method, object[] args)
        {
            try { return method.Invoke(session, args); }
            catch (TargetInvocationException error)
            {
                ExceptionDispatchInfo.Capture(error.InnerException).Throw();throw;
            }
        }
    }
}
