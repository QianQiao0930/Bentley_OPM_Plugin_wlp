"""Two-level selector UI for the unified steel-section generator."""

from __future__ import division

import tkinter as tk
import traceback
from tkinter import messagebox, ttk

from bentley_ui import (
    BORDER,
    CARD,
    FIELD,
    INK,
    MUTED,
    UI_FONT,
    UI_FONT_BOLD,
    UI_FONT_SMALL,
    GlassDialog,
    RoundButton,
    SlimScrollbar,
    attach_wheel,
)

from . import steel_registry
from . import steel_tool


MODE_PLACE = "place"
MODE_SWEEP = "sweep"


class SteelSectionDialog(GlassDialog):
    STATE_KEY = "SteelSectionGenerator"

    def __init__(self):
        GlassDialog.__init__(self, title="型钢截面生成器")
        self._family_id_by_label = {}
        self._insertion_id_by_label = {}
        self._family = tk.StringVar()
        self._profile = tk.StringVar()
        self._insertion = tk.StringVar()
        self._status = tk.StringVar()
        self._mode = tk.StringVar(value=MODE_PLACE)
        self._delete_path = tk.BooleanVar(value=False)
        self._rotation = tk.StringVar(value="0")

        self._build()
        self._load_family_choices()
        self.restore_state()
        self.restore_position()

    def _build(self):
        form = self.build_shell(
            "型钢截面生成器",
            "国标型钢截面 · 放置截面 / 沿路径扫掠生成实体",
        )
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="1. 选择型钢", style="Section.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w")

        ttk.Label(form, text="型钢型式", style="GlassMuted.TLabel").grid(
            row=1, column=0, sticky="w", pady=7)
        self._family_picker = ttk.Combobox(
            form, textvariable=self._family, state="readonly", width=26,
            style="Glass.TCombobox")
        self._family_picker.grid(row=1, column=1, columnspan=2, sticky="ew",
                                 padx=(12, 0), pady=7)
        self._family_picker.bind("<<ComboboxSelected>>", self._on_family_changed)

        ttk.Label(form, text="截面规格", style="GlassMuted.TLabel").grid(
            row=2, column=0, sticky="w", pady=7)
        self._profile_picker = ttk.Combobox(
            form, textvariable=self._profile, state="disabled", width=26,
            style="Glass.TCombobox")
        self._profile_picker.grid(row=2, column=1, columnspan=2, sticky="ew",
                                  padx=(12, 0), pady=7)
        self._profile_picker.bind("<<ComboboxSelected>>", self._refresh_details)

        ttk.Label(form, text="插入基准", style="GlassMuted.TLabel").grid(
            row=3, column=0, sticky="w", pady=7)
        self._insertion_picker = ttk.Combobox(
            form, textvariable=self._insertion, state="disabled", width=26,
            style="Glass.TCombobox")
        self._insertion_picker.grid(row=3, column=1, columnspan=2, sticky="ew",
                                    padx=(12, 0), pady=7)

        ttk.Separator(form, orient="horizontal").grid(
            row=4, column=0, columnspan=3, sticky="ew", pady=12)

        ttk.Label(form, text="2. 放置方式", style="Section.TLabel").grid(
            row=5, column=0, columnspan=3, sticky="w", pady=(0, 6))

        self._place_radio = tk.Radiobutton(
            form, text="放置截面（只生成二维截面）", variable=self._mode,
            value=MODE_PLACE, command=self._on_mode_changed, bg=CARD, fg=INK,
            activebackground=CARD, selectcolor=CARD, font=UI_FONT,
            highlightthickness=0, bd=0)
        self._place_radio.grid(row=6, column=0, columnspan=3, sticky="w")

        self._sweep_radio = tk.Radiobutton(
            form, text="沿路径扫掠（选择一条路径线生成实体）", variable=self._mode,
            value=MODE_SWEEP, command=self._on_mode_changed, bg=CARD, fg=INK,
            activebackground=CARD, selectcolor=CARD, font=UI_FONT,
            highlightthickness=0, bd=0)
        self._sweep_radio.grid(row=7, column=0, columnspan=3, sticky="w",
                               pady=(4, 0))

        self._delete_path_check = tk.Checkbutton(
            form, text="扫掠完成后删除路径线", variable=self._delete_path,
            state="disabled", bg=CARD, fg=INK, activebackground=CARD,
            selectcolor=CARD, font=UI_FONT, highlightthickness=0, bd=0)
        self._delete_path_check.grid(row=8, column=0, columnspan=3, sticky="w",
                                     padx=(22, 0), pady=(4, 0))

        rotation_row = tk.Frame(form, bg=CARD)
        rotation_row.grid(row=9, column=0, columnspan=3, sticky="w",
                          padx=(22, 0), pady=(6, 0))
        tk.Label(rotation_row, text="截面旋转角（顺时针）", bg=CARD, fg=INK,
                 font=UI_FONT).pack(side="left")
        self._rotation_entry = tk.Entry(
            rotation_row, textvariable=self._rotation, width=8, font=UI_FONT,
            fg=INK, bg=FIELD, relief="flat", highlightthickness=1,
            highlightbackground=BORDER, highlightcolor="#9FB4CC",
            insertbackground=INK, justify="center", state="disabled")
        self._rotation_entry.pack(side="left", padx=(10, 0), ipady=3)
        tk.Label(rotation_row, text="°", bg=CARD, fg=MUTED,
                 font=UI_FONT_SMALL).pack(side="left", padx=(6, 0))

        tk.Label(
            form,
            text="放置截面：连续点取插入点。\n"
                 "沿路径扫掠：截面自动放在路径起点并垂直于路径，沿所选路径（直线、折线、"
                 "SmartLine、复杂链、圆弧或样条）生成实体。",
            bg=CARD, fg=MUTED, font=UI_FONT_SMALL, justify="left", wraplength=290,
        ).grid(row=10, column=0, columnspan=3, sticky="w", pady=(8, 0),
               padx=(22, 0))

        ttk.Separator(form, orient="horizontal").grid(
            row=11, column=0, columnspan=3, sticky="ew", pady=12)

        ttk.Label(form, text="3. 截面参数", style="Section.TLabel").grid(
            row=12, column=0, columnspan=3, sticky="w", pady=(0, 6))

        tree_frame = tk.Frame(form, bg=CARD, highlightbackground=BORDER,
                              highlightthickness=1)
        tree_frame.grid(row=13, column=0, columnspan=3, sticky="ew")
        self._detail_tree = ttk.Treeview(
            tree_frame, columns=("name", "value"), show="headings", height=6,
            style="Glass.Treeview")
        self._detail_tree.heading("name", text="参数")
        self._detail_tree.heading("value", text="数值")
        self._detail_tree.column("name", width=130, anchor="w")
        self._detail_tree.column("value", width=130, anchor="w")
        scroll = SlimScrollbar(tree_frame, command=self._detail_tree.yview)
        self._detail_tree.configure(yscrollcommand=scroll.set)
        attach_wheel(self._detail_tree)
        self._detail_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.make_status_chip(form, self._status).grid(
            row=14, column=0, columnspan=3, sticky="ew", pady=(12, 0))

        button_bar = tk.Frame(form, bg=CARD)
        button_bar.grid(row=15, column=0, columnspan=3, sticky="ew", pady=(14, 0))
        self._start_button = RoundButton(
            button_bar, "开始", self._start, primary=True, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self._cancel_button = RoundButton(
            button_bar, "取消", self.destroy, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self._end_button = RoundButton(
            button_bar, "结束工具", self._end_tool, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self._end_button.pack(side="left")
        self._start_button.pack(side="right")
        self._cancel_button.pack(side="right", padx=(0, 8))
        self._start_button.set_enabled(False)

    def restore_state(self):
        state = self.ui_state
        family_label = state.get("family_label")
        if family_label in self._family_id_by_label:
            self._family.set(family_label)
            self._on_family_changed()
        profile = state.get("profile")
        if profile and profile in self._profile_picker["values"]:
            self._profile.set(profile)
        insertion = state.get("insertion")
        if insertion and insertion in self._insertion_picker["values"]:
            self._insertion.set(insertion)
        mode = state.get("mode")
        if mode in (MODE_PLACE, MODE_SWEEP):
            self._mode.set(mode)
        if isinstance(state.get("delete_path"), bool):
            self._delete_path.set(state.get("delete_path"))
        rotation = state.get("rotation")
        if isinstance(rotation, str) and rotation.strip():
            self._rotation.set(rotation)
        self._on_mode_changed()
        self._refresh_details()

    def persist_state(self, state):
        try:
            state["family_label"] = self._family.get()
            state["profile"] = self._profile.get()
            state["insertion"] = self._insertion.get()
            state["mode"] = self._mode.get()
            state["delete_path"] = bool(self._delete_path.get())
            state["rotation"] = self._rotation.get()
        except tk.TclError:
            pass

    def _on_mode_changed(self):
        sweep = self._mode.get() == MODE_SWEEP
        self._delete_path_check.configure(state="normal" if sweep else "disabled")
        try:
            self._rotation_entry.configure(state="normal" if sweep else "disabled")
        except tk.TclError:
            pass
        self._update_start_button_label()

    def _update_start_button_label(self):
        if self._mode.get() == MODE_SWEEP:
            self._start_button.set_text("选取路径")
        else:
            self._start_button.set_text("放置")

    def _end_tool(self):
        ended = steel_tool.end_active_tool()
        try:
            if ended:
                self._status.set(
                    "已结束当前工具。可改选型钢后再次点击“放置”，或点击“选取路径”。"
                )
            else:
                self._status.set("当前没有正在运行的工具。")
            self.update_idletasks()
        except tk.TclError:
            pass

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
            self._start_button.set_enabled(False)
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
        self._start_button.set_enabled(True)
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

    def _get_rotation_deg(self):
        text = (self._rotation.get() or "").strip()
        if not text:
            return 0.0
        try:
            return float(text)
        except ValueError:
            raise ValueError("截面旋转角必须是数字（单位：度）。")

    def _start(self):
        try:
            family_id = self._selected_family_id()
            insertion_mode = self._insertion_id_by_label[self._insertion.get()]
            sweep = self._mode.get() == MODE_SWEEP
            delete_path = bool(self._delete_path.get()) if sweep else False
            rotation_deg = self._get_rotation_deg() if sweep else 0.0
            steel_tool._log(
                "UI start: family={0} profile={1} mode={2} delete_path={3} "
                "rotation={4}".format(
                    family_id, self._profile.get(), self._mode.get(), delete_path,
                    rotation_deg,
                )
            )
            if sweep:
                steel_tool.start_sweep(
                    family_id, self._profile.get(), insertion_mode, delete_path,
                    rotation_deg,
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
                "已启动扫掠工具：请在模型中点选路径线。"
                "可修改型钢后再次点击“选取路径”，“结束工具”可停止。"
            )
        else:
            message = (
                "已启动放置工具：请在模型中连续点取插入点。"
                "可修改型钢后再次点击“放置”，“结束工具”可停止。"
            )
        try:
            self._status.set(message)
            self.update_idletasks()
        except tk.TclError:
            pass


def show_steel_dialog():
    dialog = SteelSectionDialog()
    dialog.run_bentley_loop()
