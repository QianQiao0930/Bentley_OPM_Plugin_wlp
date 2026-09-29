# -*- coding: utf-8 -*-
"""A1 U 型管卡（U 形螺栓管夹）—— 点选管道或辅助线自动放置。

运行后**点选一根管道或一条直线段**：

* 选中**管道**：读取其公称直径自动查表 1（DN15~900），U 型卡沿**管轴**放置，
  放置点 = 点击点在管轴上的投影 = **管道中心**；
* 选中**直线段（辅助线）**：以该直线为管轴，点击点即 **U 型管卡的放置中心
  （管中心）**，管径改用面板下拉选的 DN。

可连续点选（管道 / 直线可交替），右键退出。

**朝向**：本地 X 沿管轴，**开口方向**由面板「开口角度」给出，绕管轴右手旋转，
``0° = 开口朝上``（默认）。水平管与竖直管都能放：水平管按世界 +Z 取角度基准；
近竖直管的竖直方向无法定义角度基准，自动改用世界 +X，角度仍可调。

**建模**（扫掠）：

1. 扫掠路径 = ``+Y 侧直腿 → 与直腿相切的 180° 弯弧 → −Y 侧直腿``；
2. 用**螺栓公称直径**做圆截面，沿该路径 ``BodyFromSweep`` 扫出一个 U 型螺栓
   （弯弧于是是真圆环面，不是折线近似）；
3. 两条腿各放 **2 颗**六角螺母（背帽）：六角棱柱 − 中心通孔，第 1 颗的丝头
   露出 4 mm，第 2 颗紧贴其上。

几何口径见 ``模块/U型管卡/U型管卡_几何.py``：``C`` 是两腿**中心距**（腿中心线
距管轴 = C/2）、``B`` 是两腿**内边距**、``D`` 是**管中心 → 腿端**、``E`` 是
**弯弧起点 → 腿端**的直腿段长；由 ``D``/``E`` 反推弯弧圆心在管轴垂距 ``D−E``
处、半径 ``C/2``。**不建顶板（通板）与垫圈**（通板只进清单）。

管道信息（轴线 / 公称直径 / 保温厚度 / 走向坡度）取自 ``管道信息查询`` 的读取库
``pipe_placement_info``，并遵循它的一条铁律：**EC 读取不在工具回调里做**——点选
只把「元素 ID + 点击点」入队，真正的读取与建模由面板主循环在
``PyCadInputQueue.PythonMainLoop()`` 返回之后执行（实测回调内访问 EC 实例会让
OPM 崩溃）。

**输出全部在面板里**：生成结果与提示写入面板的「生成记录」，不打印到 Python
控制台；异常只写调试日志文件（``模块/日志/``）。
"""

from __future__ import division

import faulthandler
import importlib
import importlib.util
import math
import os
import sys
import time
import tkinter as tk
import traceback
from tkinter import ttk

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *


# ---------------------------------------------------------------------------
# 复用 管道信息查询 的读取库；接入公共支吊架库与共享 UI 工具箱
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
_PIPE_INFO_DIR = os.path.join(_REPO_ROOT, '管道信息查询', '模块', '管道信息')
_UI_DIR = os.path.join(_HERE, '模块', '公共')
_GEOM_DIR = os.path.join(_HERE, '模块', 'U型管卡')


def _load_pipe_reader():
    """按文件路径加载（必要时强制重读）管道信息读取库，规避模块缓存。"""
    name = '管道信息_读取'
    path = os.path.join(_PIPE_INFO_DIR, '管道信息_读取.py')
    if name in sys.modules:
        try:
            return importlib.reload(sys.modules[name])
        except Exception:
            pass
    if _PIPE_INFO_DIR not in sys.path:
        sys.path.insert(0, _PIPE_INFO_DIR)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


pipe_reader = _load_pipe_reader()

# ``from MSPyX import *`` 不一定导出这些符号（ISessionMgr / ElementHandle /
# PyCadInputQueue 都是典型漏网的），按名字在已加载的 MSPy 模块里补齐。
pipe_reader.fill_mspy_symbols(
    ('ISessionMgr', 'ElementHandle', 'AccuSnap', 'DgnElementSetTool',
     'PyCadInputQueue', 'WString', 'BentleyStatus', 'PyCommandState'),
    globals())

# 共享 UI 工具箱在导入前强制重读一次，避免拿到 MicroStation 缓存的旧模块。
for _path in (_REPO_ROOT, _UI_DIR, _GEOM_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)
try:
    import bentley_ui.glass as _glass_module  # noqa: F401
    import bentley_ui as _bentley_ui_module  # noqa: F401
    importlib.reload(_glass_module)
    importlib.reload(_bentley_ui_module)
except Exception:
    pass

from bentley_ui import (  # noqa: E402
    BORDER,
    CARD,
    CARD_SOFT,
    FIELD,
    INK,
    MUTED,
    UI_FONT,
    UI_FONT_BOLD,
    UI_FONT_SMALL,
    GlassDialog,
    RoundButton,
    SlimScrollbar,
)

import U型管卡_几何 as geom  # noqa: E402
import U型管卡_几何_Bentley as builder  # noqa: E402
import 支吊架公共库 as psb  # noqa: E402


UI_TITLE = 'A1-[U型管卡]'
SUPPORT_TYPE = builder.SUPPORT_TYPE
SUPPORT_CODE = builder.SUPPORT_CODE
DEBUG_LOG = os.path.join(_HERE, '模块', '日志', 'U型管卡_debug_log.txt')
try:
    os.makedirs(os.path.dirname(DEBUG_LOG), exist_ok=True)
except Exception:
    pass

# 兜底管径：管道属性读不到 / 不在表 1 时使用。
DN = geom.DEFAULT_DN

#: 版本号——排查硬崩溃时用来确认跑的是哪一版代码（写进 fault 日志）。
UI_REVISION = '2026-09-28-fix2'

# ---------------------------------------------------------------------------
# 故障兜底日志（硬崩溃 / 卡死定位）
# ---------------------------------------------------------------------------
# OPM 里的 access violation 是**原生层硬崩溃**：Python 的 try/except 抓不到，
# 也来不及吐栈，表现为"直接崩掉"。仓库其它插件（D8 / G5 / G6 / 弯头耳轴…）统一
# 用 ``faulthandler`` 兜这两种情况：
#   1) ``faulthandler.enable``：访问冲突等致命错误发生时把各线程调用栈写进文件；
#   2) ``dump_traceback_later``：主线程卡死超过 N 秒时由看门狗线程 dump 全部栈，
#      从而看出卡在哪个原生调用上（死锁不抛异常，只能靠它）。
# A1 每放置一次要建 5 个实体 + 写 3 条 ItemType，属于"高频触碰原生层"的插件，
# 因此同样布防。

FAULT_LOG = os.path.join(_HERE, '模块', '日志', 'U型管卡_fault.log')
_FAULT_FILE = None


def _enable_fault_logging():
    """布防故障日志（幂等；每次入口都重新布防看门狗）。"""
    global _FAULT_FILE
    try:
        if _FAULT_FILE is None:
            os.makedirs(os.path.dirname(FAULT_LOG), exist_ok=True)
            _FAULT_FILE = open(FAULT_LOG, 'a', encoding='utf-8')
            faulthandler.enable(_FAULT_FILE)
        _FAULT_FILE.write('=== session start %s rev=%s ===\n'
                          % (time.strftime('%Y-%m-%d %H:%M:%S'), UI_REVISION))
        _FAULT_FILE.flush()
        faulthandler.dump_traceback_later(12.0, repeat=True, file=_FAULT_FILE)
    except Exception:
        pass


def _disable_fault_logging():
    try:
        faulthandler.cancel_dump_traceback_later()
    except Exception:
        pass

# ---------------------------------------------------------------------------
# 清单写库（共享支吊架库 ItemType）策略
# ---------------------------------------------------------------------------
# 本插件是「点一次放一个」的即时落图型（同 A2 管夹 / F10 耳板），每次放置只写
# 一次库，不存在预览反复触发写库的问题。ITEM_TYPE_ATTACH 仍是逃生开关：若本机
# 该原生调用持续崩溃，置 False 后几何照常生成、照常落图，只是这批管卡不进清单。
ITEM_TYPE_ATTACH = True


def _log(message):
    try:
        stamp = time.strftime('%Y-%m-%d %H:%M:%S')
        with open(DEBUG_LOG, 'a', encoding='utf-8') as stream:
            stream.write('[%s] %s\n' % (stamp, message))
            stream.flush()
    except Exception:
        pass


def _log_exception(title):
    _log('%s: %s' % (title, traceback.format_exc()))


def _uor_per_mm():
    model = ISessionMgr.GetActiveDgnModel()
    return model.GetModelInfo().GetUorPerMeter() / 1000.0


# ---------------------------------------------------------------------------
# 面板
# ---------------------------------------------------------------------------


class _ClampPanel(GlassDialog):
    """点选提示 + 参数（管径 / 角度）+ 尺寸对照 + 生成记录。

    MicroStation 的原生回调（``_OnPostLocate`` / ``_OnDataButton``）里**不做 EC
    读取、也不碰 Tk**：只把 (元素 ID, 点击点) 放进 ``pending``、把提示放进
    ``_pending_status``。真正读取 EC 与建模型都在主循环
    ``PyCadInputQueue.PythonMainLoop()`` 返回之后调用 :meth:`_run_pending` 完成。
    """

    STATE_KEY = 'A1UBoltClamp'

    def __init__(self):
        GlassDialog.__init__(self, title=UI_TITLE)
        self.pending = []
        self._pending_status = None
        self._pending_status_is_error = False
        self._close_requested = False
        self._dn = tk.StringVar()
        self._angle = tk.StringVar()
        self._dn_by_label = {}
        self._angle_by_label = {}
        self._readout = None
        self._build()
        self.restore_state()
        self.restore_position()
        self.protocol('WM_DELETE_WINDOW', self.close_panel)
        try:
            self.minsize(430, 780)
        except tk.TclError:
            pass
        _log('panel built file=%s' % os.path.abspath(__file__))

    # -- 界面 --------------------------------------------------------------

    def _build(self):
        form = self.build_shell(
            UI_TITLE,
            '点选管道（自动读管径）或辅助线（用面板管径），在放置中心生成 U 型管卡')
        form.columnconfigure(0, weight=1)

        hint_frame, hint_text = self._text_field(form, height=4)
        hint_frame.grid(row=0, column=0, sticky='ew')
        self._set_text(hint_text, (
            '在模型中点选一根管道或一条直线段：\n'
            '· 管道 → 自动读取公称直径查表 1，管卡沿管轴放置；\n'
            '· 直线段（辅助线）→ 点击点即 U 型管卡的放置中心（管中心），'
            '管径用下面下拉选的 DN。\n'
            '可连续点选，右键退出。开口角度默认朝上。'))

        ttk.Label(form, text='管径（读不到管道属性 / 点选辅助线时使用）',
                  style='Section.TLabel').grid(row=1, column=0, sticky='w',
                                               pady=(6, 2))

        dn_row = tk.Frame(form, bg=CARD)
        dn_row.grid(row=2, column=0, sticky='w')
        tk.Label(dn_row, text='公称直径', bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left')
        for key, label in geom.dn_choices():
            self._dn_by_label[label] = key
        self._dn_combo = ttk.Combobox(
            dn_row, textvariable=self._dn, state='readonly', width=22,
            style='Glass.TCombobox', values=list(self._dn_by_label))
        self._dn_combo.pack(side='left', padx=(10, 0))
        self._dn_combo.bind('<<ComboboxSelected>>', self._refresh_readout)

        angle_row = tk.Frame(form, bg=CARD)
        angle_row.grid(row=3, column=0, sticky='w', pady=(8, 0))
        tk.Label(angle_row, text='开口角度', bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left')
        for value, label in geom.angle_choices():
            self._angle_by_label[label] = value
        self._angle_combo = ttk.Combobox(
            angle_row, textvariable=self._angle, state='readonly', width=22,
            style='Glass.TCombobox', values=list(self._angle_by_label))
        self._angle_combo.pack(side='left', padx=(10, 0))
        self._angle_combo.bind('<<ComboboxSelected>>', self._refresh_readout)
        tk.Label(form, text='绕管轴旋转（右手定则），0° = 开口朝上（默认）；'
                            '竖直管同样可调',
                 bg=CARD, fg=MUTED, font=UI_FONT_SMALL).grid(
            row=4, column=0, sticky='w')

        ttk.Label(form, text='表 1 尺寸对照（只读）',
                  style='Section.TLabel').grid(row=5, column=0, sticky='w',
                                               pady=(8, 2))
        readout_frame, readout_text = self._text_field(form, height=8)
        readout_frame.grid(row=6, column=0, sticky='ew')
        self._readout = readout_text

        ttk.Label(form, text='生成记录', style='Section.TLabel').grid(
            row=7, column=0, sticky='w', pady=(8, 2))
        log_frame = tk.Frame(form, bg=CARD_SOFT, highlightbackground=BORDER,
                             highlightthickness=1)
        log_frame.grid(row=8, column=0, sticky='nsew')
        form.rowconfigure(8, weight=1)
        self._log_view = tk.Text(
            log_frame, height=14, width=36, wrap='word', font=UI_FONT_SMALL,
            bg=CARD_SOFT, fg=INK, relief='flat', highlightthickness=0, bd=0,
            padx=8, pady=6, cursor='arrow')
        log_bar = SlimScrollbar(log_frame, command=self._log_view.yview,
                                trough=CARD_SOFT)
        self._log_view.configure(yscrollcommand=log_bar.set)
        self._log_view.pack(side='left', fill='both', expand=True)
        log_bar.pack(side='right', fill='y')
        self._log_view.configure(state='disabled')

        self._status_frame, self._status_text = self._text_field(form, height=3)
        self._status_frame.grid(row=9, column=0, sticky='ew', pady=(6, 0))
        self._set_text(self._status_text, '请在模型中点选管道或辅助线。')

        buttons = tk.Frame(form, bg=CARD)
        buttons.grid(row=10, column=0, sticky='ew', pady=(8, 0))
        self.clear_button = RoundButton(
            buttons, '清空记录', self.clear_log, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self.close_button = RoundButton(
            buttons, '退出', self.close_panel, primary=True, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self.close_button.pack(side='right')
        self.clear_button.pack(side='right', padx=(0, 8))

        self._refresh_readout()

    def _text_field(self, parent, height=3):
        frame = tk.Frame(parent, bg=CARD_SOFT, highlightbackground=BORDER,
                         highlightthickness=1)
        text = tk.Text(
            frame, height=height, width=36, wrap='word', font=UI_FONT_SMALL,
            bg=CARD_SOFT, fg=INK, relief='flat', highlightthickness=0, bd=0,
            padx=8, pady=5, cursor='arrow', takefocus=0)
        bar = SlimScrollbar(frame, command=text.yview, trough=CARD_SOFT)
        text.configure(yscrollcommand=bar.set)
        text.pack(side='left', fill='both', expand=True)
        bar.pack(side='right', fill='y')
        text.configure(state='disabled')
        return frame, text

    def _set_text(self, text_widget, value):
        if text_widget is None:
            return
        try:
            text_widget.configure(state='normal')
            text_widget.delete('1.0', 'end')
            text_widget.insert('1.0', value or '')
            text_widget.configure(state='disabled')
            text_widget.yview_moveto(0.0)
        except tk.TclError:
            pass

    # -- 参数与只读对照 ----------------------------------------------------

    def restore_state(self):
        state = self.ui_state
        selected = None
        fallback = None
        for label, key in self._dn_by_label.items():
            if fallback is None:
                fallback = label
            if key == DN:
                fallback = label
            if key == state.get('dn'):
                selected = label
        self._dn.set(selected or fallback)

        angle_selected = None
        try:
            saved_angle = float(state.get('angle', geom.DEFAULT_ANGLE_DEG))
        except (TypeError, ValueError):
            saved_angle = geom.DEFAULT_ANGLE_DEG
        for label, value in self._angle_by_label.items():
            if value == geom.DEFAULT_ANGLE_DEG:
                angle_selected = label
            if abs(value - saved_angle) < 1e-9:
                angle_selected = label
        self._angle.set(angle_selected or list(self._angle_by_label)[0])

    def persist_state(self, state):
        try:
            state['dn'] = self.current_dn()
            state['angle'] = self.current_angle()
        except Exception:
            pass

    def current_dn(self):
        return self._dn_by_label.get(self._dn.get(), DN)

    def current_angle(self):
        return self._angle_by_label.get(self._angle.get(),
                                        geom.DEFAULT_ANGLE_DEG)

    def _refresh_readout(self, _event=None):
        """刷新「表 1 尺寸对照」：表值 + 反推的几何量。"""
        try:
            geometry = geom.build_geometry(self.current_dn())
        except Exception as error:
            self._set_text(self._readout, '读取表 1 失败：%s' % error)
            return
        lines = [
            'DN%d / %s，U 型螺栓 %s（d=%.0f）'
            % (geometry.dn, geometry.nps, geometry.bolt, geometry.d),
            '表 1：B（两腿内边距）=%.0f，C（两腿中心距）=%.0f，'
            'D（管中心→腿端）=%.0f，E（原图直腿段列，仅参考）=%.0f'
            % (geometry.inner_mm, geometry.center_mm, geometry.tip_mm,
               geometry.table_straight_mm),
            '腿中心距管轴 = C/2 = %.1f（两腿外缘 %.1f）'
            % (geometry.r_leg, geometry.outer_span_mm),
            '弯弧：圆心在管轴上，半径 C/2 = %.1f，最低点 %.1f（= −C/2）；'
            '直腿段长 = D = %.0f'
            % (geometry.r_leg, geometry.arc_bottom_y, geometry.straight_mm),
            '螺母：%s 六角，对边 %.1f × 高 %.1f，每腿 2 颗（共 4 颗）；'
            '组中心距腿端 (D−管半径)/2 = %.1f（y=%.1f），占 %.1f~%.1f'
            % (geometry.bolt, geometry.nut_across_flats, geometry.nut_height,
               geometry.nut_end_offset_mm(), geometry.nut_center_y,
               geometry.nuts[0][1], geometry.nuts[1][2]),
            '整组沿开口方向总高 %.1f（弯弧最低点 → 螺母顶）'
            % geometry.height_mm,
        ]
        clearance = geometry.pipe_clearance_mm()
        if clearance is None:
            lines.append('弯弧包管：未知（表内没有 DN%d 的管外径）'
                         % geometry.dn)
        else:
            lines.append('弯弧包管：螺栓内表面半径 %.1f > 管外半径 %.1f，'
                         '净空 %.1f mm ✓'
                         % (geometry.inner_face_radius,
                            geometry.pipe_od_mm / 2.0, clearance))
        if geometry.load_axial_kn is not None:
            load = '表 1 允许荷载（20℃）：正向 %.1f kN' % geometry.load_axial_kn
            if geometry.load_lateral_kn is not None:
                load += '、横向 %.1f kN' % geometry.load_lateral_kn
            lines.append(load)
        lines.append('角度：%g°（绕管轴，0° = 开口朝上）'
                     % self.current_angle())
        self._set_text(self._readout, '\n'.join(lines))

    # -- 输出（只在主循环 / Tk 上下文里调用） ------------------------------

    def _apply_status(self, message, is_error=False):
        self._set_text(getattr(self, '_status_text', None), message)

    def append_log(self, message):
        text_widget = getattr(self, '_log_view', None)
        if text_widget is None:
            return
        try:
            text_widget.configure(state='normal')
            text_widget.insert('end', str(message) + '\n\n')
            text_widget.see('end')
            text_widget.configure(state='disabled')
        except tk.TclError:
            pass

    def clear_log(self):
        text_widget = getattr(self, '_log_view', None)
        if text_widget is None:
            return
        try:
            text_widget.configure(state='normal')
            text_widget.delete('1.0', 'end')
            text_widget.configure(state='disabled')
        except tk.TclError:
            pass

    # -- 原生回调入口：只写普通 Python 状态，绝不碰 Tk / EC ---------------

    def set_status(self, message, is_error=False):
        self._pending_status = message
        self._pending_status_is_error = bool(is_error)

    def queue_pick(self, element_id, click_mm):
        self.pending.append((element_id, click_mm))

    def close_panel(self):
        self._close_requested = True

    # -- 主循环 ------------------------------------------------------------

    def _run_pending(self):
        """在 ``PythonMainLoop`` 返回之后执行：安全读取 EC 并建模。"""
        self._drain_pending()
        if self._pending_status is not None:
            message = self._pending_status
            is_error = self._pending_status_is_error
            self._pending_status = None
            self._pending_status_is_error = False
            self._apply_status(message, is_error)

    def _drain_pending(self):
        pending, self.pending = self.pending, []
        for element_id, click_mm in pending:
            self._process(element_id, click_mm)

    def _process(self, element_id, click_mm):
        # 这里已不在工具回调内（PythonMainLoop 返回之后），可安全读取 EC。
        try:
            handle = pipe_reader.element_handle_by_id(element_id)
        except Exception as error:
            _log_exception('open element failed')
            self.set_status('打开元素失败：%s' % error, True)
            return
        if handle is None:
            self.set_status('元素 ID %s 已失效（可能已被删除）。' % element_id,
                            True)
            return
        try:
            placement = pipe_reader.pipe_placement_info(handle, 'auto')
            result, message = build_on_pick(
                placement, click_mm, self.current_dn(), self.current_angle(),
                attach=ITEM_TYPE_ATTACH)
        except Exception as error:
            _log_exception('build U-bolt clamp failed')
            self.set_status('生成失败：%s' % error, True)
            return
        self.append_log(message)
        self.set_status('已生成一副 U 型管卡。继续点选管道或辅助线，右键退出。')
        return result

    # -- 收尾 --------------------------------------------------------------

    def _finish_tool(self):
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

    def run_dialog_loop(self):
        """Tk 主循环：UI 事件 + MicroStation；EC 读取放在 PythonMainLoop 之后。"""
        while tk._default_root is not None:
            try:
                self.update_idletasks()
                self.update()
            except tk.TclError:
                break
            if self._close_requested:
                self._close_requested = False
                self._finish_tool()
                break
            try:
                PyCadInputQueue.PythonMainLoop()
            except Exception:
                _log_exception('PythonMainLoop failed')
                break
            self._run_pending()


# ---------------------------------------------------------------------------
# 建模调度
# ---------------------------------------------------------------------------


def _is_pipe_placement(placement):
    """判断本次点选到的是**管道**（有 OpenPlant EC 实例）还是普通直线段。"""
    snapshot = placement.get('snapshot') or {}
    return bool((snapshot.get('ec') or {}).get('found'))


def build_on_pick(placement, click_mm, fallback_dn=None, angle_deg=None,
                  attach=True):
    """按所选元素（管道或直线段）与点击点生成一副 U 型管卡。

    * 选中**管道**：用其公称直径自动查表 1；点击点在轴上的投影 = 放置中心；
    * 选中**直线段**（辅助线）：以该直线为管轴，**点击点即放置中心（管中心）**，
      管径改用面板输入的 ``fallback_dn``。

    ``attach=True`` 时把整组写进公共支吊架库；``attach=False``（逃生开关
    ``ITEM_TYPE_ATTACH``）时只出几何、不进清单统计。
    返回 ``(模型单元, 提示文本)``。
    """
    fallback_dn = DN if fallback_dn is None else fallback_dn
    angle_deg = geom.DEFAULT_ANGLE_DEG if angle_deg is None else angle_deg

    start = placement.get('start_mm')
    end = placement.get('end_mm')
    axis = placement.get('axis')
    if not start or not end or axis is None:
        raise ValueError('该元素没有可用的轴线（起点 / 终点不可用），无法定位 '
                         'U 型管卡；请点选管道或一条直线段。')

    is_pipe = _is_pipe_placement(placement)
    nominal = placement.get('nominal_diameter_mm')
    matched = geom.match_table_dn(nominal)
    dn = matched if matched is not None else fallback_dn

    if is_pipe:
        if click_mm is not None:
            center = pipe_reader.project_onto_axis(click_mm, start, end)
        else:
            center = placement.get('center_mm') or start
    else:
        # 点选辅助线：**点击点本身就是放置中心**（U 型管卡的示意图中心 = 管中心），
        # 不做投影——这样"在哪儿点就放在哪儿"，与甲方口径一致。
        center = click_mm or placement.get('center_mm') or start

    pipe_insulation = placement.get('insulation_thickness_mm')
    insulation = 0.0 if pipe_insulation is None else float(pipe_insulation)
    pipe_number = ''
    snapshot = placement.get('snapshot') or {}
    values = snapshot.get('values') or {}
    for key in ('linenumber', 'line_number'):
        if values.get(key):
            pipe_number = str(values[key])
            break

    raw_warnings = [text for text in (placement.get('warnings') or []) if text]
    parts = []
    if is_pipe:
        if matched is not None:
            parts.append('管道公称直径 %.1f mm → 表 1 DN%d。'
                         % (float(nominal), dn))
        else:
            parts.append('管道公称直径 %s 未匹配到表 1，改用面板管径 DN%d。'
                         % ('未知' if nominal is None else '%.1f mm' % nominal,
                            fallback_dn))
        warnings = raw_warnings
    else:
        parts.append('按所选直线作为管轴、点击点为放置中心；未读到管道属性，'
                     '改用面板参数 DN%d。' % dn)
        # 直线元素上"没有管道实例 / 没有公称直径 / 无法标定属性单位"属正常，
        # 都是面向管道 EC 属性的提示，对直线无意义。
        skip = ('没有找到 OpenPlant', '公称直径', '没有读到公称直径',
                '标定属性单位')
        warnings = [text for text in raw_warnings
                    if not any(mark in text for mark in skip)]

    if not placement.get('exact', True):
        parts.append('按包围盒最长边近似管轴（仅对与世界坐标轴平行的直管段可靠）。')
    orientation = placement.get('orientation')
    slope = placement.get('slope_percent')
    if orientation:
        text = '走向%s' % orientation
        if slope is not None:
            text += '（坡度 %.2f%%）' % slope
        parts.append(text + '。')
    if warnings:
        parts.append('注意：%s' % '；'.join(warnings))

    result, message = builder.build_clamp(
        center, axis, dn=dn, angle_deg=angle_deg,
        insulation_mm=insulation, note=''.join(parts))

    if attach:
        geometry = geom.build_geometry(dn)
        attached = builder.attach_support_items(
            result, dn, geometry, angle_deg, pipe_number=pipe_number)
        if attached:
            message += '\n已写入公共支吊架清单（%d 条记录%s）。' % (
                attached, '，管道号 %s' % pipe_number if pipe_number else '')
        else:
            message += '\n注意：公共支吊架清单写入失败（几何已生成），详见日志。'
    return result, message


# ---------------------------------------------------------------------------
# 交互工具：点选管道 / 辅助线（只入队，EC 读取在面板循环里）
# ---------------------------------------------------------------------------


class UBoltClampPipeTool(DgnElementSetTool):
    """点选**管道或直线段**，在放置中心生成一副 A1 U 型管卡。

    选中管道时自动读取公称直径；选中普通直线段（辅助线）时以该直线为管轴、
    **点击点即放置中心**，管径用面板下拉的 DN。两种元素都支持，可连续点选。

    ``_OnPostLocate`` 只记元素 ID；``_OnDataButton`` 只把 (元素 ID, 点击点)
    交给面板排队并消费点击——**回调内不做任何 EC 读取**。
    """

    def __init__(self, tool_id=0, panel=None):
        DgnElementSetTool.__init__(self, tool_id)
        self.m_self = self
        self.panel = panel
        self._located_id = None

    def _GetToolName(self, name):
        return WString('UBoltClampPipeTool')

    def _DoGroups(self):
        return False

    def _AllowSelection(self):
        return DgnElementSetTool.eUSES_SS_None

    def _NeedAcceptPoint(self):
        return False

    def _WantDynamics(self):
        return False

    def _OnPostInstall(self):
        AccuSnap.GetInstance().EnableSnap(True)
        DgnElementSetTool._OnPostInstall(self)
        if self.panel is not None:
            self.panel.set_status('请点选一根管道或一条直线段（辅助线）；右键退出。')

    def _OnPostLocate(self, path, cant_accept_reason):
        """只记下定位到的元素 ID（不保存句柄、不读属性）。"""
        if not DgnElementSetTool._OnPostLocate(self, path, cant_accept_reason):
            return False
        try:
            handle = ElementHandle(path.GetHeadElem(), path.GetRoot())
            self._located_id = pipe_reader.read_element_id(handle)
            return self._located_id is not None
        except Exception:
            self._located_id = None
            return False

    def _OnDataButton(self, event):
        """把 (元素 ID, 点击点) 入队；返回 True 消费本次点击。"""
        if self.panel is None:
            return True
        element_id = self._located_id
        if element_id is None:
            self.panel.set_status(
                '没有定位到元素：请把光标放在管道或直线上再点击。', True)
            return True
        try:
            point = event.GetPoint()
            uor = _uor_per_mm()
            click_mm = (point.x / uor, point.y / uor, point.z / uor)
        except Exception:
            click_mm = None
        self.panel.queue_pick(element_id, click_mm)
        return True

    def _OnResetButton(self, event):
        if self.panel is not None:
            self.panel.close_panel()
        return True

    def _OnRestartTool(self):
        # 保留面板引用重装工具，从而可以连续点取。
        panel = self.panel
        self.panel = None
        UBoltClampPipeTool.InstallNewInstance(self.GetToolId(), panel, False)

    @staticmethod
    def InstallNewInstance(tool_id=0, panel=None, start_loop=True):
        tool = UBoltClampPipeTool(tool_id, panel)
        tool.InstallTool()
        if start_loop and panel is not None:
            panel.run_dialog_loop()
        return tool


_active_panel = None


def show_clamp_panel():
    """打开面板；已在运行时把已有窗口提到前台，避免重复窗口残留。"""
    global _active_panel
    if _active_panel is not None:
        try:
            if _active_panel.winfo_exists():
                _active_panel.lift()
                return None
        except tk.TclError:
            pass
    panel = _ClampPanel()
    _active_panel = panel
    try:
        return UBoltClampPipeTool.InstallNewInstance(0, panel, True)
    finally:
        _active_panel = None


def PyMain():
    try:
        _log('PyMain: entry rev=%s' % UI_REVISION)
        _enable_fault_logging()
        return show_clamp_panel()
    except Exception as error:
        detail = traceback.format_exc()
        _log_exception('U-bolt clamp tool start failed')
        print('A1 U型管卡启动失败：%s\n%s' % (error, detail))
        try:
            MessageCenter.ShowErrorMessage(
                'A1 U型管卡启动失败：%s\n详见日志：%s' % (error, DEBUG_LOG),
                '', False)
        except Exception:
            pass
        return None


if __name__ == '__main__':
    PyMain()
