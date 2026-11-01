"""tkinter 界面：选择 Schema 目录、备份文件夹和修改内容，检查/执行并显示、保存记录。"""
import datetime
import json
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from . import VERSION
from .engine import PatchError, apply_plan, describe_plan, file_name, format_log, load_plan
from .features import FEATURES

_SETTINGS = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SteelSectionProbe", "SchemaPatcher",
                         "settings.json")
_COLORS = {"info": "#24292f", "ok": "#1a7f37", "change": "#1f6feb", "warn": "#9a6700", "error": "#cf222e",
           "title": "#24292f"}
_NO_CHANGE = "当前选择的 Schema 文件已经具备这些字段，无需修改。"


class App(object):
    def __init__(self, root):
        self.root = root
        self.queue = queue.Queue()
        self.busy = False
        self.session_logs = []
        self.last_run_dir = None
        root.title("OpenPlant 工作集 Schema 增补工具  V%s" % VERSION)
        root.geometry("940x700")
        root.minsize(780, 560)
        self._build()
        self._load_settings()
        self._on_feature()
        self._write("title", "使用步骤：1. 选择工作集 Schema 目录  2. 选择备份文件夹  3. 选择修改内容  4. 先「检查」再「执行修改」")
        self._write("info", "修改前请保存并关闭 OPM；修改完成后重启 OPM 生效。默认只读检查，不会改动文件。")
        root.after(100, self._poll)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------ 布局
    def _build(self):
        self.root.option_add("*Font", ("Microsoft YaHei UI", 10))
        style = ttk.Style(self.root)
        style.configure("Accent.TButton", foreground="#1f6feb")
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(1, weight=1)

        self.schema_var = tk.StringVar()
        self.backup_var = tk.StringVar()
        self.feature_var = tk.StringVar()
        ttk.Label(outer, text="Schema 目录").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(outer, textvariable=self.schema_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(outer, text="浏览…", command=self._pick_schema).grid(row=0, column=2)
        ttk.Label(outer, text="备份文件夹").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(outer, textvariable=self.backup_var).grid(row=1, column=1, sticky="ew", padx=6)
        ttk.Button(outer, text="浏览…", command=self._pick_backup).grid(row=1, column=2)
        ttk.Label(outer, text="修改内容").grid(row=2, column=0, sticky="w", pady=4)
        self.labels = [f.label for f in FEATURES.values()]
        combo = ttk.Combobox(outer, textvariable=self.feature_var, values=self.labels, state="readonly")
        combo.grid(row=2, column=1, sticky="ew", padx=6)
        combo.bind("<<ComboboxSelected>>", lambda _: self._on_feature())
        hint = ("Schema 目录一般为：工作集\\Standards\\OpenPlant\\Schemas，需包含 OpenPlant_3D / "
                "Supplemental_Modeling / Supplemental_Isometrics_Isoextractor 三份 .01.08.ecschema.xml")
        ttk.Label(outer, text=hint, foreground="#57606a", wraplength=820).grid(row=3, column=0, columnspan=3,
                                                                              sticky="w", pady=(2, 6))
        self.description = ttk.Label(outer, foreground="#1f6feb", wraplength=820, justify="left")
        self.description.grid(row=4, column=0, columnspan=3, sticky="w", pady=(0, 8))

        bar = ttk.Frame(outer)
        bar.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        self.buttons = [
            ttk.Button(bar, text="检查（只读）", command=self._check),
            ttk.Button(bar, text="执行修改", style="Accent.TButton", command=self._apply),
            ttk.Button(bar, text="保存日志…", command=self._save_log),
            ttk.Button(bar, text="打开备份文件夹", command=self._open_backup),
            ttk.Button(bar, text="清空显示", command=self._clear),
        ]
        for index, button in enumerate(self.buttons):
            button.pack(side="left", padx=(0 if index == 0 else 6, 0))

        self.text = ScrolledText(outer, wrap="word", height=20, font=("Microsoft YaHei UI", 10), relief="solid",
                                 borderwidth=1)
        self.text.grid(row=6, column=0, columnspan=3, sticky="nsew")
        outer.rowconfigure(6, weight=1)
        for tag, color in _COLORS.items():
            self.text.tag_configure(tag, foreground=color)
        self.text.tag_configure("title", font=("Microsoft YaHei UI", 10, "bold"))
        self.text.configure(state="disabled")

        self.status = tk.StringVar(value="就绪")
        ttk.Label(outer, textvariable=self.status, foreground="#57606a").grid(row=7, column=0, columnspan=3,
                                                                              sticky="w", pady=(6, 0))

    # ------------------------------------------------------------ 设置
    def _load_settings(self):
        data = {}
        try:
            with open(_SETTINGS, "r", encoding="utf-8-sig") as stream:
                data = json.load(stream)
        except (OSError, ValueError):
            pass
        self.schema_var.set(data.get("schema_dir", ""))
        self.backup_var.set(data.get("backup_dir", ""))
        key = data.get("feature")
        self.feature_var.set(FEATURES[key].label if key in FEATURES else self.labels[0])

    def _save_settings(self):
        try:
            os.makedirs(os.path.dirname(_SETTINGS), exist_ok=True)
            with open(_SETTINGS, "w", encoding="utf-8") as stream:
                json.dump({"schema_dir": self.schema_var.get().strip(), "backup_dir": self.backup_var.get().strip(),
                           "feature": self._feature_key()}, stream, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _on_close(self):
        if self.busy and not messagebox.askyesno("正在处理", "正在处理中，确定要退出吗？"):
            return
        self._save_settings()
        self.root.destroy()

    # ------------------------------------------------------------ 交互
    def _feature_key(self):
        label = self.feature_var.get()
        return next((k for k, f in FEATURES.items() if f.label == label), next(iter(FEATURES)))

    def _on_feature(self):
        feature = FEATURES[self._feature_key()]
        self.description.configure(text=feature.description)

    def _pick_schema(self):
        folder = filedialog.askdirectory(title="选择工作集 Schema 目录", initialdir=self.schema_var.get() or None)
        if folder:
            self.schema_var.set(os.path.normpath(folder))

    def _pick_backup(self):
        folder = filedialog.askdirectory(title="选择备份文件夹", initialdir=self.backup_var.get() or None)
        if folder:
            self.backup_var.set(os.path.normpath(folder))

    def _write(self, level, text):
        self.text.configure(state="normal")
        self.text.insert("end", text + "\n", level)
        self.text.see("end")
        self.text.configure(state="disabled")

    def _clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    def _set_busy(self, busy, message):
        self.busy = busy
        for button in self.buttons:
            button.configure(state="disabled" if busy else "normal")
        self.root.configure(cursor="watch" if busy else "")
        self.status.set(message)

    def _run(self, work, done):
        def target():
            try:
                self.queue.put((done, work(), None))
            except Exception as error:
                self.queue.put((done, None, error))
        threading.Thread(target=target, daemon=True).start()

    def _poll(self):
        try:
            while True:
                done, result, error = self.queue.get_nowait()
                done(result, error)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _schema_dir(self):
        folder = self.schema_var.get().strip()
        if not folder:
            messagebox.showwarning("缺少目录", "请先选择工作集 Schema 目录。")
            return None
        return folder

    def _stamp(self, title):
        self._write("title", "\n==== %s  %s ====" % (title, datetime.datetime.now().strftime("%H:%M:%S")))

    def _show_plan(self, plan):
        for level, text in describe_plan(plan):
            self._write(level, text)
        self.session_logs.append(format_log(plan))

    # ------------------------------------------------------------ 检查
    def _check(self):
        folder = self._schema_dir()
        if folder is None:
            return
        self._save_settings()
        key = self._feature_key()
        self._stamp("检查（只读）")
        self._set_busy(True, "正在检查…")
        self._run(lambda: load_plan(folder, key), self._check_done)

    def _check_done(self, plan, error):
        self._set_busy(False, "检查完成")
        if error is not None:
            self._write("error", "检查失败：%s" % error)
            self.status.set("检查失败")
            return
        self._show_plan(plan)
        if plan.blocked:
            self.status.set("存在冲突或错误，不能修改")
        elif plan.nothing_to_do:
            self.status.set("已具备，无需修改")
            messagebox.showinfo("无需修改", _NO_CHANGE)
        else:
            self.status.set("共 %d 处需要修改，尚未写入" % len(plan.pending))

    # ------------------------------------------------------------ 执行
    def _apply(self):
        folder = self._schema_dir()
        if folder is None:
            return
        backup = self.backup_var.get().strip()
        if not backup:
            messagebox.showwarning("缺少备份文件夹", "请先选择备份文件夹，修改前会把原文件备份到这里。")
            return
        self._save_settings()
        key = self._feature_key()
        self._stamp("执行修改")
        self._set_busy(True, "正在检查…")
        self._run(lambda: load_plan(folder, key), lambda plan, error: self._apply_checked(plan, error, backup))

    def _apply_checked(self, plan, error, backup):
        self._set_busy(False, "检查完成")
        if error is not None:
            self._write("error", "检查失败：%s" % error)
            return
        self._show_plan(plan)
        if plan.blocked:
            self.status.set("存在冲突或错误，未修改")
            messagebox.showerror("不能修改", "存在冲突或错误，未修改任何文件。详情见窗口中的红色条目。")
            return
        if plan.nothing_to_do:
            self.status.set("已具备，无需修改")
            messagebox.showinfo("无需修改", _NO_CHANGE)
            return
        files = sorted(set(file_name(i.file_key) for i in plan.pending))
        question = ("将修改 %d 处，涉及：\n%s\n\n原文件会先备份到：\n%s\n\n请确认 OPM 已关闭。是否继续？"
                    % (len(plan.pending), "\n".join(files), backup))
        if not messagebox.askyesno("确认修改", question):
            self._write("warn", "已取消，未修改任何文件。")
            self.status.set("已取消")
            return
        self._set_busy(True, "正在备份并写入…")
        self._run(lambda: apply_plan(plan, backup), self._apply_done)

    def _apply_done(self, result, error):
        self._set_busy(False, "完成")
        if error is not None:
            message = str(error) if isinstance(error, PatchError) else "%s: %s" % (type(error).__name__, error)
            self._write("error", "修改失败：%s" % message)
            self.status.set("修改失败")
            messagebox.showerror("修改失败", message)
            return
        self.last_run_dir = result.run_dir
        self.session_logs.append(result.log_text)
        self._write("ok", "修改完成，已备份原文件。重启 OPM 后生效。")
        for record in result.files:
            self._write("info", "  %s\n      备份：%s" % (record["schema"], record["backup"]))
        self._write("info", "  详细记录：%s" % result.log_path)
        self.status.set("修改完成：%s" % result.run_dir)
        messagebox.showinfo("修改完成", "修改完成，原文件已备份。\n\n备份与记录：\n%s\n\n重启 OPM 后生效。" % result.run_dir)

    # ------------------------------------------------------------ 记录
    def _save_log(self):
        name = "SchemaPatch_%s.log" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        target = filedialog.asksaveasfilename(title="保存日志", defaultextension=".log", initialfile=name,
                                              initialdir=self.backup_var.get() or None,
                                              filetypes=[("日志", "*.log"), ("文本", "*.txt"), ("全部", "*.*")])
        if not target:
            return
        content = self.text.get("1.0", "end").rstrip() + "\n"
        if self.session_logs:
            content += "\n\n==== 详细记录 ====\n\n" + "\n".join(self.session_logs)
        try:
            with open(target, "w", encoding="utf-8-sig") as stream:
                stream.write(content)
        except OSError as error:
            messagebox.showerror("保存失败", str(error))
            return
        self.status.set("日志已保存：%s" % target)

    def _open_backup(self):
        folder = self.last_run_dir or self.backup_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showinfo("备份文件夹", "备份文件夹尚不存在。")
            return
        os.startfile(folder)


def run():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    App(root)
    root.mainloop()
