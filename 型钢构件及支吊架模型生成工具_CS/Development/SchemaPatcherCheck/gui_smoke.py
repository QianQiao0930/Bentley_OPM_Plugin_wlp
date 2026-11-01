"""界面冒烟检查：驱动真实 App 走完 检查→执行修改→再检查→保存日志，弹窗自动应答，并截图到 obj/smoke。"""
import ctypes
import os
import shutil
import subprocess
import sys
import time
import tkinter as tk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "Deployment", "SchemaPatcher"))
sys.path.insert(0, HERE)

from schema_patcher import gui  # noqa: E402
from schema_patcher.features import FEATURES  # noqa: E402
from test_schema_patcher import REAL_FIXTURES, Workspace  # noqa: E402

SMOKE = os.path.join(HERE, "obj", "smoke")
CAPTURE = r"""
param([long]$Hwnd,[string]$Path)
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System; using System.Runtime.InteropServices;
public static class W { [StructLayout(LayoutKind.Sequential)] public struct R { public int L,T,Ri,B; }
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out R r);
 [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
 [DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); }
'@
[void][W]::SetProcessDPIAware()
$r=New-Object W+R; [void][W]::GetWindowRect([IntPtr]$Hwnd,[ref]$r)
$bmp=New-Object System.Drawing.Bitmap ($r.Ri-$r.L),($r.B-$r.T)
$g=[System.Drawing.Graphics]::FromImage($bmp); $dc=$g.GetHdc(); [void][W]::PrintWindow([IntPtr]$Hwnd,$dc,2); $g.ReleaseHdc($dc)
$bmp.Save($Path,[System.Drawing.Imaging.ImageFormat]::Png)
"""


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    shutil.rmtree(SMOKE, ignore_errors=True)
    os.makedirs(SMOKE)
    script = os.path.join(SMOKE, "capture.ps1")
    with open(script, "w", encoding="utf-8-sig") as stream:
        stream.write(CAPTURE)
    ws = Workspace(REAL_FIXTURES)
    gui._SETTINGS = os.path.join(SMOKE, "settings.json")
    answers = []
    gui.messagebox.askyesno = lambda title, text, **k: answers.append(("askyesno", title, text)) or True
    gui.messagebox.showinfo = lambda title, text, **k: answers.append(("showinfo", title, text))
    gui.messagebox.showerror = lambda title, text, **k: answers.append(("showerror", title, text))
    gui.messagebox.showwarning = lambda title, text, **k: answers.append(("showwarning", title, text))
    saved_log = os.path.join(SMOKE, "saved.log")
    gui.filedialog.asksaveasfilename = lambda **k: saved_log

    root = tk.Tk()
    app = gui.App(root)
    app.schema_var.set(ws.schema)
    app.backup_var.set(ws.backup)
    app.feature_var.set(FEATURES["all"].label)
    app._on_feature()

    def settle():
        deadline = time.time() + 60
        quiet = 0
        while time.time() < deadline and quiet < 5:
            root.update()
            quiet = quiet + 1 if not app.busy and app.queue.empty() else 0
            time.sleep(0.05)
        if app.busy:
            raise RuntimeError("界面处理超时")

    def capture(name):
        settle()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        target = os.path.join(SMOKE, name + ".png")
        # PrintWindow 会向本线程的窗口发消息，等待期间必须继续处理消息。
        process = subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script,
                                    str(hwnd), target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        while process.poll() is None:
            root.update()
            time.sleep(0.05)
        if process.returncode != 0 or not os.path.isfile(target):
            raise RuntimeError("截图失败：" + name)
        print("截图：" + target)

    try:
        capture("01_start")
        app._check()
        capture("02_check")
        assert not answers, answers
        app._apply()
        capture("03_apply")
        assert answers[0][0] == "askyesno", answers
        assert answers[-1][0] == "showinfo" and "修改完成" in answers[-1][1], answers
        app._check()
        capture("04_recheck")
        assert answers[-1][0] == "showinfo" and "无需修改" in answers[-1][2], answers
        app._apply()
        settle()
        assert answers[-1][0] == "showinfo" and "无需修改" in answers[-1][2], answers
        app._save_log()
        with open(saved_log, encoding="utf-8-sig") as stream:
            content = stream.read()
        assert "==== 详细记录 ====" in content and "修改后第" in content, "saved log incomplete"
        assert os.path.isfile(gui._SETTINGS), "settings not saved"
        print("PASS: 界面冒烟检查（检查/执行/已具备提醒/保存日志/记住路径）")
    finally:
        root.destroy()
        ws.cleanup()


if __name__ == "__main__":
    main()
