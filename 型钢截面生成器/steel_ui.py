"""Two-level selector UI for the unified steel-section generator."""

from __future__ import division

import tkinter as tk
import traceback
from tkinter import messagebox, ttk

import win32gui

from MSPyMstnPlatform import PyCadInputQueue

import steel_registry
import steel_tool


MODE_PLACE = "place"
MODE_SWEEP = "sweep"


class BentleyTk(tk.Tk):
    """Tk loop integrated with Bentley's persistent Python loop."""

    def run_bentley_loop(self):
        attached = False
        while tk._default_root is not None:
            try:
                self.update_idletasks()
                self.update()
            except tk.TclError:
                break
            try:
                if not win32gui.IsWindow(self.winfo_id()):
                    break
                if not attached:
                    host_frame = win32gui.GetParent(self.winfo_id())
                    if host_frame:
                        PyCadInputQueue.AttachTkinterToolSetting(host_frame)
                        attached = True
            except tk.TclError:
                break
            PyCadInputQueue.PythonMainLoop()


class SteelSectionDialog(BentleyTk):
    def __init__(self):
        BentleyTk.__init__(self)
        self._family_id_by_label = {}
        self._insertion_id_by_label = {}
        self._family = tk.StringVar()
        self._profile = tk.StringVar()
        self._insertion = tk.StringVar()
        self._status = tk.StringVar()
        self._mode = tk.StringVar(value=MODE_PLACE)
        self._delete_path = tk.BooleanVar(value=False)

        self.title("型钢截面生成器")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._build()
        self._load_family_choices()

    def _build(self):
        root = ttk.Frame(self, padding=12)
        root.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(1, weight=1)

        ttk.Label(root, text="型钢截面生成器", font=("Microsoft YaHei UI", 12, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )

        selector = ttk.LabelFrame(root, text="1. 选择型钢", padding=10)
        selector.grid(row=1, column=0, columnspan=2, sticky="ew")
        selector.columnconfigure(1, weight=1)

        ttk.Label(selector, text="型钢型式：").grid(row=0, column=0, sticky="w", pady=(0, 7))
        self._family_picker = ttk.Combobox(selector, textvariable=self._family, state="readonly", width=43)
        self._family_picker.grid(row=0, column=1, sticky="ew", pady=(0, 7))
        self._family_picker.bind("<<ComboboxSelected>>", self._on_family_changed)

        ttk.Label(selector, text="截面规格：").grid(row=1, column=0, sticky="w", pady=(0, 7))
        self._profile_picker = ttk.Combobox(selector, textvariable=self._profile, state="disabled", width=43)
        self._profile_picker.grid(row=1, column=1, sticky="ew", pady=(0, 7))
        self._profile_picker.bind("<<ComboboxSelected>>", self._refresh_details)

        ttk.Label(selector, text="插入基准：").grid(row=2, column=0, sticky="w")
        self._insertion_picker = ttk.Combobox(selector, textvariable=self._insertion, state="disabled", width=43)
        self._insertion_picker.grid(row=2, column=1, sticky="ew")

        options = ttk.LabelFrame(root, text="2. 放置方式", padding=10)
        options.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(9, 0))
        options.columnconfigure(0, weight=1)

        self._place_radio = ttk.Radiobutton(
            options, text="放置截面（只生成二维截面）",
            variable=self._mode, value=MODE_PLACE, command=self._on_mode_changed,
        )
        self._place_radio.grid(row=0, column=0, sticky="w")

        self._sweep_radio = ttk.Radiobutton(
            options, text="沿路径扫掠（选择一条路径线生成实体）",
            variable=self._mode, value=MODE_SWEEP, command=self._on_mode_changed,
        )
        self._sweep_radio.grid(row=1, column=0, sticky="w")

        self._delete_path_check = ttk.Checkbutton(
            options, text="扫掠完成后删除路径线",
            variable=self._delete_path, state="disabled",
        )
        self._delete_path_check.grid(row=2, column=0, sticky="w", padx=(22, 0), pady=(4, 0))

        ttk.Label(
            options,
            text="放置截面：连续点取插入点。\n"
                 "沿路径扫掠：截面自动放在路径起点并垂直于路径，沿所选路径（直线、折线、"
                 "SmartLine、复杂链、圆弧或样条）生成实体。",
            foreground="#666666", justify="left", wraplength=500,
        ).grid(row=3, column=0, sticky="w", pady=(7, 0))

        ttk.Label(root, textvariable=self._status, foreground="#3f5f7a", justify="left", wraplength=500).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(9, 7)
        )

        details = ttk.LabelFrame(root, text="3. 截面参数", padding=8)
        details.grid(row=4, column=0, columnspan=2, sticky="ew")
        self._detail_tree = ttk.Treeview(details, columns=("name", "value"), show="headings", height=8)
        self._detail_tree.heading("name", text="参数")
        self._detail_tree.heading("value", text="数值")
        self._detail_tree.column("name", width=245, anchor="w")
        self._detail_tree.column("value", width=245, anchor="w")
        self._detail_tree.grid(row=0, column=0, sticky="nsew")

        buttons = ttk.Frame(root)
        buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(9, 0))
        ttk.Button(buttons, text="取消", command=self.destroy).grid(row=0, column=0, padx=(0, 8))
        self._start_button = ttk.Button(buttons, text="开始", command=self._start, state="disabled")
        self._start_button.grid(row=0, column=1)

    def _on_mode_changed(self):
        if self._mode.get() == MODE_SWEEP:
            self._delete_path_check.configure(state="normal")
        else:
            self._delete_path_check.configure(state="disabled")

    def _load_family_choices(self):
        labels = []
        first_available = None
        for identifier, label, available in steel_registry.family_choices():
            display = label if available else "{}（待导入数据）".format(label)
            labels.append(display)
            self._family_id_by_label[display] = identifier
            if available and first_available is None:
                first_available = display
        self._family_picker.configure(values=labels)
        self._family.set(first_available)
        self._on_family_changed()

    def _selected_family_id(self):
        return self._family_id_by_label[self._family.get()]

    def _on_family_changed(self, event=None):
        family_id = self._selected_family_id()
        family = steel_registry.get_family(family_id)
        self._clear_details()
        self._status.set(steel_registry.describe(family_id))
        if not family.available:
            self._profile.set("")
            self._profile_picker.configure(values=(), state="disabled")
            self._insertion.set("")
            self._insertion_picker.configure(values=(), state="disabled")
            self._start_button.configure(state="disabled")
            return

        profiles = steel_registry.profile_names(family_id)
        default_profile = steel_registry.default_profile(family_id)
        self._profile_picker.configure(values=profiles, state="readonly")
        self._profile.set(default_profile if default_profile in profiles else profiles[0])

        insertion_labels = []
        self._insertion_id_by_label = {}
        for identifier, label in steel_registry.insertion_modes(family_id):
            insertion_labels.append(label)
            self._insertion_id_by_label[label] = identifier
        self._insertion_picker.configure(values=insertion_labels, state="readonly")
        self._insertion.set(insertion_labels[0])
        self._start_button.configure(state="normal")
        self._refresh_details()

    def _clear_details(self):
        for item in self._detail_tree.get_children():
            self._detail_tree.delete(item)

    def _refresh_details(self, event=None):
        if not self._profile.get():
            return
        self._clear_details()
        for label, value in steel_registry.detail_rows(self._selected_family_id(), self._profile.get()):
            self._detail_tree.insert("", "end", values=(label, value))

    def _start(self):
        try:
            family_id = self._selected_family_id()
            insertion_mode = self._insertion_id_by_label[self._insertion.get()]
            sweep = self._mode.get() == MODE_SWEEP
            delete_path = bool(self._delete_path.get()) if sweep else False
            steel_tool._log(
                "UI start: family={0} profile={1} mode={2} delete_path={3}".format(
                    family_id, self._profile.get(), self._mode.get(), delete_path
                )
            )
            if sweep:
                steel_tool.start_sweep(
                    family_id, self._profile.get(), insertion_mode, delete_path
                )
            else:
                steel_tool.start_placement(
                    family_id, self._profile.get(), insertion_mode
                )
        except Exception as exc:
            steel_tool._log(
                "UI start failed: {0}\n{1}".format(exc, traceback.format_exc())
            )
            messagebox.showerror(
                "型钢截面生成器",
                "无法启动工具：{0}\n\n详见日志：{1}".format(
                    exc, steel_tool.DEBUG_LOG
                ),
                parent=self,
            )
            return
        if sweep:
            message = (
                "已启动扫掠工具：请在模型中点选一条路径线。\n"
                "截面会放在路径起点并垂直于路径，随后沿路径生成实体。"
            )
        else:
            message = "已启动放置工具：请连续点取插入点放置二维截面，右键 Reset 退出。"
        self._enter_running_state(message)

    def _enter_running_state(self, message):
        for widget in (
                self._family_picker, self._profile_picker, self._insertion_picker,
                self._place_radio, self._sweep_radio, self._delete_path_check):
            try:
                widget.configure(state="disabled")
            except tk.TclError:
                pass
        try:
            self._status.set(message)
            self._start_button.configure(
                text="关闭", state="normal", command=self.destroy
            )
            self.update_idletasks()
        except tk.TclError:
            pass


def show_steel_dialog():
    dialog = SteelSectionDialog()
    dialog.run_bentley_loop()
