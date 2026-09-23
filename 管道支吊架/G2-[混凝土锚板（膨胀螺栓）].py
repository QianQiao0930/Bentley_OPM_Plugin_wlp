# -*- coding: utf-8 -*-
"""G2 混凝土锚板 + 膨胀锚栓放置工具。

在三维 DGN 模型中点取**混凝土表面**上锚板背面的中心点，生成一块正方形锚板与
四根膨胀锚栓（表 1 子项 A~D）：

    * 锚板：正方形 (S+100)×(S+100)、厚 T，四角四个 φG 螺栓孔（间距 S）。
    * 锚栓：埋入端膨胀套管 + 螺杆 + 垫圈 + 六角螺母，全部由最简单的拉伸 / 圆柱
      构成，不做布尔融合（允许实体重合），只保证外形可辨认。
    * 锚栓朝向沿所选点的混凝土外法向。安装面可选**竖直墙面**（螺栓水平）或
      **水平楼板顶面 / 底面**（楼板水平、螺栓朝下 / 朝上）；「朝向」在各自平面内
      绕外法向旋转。

建模逻辑全部在 ``混凝土锚板.py`` 中，不含任何界面依赖，其它插件可直接
``import 混凝土锚板`` 调用：

    import 混凝土锚板 as anchor
    cell, result = anchor.draw_anchor_plate(placement_point, options)

本文件只负责 **Tkinter** 面板与交互工具，外观沿用仓库共享的 ``bentley_ui``
主题（卡片 / 圆角按钮），并自动记住上次窗口位置与子项 / 间距 / 朝向。
"""

from __future__ import division

import os
import sys
import tkinter as tk
import traceback
from tkinter import ttk

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *


HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
# 仓库根提供共享 UI 工具箱 bentley_ui；建模库在 模块/公共/。
_COMMON_DIR = os.path.join(HERE, '模块', '公共')
for _path in (REPO_ROOT, _COMMON_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

# 共享 UI 工具箱在导入前强制重读一次，避免拿到 MicroStation 缓存的旧模块。
import importlib  # noqa: E402
import importlib.util  # noqa: E402
try:
    import bentley_ui.glass as _glass_module  # noqa: F401
    import bentley_ui as _bentley_ui_module  # noqa: F401
    importlib.reload(_glass_module)
    importlib.reload(_bentley_ui_module)
except Exception:
    pass


def _load_module(name, file_path):
    """按文件路径加载模块；已加载则原地重读，规避 MicroStation 的模块缓存。"""
    if name in sys.modules:
        try:
            return importlib.reload(sys.modules[name])
        except Exception:
            pass
    spec = importlib.util.spec_from_file_location(name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


from bentley_ui import (  # noqa: E402
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
)

import 支吊架公共库 as psb  # noqa: E402  写入统一统计 / 清单

# 建模库按文件路径强制重读：避免拿到 MicroStation 缓存里的旧版本
# （旧版本没有 MOUNT_OPTIONS 等新接口）。
geometry = _load_module('混凝土锚板', os.path.join(_COMMON_DIR, '混凝土锚板.py'))


DEBUG_LOG = os.path.join(
    HERE, '模块', '日志', 'G2-混凝土锚板_debug_log.txt')
try:
    os.makedirs(os.path.dirname(DEBUG_LOG), exist_ok=True)
except Exception:
    pass

UI_TITLE = 'G2-[混凝土锚板（膨胀螺栓）]'
SUPPORT_TYPE = 'G2-[混凝土锚板（膨胀螺栓）]'
SUPPORT_CODE = 'G2_ANCHOR_PLATE'
DEFAULT_SUBTYPE = 'A'
DEFAULT_HEADING = 0.0

# 选项变化后延迟重建的毫秒数：连点几下只重建一次。
REGENERATE_DELAY_MS = 150        # 下拉框的防抖
TEXT_REGENERATE_DELAY_MS = 750   # 文本框的防抖，避免打到一半就重建


def _log(message):
    try:
        with open(DEBUG_LOG, 'a', encoding='utf-8') as log_file:
            log_file.write(str(message) + '\n')
    except Exception:
        pass


def _log_exception(title):
    _log('%s: %s' % (title, traceback.format_exc()))


def _copy_dpoint(point):
    return DPoint3d.From(point.x, point.y, point.z)


def _subtype_label(subtype):
    table = geometry.ANCHOR_TABLE[subtype]
    return ('%s  |  M%.0f×%.0f  |  板厚 %.0f  |  孔 φ%.0f'
            % (subtype, table['bolt_dia'], table['length'],
               table['plate_t'], table['hole_dia']))


def _attach_support_items(cell, result):
    """把锚板整组写入共享支吊架库（整组记录 + 构件记录），供统一统计 / 清单。"""
    subtype = result.get('subtype', DEFAULT_SUBTYPE)
    plate_spec = '%.0f×%.0f×%.0f（S=%.0f，4-φ%.0f）' % (
        float(result.get('plate_side', 0.0)), float(result.get('plate_side', 0.0)),
        float(result.get('plate_t', 0.0)), float(result.get('spacing', 0.0)),
        float(result.get('hole_dia', 0.0)))
    bolt_spec = 'M%.0f×%.0f' % (
        float(result.get('bolt_dia', 0.0)), float(result.get('bolt_length', 0.0)))
    assembly_spec = 'G2-%s：锚板 %s，膨胀锚栓 %s ×4' % (
        subtype, plate_spec, bolt_spec)
    components = [
        {'code': 'AnchorPlate', 'name': '锚板', 'specification': plate_spec,
         'length': float(result.get('plate_t', 0.0)), 'quantity': 1, 'unit': '块'},
        {'code': 'AnchorBolt', 'name': '膨胀锚栓', 'specification': bolt_spec,
         'length': float(result.get('bolt_length', 0.0)), 'quantity': 4, 'unit': '套'},
    ]
    try:
        return psb.attach_components(
            cell, support_type=SUPPORT_TYPE, support_code=SUPPORT_CODE,
            assembly_tag='G2-%s' % subtype, assembly_spec=assembly_spec,
            components=components)
    except Exception:
        _log_exception('attach support items failed')
        return 0


# ---------------------------------------------------------------------------
# 设置面板（Tkinter）
# ---------------------------------------------------------------------------


class _AnchorPlateDialog(GlassDialog):
    """子项 / 间距 / 朝向选择，预览 / 确定 / 取消面板。"""

    STATE_KEY = 'G2AnchorPlate'

    def __init__(self):
        GlassDialog.__init__(self, title=UI_TITLE)
        self.placement_point = None
        self.preview_handle = None
        self.preview_result = None
        self.confirmed = False
        self._regen_job = None

        self._subtype = tk.StringVar()
        self._spacing = tk.StringVar(value='75')
        self._heading = tk.StringVar(value='%.0f' % DEFAULT_HEADING)
        self._mount = tk.StringVar(value=geometry.MOUNT_OPTIONS[0][1])
        self._spec = tk.StringVar()
        self._preview_info = tk.StringVar(value='预览：—')
        self._status = tk.StringVar()
        self._plate_text = tk.StringVar(value='—')
        self._bolt_text = tk.StringVar(value='—')
        self._subtype_by_label = {}
        self._mount_by_label = {}

        self._build()
        self.restore_state()
        self.restore_position()

        # 关闭窗口时按"取消"处理：丢弃预览并结束工具。
        self.protocol('WM_DELETE_WINDOW', self.cancel_tool)
        _log('panel built rev=anchor-plate-tk file=%s'
             % os.path.abspath(__file__))

    # -- 构建 --------------------------------------------------------------

    def _build(self):
        form = self.build_shell(
            UI_TITLE, '点取混凝土表面锚板中心 · 子项 / 间距 / 朝向可调，自动预览')
        form.columnconfigure(1, weight=1)

        tk.Label(
            form,
            text='在模型中点取混凝土表面上锚板背面的中心点；锚栓沿「安装面」的'
                 '外法向伸入（竖直墙面＝水平方向，水平楼板＝竖直方向）。点取后'
                 '可改子项 / 间距 S / 安装面 / 朝向，预览会自动重建；点【确定】'
                 '保留，点【取消】或右键放弃。',
            bg=CARD, fg=MUTED, font=UI_FONT_SMALL, justify='left',
            wraplength=430,
        ).grid(row=0, column=0, columnspan=2, sticky='w')

        ttk.Label(form, text='锚栓规格', style='Section.TLabel').grid(
            row=1, column=0, columnspan=2, sticky='w', pady=(10, 4))

        ttk.Label(form, text='子项', style='GlassMuted.TLabel').grid(
            row=2, column=0, sticky='w', pady=6)
        labels = []
        for key in sorted(geometry.ANCHOR_TABLE):
            label = _subtype_label(key)
            labels.append(label)
            self._subtype_by_label[label] = key
        self._subtype_combo = ttk.Combobox(
            form, textvariable=self._subtype, state='readonly', width=30,
            style='Glass.TCombobox', values=labels)
        self._subtype_combo.grid(row=2, column=1, sticky='ew', padx=(10, 0),
                                 pady=6)
        self._subtype_combo.bind('<<ComboboxSelected>>', self.on_subtype_changed)
        default_label = next(
            (label for label, key in self._subtype_by_label.items()
             if key == DEFAULT_SUBTYPE), labels[0])
        self._subtype.set(default_label)

        ttk.Label(form, text='锚板', style='GlassMuted.TLabel').grid(
            row=3, column=0, sticky='w', pady=6)
        tk.Label(form, textvariable=self._plate_text, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w', justify='left',
                 wraplength=330).grid(row=3, column=1, sticky='w',
                                      padx=(10, 0), pady=6)

        ttk.Label(form, text='锚栓', style='GlassMuted.TLabel').grid(
            row=4, column=0, sticky='w', pady=6)
        tk.Label(form, textvariable=self._bolt_text, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, anchor='w', justify='left',
                 wraplength=330).grid(row=4, column=1, sticky='w',
                                      padx=(10, 0), pady=6)

        ttk.Separator(form, orient='horizontal').grid(
            row=5, column=0, columnspan=2, sticky='ew', pady=10)

        ttk.Label(form, text='布置参数', style='Section.TLabel').grid(
            row=6, column=0, columnspan=2, sticky='w', pady=(0, 4))

        ttk.Label(form, text='间距 S', style='GlassMuted.TLabel').grid(
            row=7, column=0, sticky='w', pady=6)
        spacing_row = tk.Frame(form, bg=CARD)
        spacing_row.grid(row=7, column=1, sticky='w', padx=(10, 0), pady=6)
        self._spacing_entry = self._entry(spacing_row, self._spacing, 9)
        tk.Label(spacing_row, text='mm　孔中心距，不得小于该子项 MIN.S',
                 bg=CARD, fg=MUTED, font=UI_FONT_SMALL).pack(side='left',
                                                             padx=(8, 0))

        ttk.Label(form, text='安装面', style='GlassMuted.TLabel').grid(
            row=8, column=0, sticky='w', pady=6)
        mount_labels = []
        for key, label in geometry.MOUNT_OPTIONS:
            mount_labels.append(label)
            self._mount_by_label[label] = key
        self._mount_combo = ttk.Combobox(
            form, textvariable=self._mount, state='readonly', width=30,
            style='Glass.TCombobox', values=mount_labels)
        self._mount_combo.grid(row=8, column=1, sticky='w', padx=(10, 0),
                               pady=6)
        self._mount_combo.bind('<<ComboboxSelected>>', self.on_options_changed)

        ttk.Label(form, text='朝向', style='GlassMuted.TLabel').grid(
            row=9, column=0, sticky='w', pady=6)
        heading_row = tk.Frame(form, bg=CARD)
        heading_row.grid(row=9, column=1, sticky='w', padx=(10, 0), pady=6)
        self._heading_entry = self._entry(heading_row, self._heading, 9)
        tk.Label(heading_row, text='°　墙面为绕 Z 方位角，楼板为绕竖轴转角',
                 bg=CARD, fg=MUTED, font=UI_FONT_SMALL).pack(side='left',
                                                             padx=(8, 0))

        ttk.Separator(form, orient='horizontal').grid(
            row=10, column=0, columnspan=2, sticky='ew', pady=10)

        tk.Label(form, textvariable=self._spec, bg=CARD, fg=MUTED,
                 font=UI_FONT_SMALL, justify='left', anchor='w',
                 wraplength=430).grid(row=11, column=0, columnspan=2, sticky='w')
        tk.Label(form, textvariable=self._preview_info, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD, justify='left', anchor='w',
                 wraplength=430).grid(row=12, column=0, columnspan=2, sticky='w',
                                      pady=(4, 0))

        self.make_status_chip(form, self._status, wraplength=430).grid(
            row=13, column=0, columnspan=2, sticky='ew', pady=(10, 0))

        buttons = tk.Frame(form, bg=CARD)
        buttons.grid(row=14, column=0, columnspan=2, sticky='ew', pady=(12, 0))
        self.confirm_button = RoundButton(
            buttons, '确定', self.confirm_tool, primary=True, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self.cancel_button = RoundButton(
            buttons, '取消', self.cancel_tool, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self.confirm_button.pack(side='right')
        self.cancel_button.pack(side='right', padx=(0, 8))

        self._spacing.trace_add('write', self.on_text_changed)
        self._heading.trace_add('write', self.on_text_changed)

    def _entry(self, parent, variable, width):
        entry = tk.Entry(
            parent, textvariable=variable, width=width, font=UI_FONT, fg=INK,
            bg=FIELD, relief='flat', highlightthickness=1,
            highlightbackground=BORDER, highlightcolor='#9FB4CC',
            insertbackground=INK, justify='center')
        entry.pack(side='left', ipady=3)
        return entry

    # -- 记忆 --------------------------------------------------------------

    def restore_state(self):
        state = self.ui_state
        subtype = state.get('subtype')
        if subtype in geometry.ANCHOR_TABLE:
            for label, key in self._subtype_by_label.items():
                if key == subtype:
                    self._subtype.set(label)
                    break
        spacing = state.get('spacing')
        if isinstance(spacing, str) and spacing.strip():
            self._spacing.set(spacing)
        else:
            table = geometry.ANCHOR_TABLE.get(self.current_subtype())
            if table is not None:
                self._spacing.set('%.0f' % table['min_spacing'])
        heading = state.get('heading')
        if isinstance(heading, str) and heading.strip():
            self._heading.set(heading)
        mount = state.get('mount')
        if mount in geometry.MOUNT_KEYS:
            for label, key in self._mount_by_label.items():
                if key == mount:
                    self._mount.set(label)
                    break
        self.refresh_spec()

    def persist_state(self, state):
        try:
            state['subtype'] = self.current_subtype()
            state['spacing'] = self._spacing.get()
            state['heading'] = self._heading.get()
            state['mount'] = self.current_mount()
        except Exception:
            pass

    # -- 选项 --------------------------------------------------------------

    def current_subtype(self):
        return self._subtype_by_label.get(self._subtype.get(), DEFAULT_SUBTYPE)

    def current_mount(self):
        return self._mount_by_label.get(self._mount.get(), 'wall')

    def current_options(self):
        subtype = self.current_subtype()
        if subtype not in geometry.ANCHOR_TABLE:
            raise ValueError('未知子项：%s。' % subtype)
        try:
            spacing = float((self._spacing.get() or '').strip())
        except (TypeError, ValueError):
            raise ValueError('间距 S 必须是数字（mm）。')
        try:
            heading = float((self._heading.get() or '').strip())
        except (TypeError, ValueError):
            raise ValueError('朝向必须是数字（度）。')
        return {'subtype': subtype, 'spacing': spacing,
                'heading_deg': heading, 'mount': self.current_mount()}

    def set_status(self, message, is_error=False):
        try:
            self._status.set(message)
            self.update_idletasks()
        except tk.TclError:
            pass

    def set_result(self, result):
        self._preview_info.set(
            '预览：%s 子项，锚板 %.0f×%.0f×%.0f，4-φ%.0f 孔（S=%.0f），'
            'M%.0f×%.0f 锚栓 ×%d，有效埋深 %.0f mm，单元含 %d 个子元素。' % (
                result['subtype'], result['plate_side'], result['plate_side'],
                result['plate_t'], result['hole_dia'], result['spacing'],
                result['bolt_dia'], result['bolt_length'], result['bolt_count'],
                result['embedment_actual'], result['child_count'],
            )
        )

    def refresh_spec(self):
        subtype = self.current_subtype()
        table = geometry.ANCHOR_TABLE.get(subtype)
        if table is None:
            self._spec.set('子项有误。')
            return
        self._plate_text.set('%.0f×%.0f×%.0f（板厚 T=%.0f）' % (
            table['min_spacing'] + 2.0 * geometry.PLATE_MARGIN,
            table['min_spacing'] + 2.0 * geometry.PLATE_MARGIN,
            table['plate_t'], table['plate_t']))
        self._bolt_text.set('M%.0f×%.0f 膨胀锚栓，孔径 φ%.0f' % (
            table['bolt_dia'], table['length'], table['hole_dia']))
        try:
            self._spec.set(geometry.describe_spec(self.current_options()))
        except (ValueError, RuntimeError) as error:
            self._spec.set('参数有误：%s' % error)

    def _set_busy(self, busy):
        for combo in (self._subtype_combo, self._mount_combo):
            try:
                combo.configure(state='disabled' if busy else 'readonly')
            except tk.TclError:
                pass
        for entry in (self._spacing_entry, self._heading_entry):
            try:
                entry.configure(state='disabled' if busy else 'normal')
            except tk.TclError:
                pass
        for button in (self.confirm_button, self.cancel_button):
            button.set_enabled(not busy)
        try:
            self.update_idletasks()
        except tk.TclError:
            pass

    def on_subtype_changed(self, event=None):
        """切换子项时把间距 S 重置为该子项 MIN.S，保证默认参数合法。"""
        table = geometry.ANCHOR_TABLE.get(self.current_subtype())
        if table is not None:
            self._spacing.set('%.0f' % table['min_spacing'])
        self.on_options_changed()

    def on_options_changed(self, event=None):
        self.refresh_spec()
        self._schedule_regeneration(REGENERATE_DELAY_MS)

    def on_text_changed(self, *_args):
        self.refresh_spec()
        self._schedule_regeneration(TEXT_REGENERATE_DELAY_MS)

    def _schedule_regeneration(self, delay):
        self._cancel_pending_regeneration()
        if self.placement_point is None:
            return
        try:
            self._regen_job = self.after(delay, self._run_pending_regeneration)
        except tk.TclError:
            self._regen_job = None

    def _cancel_pending_regeneration(self):
        if self._regen_job is not None:
            try:
                self.after_cancel(self._regen_job)
            except Exception:
                pass
            self._regen_job = None

    def _run_pending_regeneration(self):
        self._regen_job = None
        self.regenerate()

    # -- 预览 --------------------------------------------------------------

    def regenerate(self, placement_point=None):
        """按当前选项重建预览：先建新的一版，成功后再删掉旧的。"""
        self._cancel_pending_regeneration()
        if placement_point is not None:
            self.placement_point = _copy_dpoint(placement_point)
        if self.placement_point is None:
            return None

        try:
            options = self.current_options()
            geometry.resolve_options(options)
        except (ValueError, RuntimeError) as error:
            self.set_status('参数有误：%s' % error, True)
            return None

        self._set_busy(True)
        self.set_status('正在生成锚板预览，请稍候……')
        try:
            handle, result, deleted = geometry.replace_anchor_plate(
                self.placement_point, options, self.preview_handle)
        except Exception as error:
            message = '锚板生成失败：%s' % error
            self.set_status(message, True)
            NotificationManager.OutputPrompt(message)
            print(message)
            _log_exception('preview failed')
            return None
        finally:
            self._set_busy(False)

        self.preview_handle = handle
        self.preview_result = result
        _attach_support_items(handle, result)
        self.set_result(result)
        message = (
            '预览已更新：%s 子项，锚板 %.0f×%.0f×%.0f，M%.0f×%.0f 锚栓 ×4，'
            '单元含 %d 个子元素。%s改参数会自动重建；点【确定】保留，'
            '点【取消】放弃。'
            % (result['subtype'], result['plate_side'], result['plate_side'],
               result['plate_t'], result['bolt_dia'], result['bolt_length'],
               result['child_count'], '已替换上一版预览。' if deleted else '')
        )
        self.set_status(message)
        NotificationManager.OutputPrompt(message)
        return result

    def discard_preview(self):
        handle = self.preview_handle
        self.preview_handle = None
        self.preview_result = None
        return geometry._delete_element(handle)

    # -- 收尾 --------------------------------------------------------------

    def confirm_tool(self):
        self._cancel_pending_regeneration()
        self.confirmed = True
        self.finish_tool()

    def cancel_tool(self):
        self._cancel_pending_regeneration()
        self.confirmed = False
        self.discard_preview()
        self.finish_tool()

    def finish_tool(self):
        """结束原生工具并收起面板：点【确定】/【取消】/关闭都走这里，退回默认命令。"""
        try:
            PyCommandState.StartDefaultCommand()
        except Exception:
            _log_exception('StartDefaultCommand failed')
        self.shutdown()

    def shutdown(self):
        try:
            if self.winfo_exists():
                self.destroy()
        except tk.TclError:
            pass


# ---------------------------------------------------------------------------
# 交互工具
# ---------------------------------------------------------------------------


class AnchorPlatePlacementTool(DgnPrimitiveTool):
    """点取混凝土表面上的锚板中心并放置锚板的交互工具。"""

    def __init__(self, tool_id=0):
        DgnPrimitiveTool.__init__(self, tool_id, 0)
        self.m_self = self
        self.tool_settings = None

    def _GetToolName(self, name):
        return WString('ConcreteAnchorPlatePlacementTool')

    def _OnPostInstall(self):
        AccuSnap.GetInstance().EnableSnap(True)
        DgnPrimitiveTool._OnPostInstall(self)
        NotificationManager.OutputPrompt(
            '请点取混凝土表面上锚板背面的中心点；点取后可改子项 / 间距 S / '
            '安装面 / 朝向，预览会自动重建，点【确定】保留，点【取消】或右键放弃。')

    def _OnDataButton(self, event):
        if self.tool_settings is None:
            return True
        self.tool_settings.regenerate(event.GetPoint())
        return True

    def _OnResetButton(self, event):
        settings = self.tool_settings
        if settings is not None:
            try:
                settings.after(0, settings.cancel_tool)
            except Exception:
                pass
        return True

    def _OnCleanup(self):
        settings = self.tool_settings
        if settings is None:
            return
        self.tool_settings = None
        try:
            if not settings.confirmed:
                settings.discard_preview()
        except Exception:
            pass
        settings.shutdown()

    @staticmethod
    def InstallNewInstance(tool_id=0, tool_settings=None, start_ui_loop=True):
        owner = tool_settings is None
        if owner:
            active = getattr(AnchorPlatePlacementTool, '_active_settings', None)
            if active is not None:
                try:
                    if active.winfo_exists():
                        active.lift()
                        return None
                except tk.TclError:
                    pass
        settings = (tool_settings if tool_settings is not None
                    else _AnchorPlateDialog())
        if owner:
            AnchorPlatePlacementTool._active_settings = settings
        tool = AnchorPlatePlacementTool(tool_id)
        tool.tool_settings = settings
        tool.InstallTool()
        try:
            if start_ui_loop:
                settings.run_bentley_loop()
        finally:
            if owner:
                AnchorPlatePlacementTool._active_settings = None
        return tool


def PyMain():
    """供 MicroStation Python 管理器调用的入口。"""
    try:
        AnchorPlatePlacementTool.InstallNewInstance(0)
    except Exception as error:
        detail = traceback.format_exc()
        _log('tool start failed: %s\n%s' % (error, detail))
        print('G2-混凝土锚板工具启动失败：%s\n%s' % (error, detail))
        try:
            MessageCenter.ShowErrorMessage(
                'G2-混凝土锚板启动失败：%s\n详见日志：%s' % (error, DEBUG_LOG),
                '', False)
        except Exception:
            pass
        return None
    return None


show_anchor_plate_dialog = PyMain


if __name__ == '__main__':
    PyMain()
