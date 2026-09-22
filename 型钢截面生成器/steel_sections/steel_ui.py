"""Two-level selector UI for the unified steel-section generator."""

from __future__ import division

import time
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
        self._last_tool_status_revision = steel_tool.status_snapshot()[0]
        self._status_poll_job = None
        self._family_id_by_label = {}
        self._insertion_id_by_label = {}
        self._family = tk.StringVar()
        self._profile = tk.StringVar()
        self._insertion = tk.StringVar()
        self._status = tk.StringVar()
        self._mode = tk.StringVar(value=MODE_PLACE)
        self._delete_path = tk.BooleanVar(value=False)
        self._rotation = tk.StringVar(value="0")

        # 扫掠"预览 + 确认"状态。原生回调（选路径 / 参数变化）只写这些普通
        # Python 属性，所有 Tk 刷新交给常驻定时器 _poll_ui，避免重入崩溃。
        self.preview_handle = None
        self.preview_result = None
        self.path_handle = None
        self._pending_path_handle = None
        self.confirmed = False
        self._params = {}
        self._regen_deadline = None
        self._pending_message = None
        self._pending_is_error = False
        self._cleanup_requested = False
        self._cancel_requested = False

        self._build()
        self._load_family_choices()
        self.restore_state()
        self.restore_position()
        self._poll_ui()

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
        self._profile_picker.bind("<<ComboboxSelected>>", self._on_profile_changed)

        ttk.Label(form, text="插入基准", style="GlassMuted.TLabel").grid(
            row=3, column=0, sticky="w", pady=7)
        self._insertion_picker = ttk.Combobox(
            form, textvariable=self._insertion, state="disabled", width=26,
            style="Glass.TCombobox")
        self._insertion_picker.grid(row=3, column=1, columnspan=2, sticky="ew",
                                    padx=(12, 0), pady=7)
        self._insertion_picker.bind("<<ComboboxSelected>>", self._on_insertion_changed)

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
        self._rotation.trace_add("write", self._on_rotation_changed)

        tk.Label(
            form,
            text="放置截面：连续点取插入点。\n"
                 "沿路径扫掠：点选路径后仅生成预览，改型钢 / 规格 / 旋转角会"
                 "实时重建预览，点【确定】才保留实体并计入统计，右键放弃预览。",
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

        self._status_chip = self.make_status_chip(form, self._status)
        self._status_chip.grid(
            row=14, column=0, columnspan=3, sticky="ew", pady=(12, 0))

        button_bar = tk.Frame(form, bg=CARD)
        button_bar.grid(row=15, column=0, columnspan=3, sticky="ew", pady=(14, 0))
        self._start_button = RoundButton(
            button_bar, "开始", self._start, primary=True, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self._confirm_button = RoundButton(
            button_bar, "确定", self.confirm_tool, primary=True, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self._cancel_button = RoundButton(
            button_bar, "取消", self.cancel_tool, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self._end_button = RoundButton(
            button_bar, "结束工具", self._end_tool, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self._end_button.pack(side="left")
        self._start_button.pack(side="right")
        self._cancel_button.pack(side="right", padx=(0, 8))
        self._confirm_button.pack(side="right", padx=(0, 8))
        self._start_button.set_enabled(False)
        self._confirm_button.set_enabled(False)

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
        self._update_confirm_button()

    def _update_start_button_label(self):
        if self._mode.get() == MODE_SWEEP:
            self._start_button.set_text("选取路径")
        else:
            self._start_button.set_text("放置")

    def _update_confirm_button(self):
        """【确定】只在存在扫掠预览时可用。"""
        try:
            self._confirm_button.set_enabled(self.preview_handle is not None)
        except (AttributeError, tk.TclError):
            pass

    def _sync_params(self):
        """把当前 Tk 选项缓存成普通 Python 字典，供原生回调安全读取。"""
        try:
            family_id = self._family_id_by_label.get(self._family.get())
            insertion = self._insertion_id_by_label.get(self._insertion.get())
            rotation_text = (self._rotation.get() or "").strip()
            try:
                rotation = float(rotation_text) if rotation_text else 0.0
            except ValueError:
                rotation = 0.0
            self._params = {
                "family_id": family_id,
                "profile": self._profile.get(),
                "insertion": insertion,
                "rotation_deg": rotation,
                "delete_path": bool(self._delete_path.get()),
            }
        except tk.TclError:
            pass

    def _on_profile_changed(self, event=None):
        self._refresh_details()
        self._sync_params()
        self._schedule_regeneration()

    def _on_insertion_changed(self, event=None):
        self._sync_params()
        self._schedule_regeneration()

    def _on_rotation_changed(self, *_args):
        self._sync_params()
        self._schedule_regeneration()

    def _schedule_regeneration(self, delay_ms=150):
        """参数变化后防抖重建预览（没有已选路径时什么都不做）。"""
        if self.path_handle is None:
            return
        self._regen_deadline = time.monotonic() + delay_ms / 1000.0

    def note_path(self, handle):
        """悬停到合规路径时记录稳定句柄（原生回调，仅写普通状态）。"""
        self._pending_path_handle = handle

    # -- 预览：可能由原生回调调用，只做 Bentley 建模，不碰 Tcl ----------------

    def regenerate(self, path_element=None):
        self._regen_deadline = None
        handle = self._pending_path_handle
        self._pending_path_handle = None
        if handle is None:
            handle = path_element
        if handle is None:
            handle = self.path_handle
        if handle is None:
            return None
        self.path_handle = handle
        if not self._params.get("family_id") or not self._params.get("profile"):
            self._sync_params()
        try:
            handle, result, _deleted = steel_tool.build_preview(
                self._params["family_id"],
                self._params["profile"],
                self._params["insertion"],
                self._params["rotation_deg"],
                self.path_handle,
                self.preview_handle,
            )
        except Exception as error:
            steel_tool._log_exception("sweep preview failed")
            self._pending_message = "扫掠预览失败：{0}".format(error)
            self._pending_is_error = True
            return None
        self.preview_handle = handle
        self.preview_result = result
        self._pending_message = (
            "预览已更新：{label} {profile}，长度 {length:.0f} mm，"
            "旋转 {rot:.1f}°，已附加统计项 {items} 条。"
            "改型钢 / 规格 / 旋转角会实时重建；点【确定】保留，右键放弃。".format(
                label=result["family_label"], profile=result["profile"],
                length=result["length_mm"], rot=result["rotation_deg"],
                items=result["attached_items"])
        )
        self._pending_is_error = False
        return result

    def discard_preview(self):
        handle = self.preview_handle
        self.preview_handle = None
        self.preview_result = None
        if handle is not None:
            steel_tool._delete_element(handle)
        self._update_confirm_button()

    def _on_tool_cleanup(self):
        """工具退出后的 UI 复位：未确认则丢弃预览。"""
        if self.confirmed:
            # 已确认：实体保留在模型中，只解除跟踪，绝不能删除。
            self.preview_handle = None
        else:
            self.discard_preview()
        self.path_handle = None
        self.preview_result = None
        self._update_confirm_button()

    def _handle_cancel_request(self):
        """右键 Reset：放弃预览并结束工具，但保留面板。"""
        self.confirmed = False
        self.discard_preview()
        self.path_handle = None
        steel_tool.end_active_tool()
        try:
            self._status.set("已放弃预览。可重新选取路径。")
            self._set_status_appearance(False)
        except tk.TclError:
            pass

    def request_cancel(self):
        self._cancel_requested = True

    def request_cleanup(self):
        self._cleanup_requested = True

    def confirm_tool(self):
        """【确定】：保留预览实体（已附加统计项）并结束扫掠工具。"""
        if self.preview_handle is None:
            return
        self.confirmed = True
        self._sync_params()
        if self._params.get("delete_path") and self.path_handle is not None:
            steel_tool._delete_element(self.path_handle)
        steel_tool.end_active_tool()
        # 已确认：实体保留在模型中，解除预览跟踪以免后续误删。
        self.preview_handle = None
        self.path_handle = None
        self.preview_result = None
        self._update_confirm_button()
        try:
            self._status.set("已确认并保留扫掠实体（已计入统计）。可继续选取路径。")
            self._set_status_appearance(False)
        except tk.TclError:
            pass

    def cancel_tool(self):
        """【取消】：放弃预览、结束工具并关闭面板。"""
        self.confirmed = False
        self.discard_preview()
        self.destroy()

    def _end_tool(self):
        ended = steel_tool.end_active_tool()
        try:
            if ended:
                self._status.set(
                    "已结束当前工具。可改选型钢后再次点击“放置”，或点击“选取路径”。"
                )
            else:
                self._status.set("当前没有正在运行的工具。")
            self._set_status_appearance(False)
            self.update_idletasks()
        except tk.TclError:
            pass

    def _set_status_appearance(self, is_error=False):
        try:
            children = self._status_chip.winfo_children()
            if children:
                children[0].configure(fg="#B42318" if is_error else "#1f5f99")
        except (AttributeError, tk.TclError):
            pass

    def _poll_ui(self):
        """常驻 Tk 定时器：处理原生回调排队的预览 / 取消 / 清理与状态刷新。"""
        self._status_poll_job = None
        try:
            if self._cleanup_requested:
                self._cleanup_requested = False
                self._on_tool_cleanup()
            if self._cancel_requested:
                self._cancel_requested = False
                self._handle_cancel_request()
            if (self._regen_deadline is not None
                    and time.monotonic() >= self._regen_deadline):
                self.regenerate()
            revision, message, is_error = steel_tool.status_snapshot()
            if revision != self._last_tool_status_revision:
                self._last_tool_status_revision = revision
                self._status.set(message)
                self._set_status_appearance(is_error)
            if self._pending_message is not None:
                message = self._pending_message
                is_error = self._pending_is_error
                self._pending_message = None
                self._pending_is_error = False
                self._status.set(message)
                self._set_status_appearance(is_error)
            self._update_confirm_button()
            self._status_poll_job = self.after(100, self._poll_ui)
        except tk.TclError:
            self._status_poll_job = None

    def destroy(self):
        """Close the dialog and never leave a Bentley tool running behind it."""
        if self._status_poll_job is not None:
            try:
                self.after_cancel(self._status_poll_job)
            except tk.TclError:
                pass
            self._status_poll_job = None
        self.confirmed = False
        self.discard_preview()
        steel_tool.end_active_tool()
        GlassDialog.destroy(self)

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
        self._set_status_appearance(False)
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
        self._sync_params()
        self._schedule_regeneration()

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
            rotation_deg = self._get_rotation_deg() if sweep else 0.0
            steel_tool._log(
                "UI start: family={0} profile={1} mode={2} rotation={3}".format(
                    family_id, self._profile.get(), self._mode.get(),
                    rotation_deg,
                )
            )
            if sweep:
                # 进入预览模式前，先结束可能存在的旧工具并清空旧预览。
                steel_tool.end_active_tool()
                self.confirmed = False
                self.path_handle = None
                self._pending_path_handle = None
                self._cleanup_requested = False
                self._cancel_requested = False
                self.discard_preview()
                self._sync_params()
                steel_tool.start_sweep(self)
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
                "已启动扫掠预览：请点选一条路径线。改型钢 / 规格 / 旋转角会实时"
                "重建预览，点【确定】保留实体并计入统计，右键放弃。"
            )
        else:
            message = (
                "已启动放置工具：请在模型中连续点取插入点。"
                "可修改型钢后再次点击“放置”，“结束工具”可停止。"
            )
        try:
            self._status.set(message)
            self._set_status_appearance(False)
            self.update_idletasks()
        except tk.TclError:
            pass


def show_steel_dialog():
    dialog = SteelSectionDialog()
    dialog.run_bentley_loop()
