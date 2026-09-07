# -*- coding: utf-8 -*-
"""Parameterized end-welded triangle bracket placement tool.

Select variant A-D in the dialog, enter L1 and E in millimetres, then pick
the centre of the welded end face in the active MicroStation model.
"""

from __future__ import division

import math
import os

import end_welded_triangle_bracket as base


DEBUG_LOG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    u'\u7aef\u710a\u4e09\u89d2\u67b6_debug_log.txt')

# A separate prefix keeps this tool's BOM ItemTypes distinct from the legacy
# type-1 end_welded_triangle_bracket tool, even when both are used in one DGN.
ITEM_TYPE_PREFIX = 'EndWeldedTriangleBracketComponent'
MIN_END_OVERHANG = 150.0
MAX_BEAM_LENGTH = 2500.0

COMPONENT_A_NAME = u'\u6784\u4ef6A\uff08\u6a2a\u62c5\uff09'
COMPONENT_B_NAME = u'\u6784\u4ef6B\uff08\u659c\u6491\uff09'

VARIANTS = {
    'A': {
        'h_beam': (125.0, 125.0, 6.5, 9.0),
        'angle': (100.0, 10.0),
        'h_beam_specification': u'H125\u00d7125\u00d76.5\u00d79',
        'angle_specification': u'\u2220100\u00d710',
    },
    'B': {
        'h_beam': (150.0, 150.0, 7.0, 10.0),
        'angle': (125.0, 10.0),
        'h_beam_specification': u'H150\u00d7150\u00d77\u00d710',
        'angle_specification': u'\u2220125\u00d710',
    },
    'C': {
        'h_beam': (200.0, 200.0, 8.0, 12.0),
        'angle': (160.0, 12.0),
        'h_beam_specification': u'H200\u00d7200\u00d78\u00d712',
        'angle_specification': u'\u2220160\u00d712',
    },
    'D': {
        'h_beam': (250.0, 250.0, 9.0, 14.0),
        'angle': (200.0, 14.0),
        'h_beam_specification': u'H250\u00d7250\u00d79\u00d714',
        'angle_specification': u'\u2220200\u00d714',
    },
}


def _log(message):
    try:
        with open(DEBUG_LOG, 'a', encoding='utf-8') as log_file:
            log_file.write(str(message) + '\n')
    except Exception:
        pass


def _variant_description(variant_key):
    variant = VARIANTS[variant_key]
    return (u'%s  |  %s  |  %s' %
            (variant_key, variant['h_beam_specification'],
             variant['angle_specification']))


def calculate_beam_length(l1, end_overhang, variant_key):
    """Return L2, rounded upward to a whole millimetre for one variant."""
    angle_width = VARIANTS[variant_key]['angle'][0]
    return float(math.ceil(
        float(l1) + angle_width * math.sqrt(2.0) / 2.0 + float(end_overhang)))


def _apply_variant_to_base(variant_key):
    """Apply a variant only while one synchronous base-tool call is running."""
    variant = VARIANTS[variant_key]
    old_values = {
        'H_BEAM_HEIGHT': base.H_BEAM_HEIGHT,
        'H_BEAM_WIDTH': base.H_BEAM_WIDTH,
        'H_BEAM_WEB_THICKNESS': base.H_BEAM_WEB_THICKNESS,
        'H_BEAM_FLANGE_THICKNESS': base.H_BEAM_FLANGE_THICKNESS,
        'ANGLE_WIDTH': base.ANGLE_WIDTH,
        'ANGLE_THICKNESS': base.ANGLE_THICKNESS,
        'ITEM_TYPE_PREFIX': base.ITEM_TYPE_PREFIX,
        '_attach_component_item': base._attach_component_item,
    }
    h_height, h_width, h_web, h_flange = variant['h_beam']
    angle_width, angle_thickness = variant['angle']
    base.H_BEAM_HEIGHT = h_height
    base.H_BEAM_WIDTH = h_width
    base.H_BEAM_WEB_THICKNESS = h_web
    base.H_BEAM_FLANGE_THICKNESS = h_flange
    base.ANGLE_WIDTH = angle_width
    base.ANGLE_THICKNESS = angle_thickness
    base.ITEM_TYPE_PREFIX = ITEM_TYPE_PREFIX

    original_attach = old_values['_attach_component_item']

    def attach_with_variant_metadata(element, component_code, component_name,
                                     specification, design_length_mm):
        if component_code == 'HBeam':
            component_name = COMPONENT_A_NAME
            specification = variant['h_beam_specification']
        elif component_code == 'AngleBrace':
            component_name = COMPONENT_B_NAME
            specification = variant['angle_specification']
        return original_attach(element, component_code, component_name,
                               specification, design_length_mm)

    base._attach_component_item = attach_with_variant_metadata
    return old_values


def _restore_base(old_values):
    for name, value in old_values.items():
        setattr(base, name, value)


def create_end_welded_triangle_bracket(l1, end_overhang, variant_key,
                                       origin=(0.0, 0.0, 0.0)):
    """Create one selected bracket variant at the given welded-face centre."""
    if variant_key not in VARIANTS:
        _log('unknown variant: %r' % (variant_key,))
        return None
    if l1 <= 0.0:
        _log('L1 must be greater than zero')
        return None
    if end_overhang < MIN_END_OVERHANG:
        _log('E %.1f is below minimum %.1f' %
             (end_overhang, MIN_END_OVERHANG))
        return None

    angle_width = VARIANTS[variant_key]['angle'][0]
    min_l1 = angle_width * math.sqrt(2.0) / 2.0
    if l1 <= min_l1:
        _log('L1 must exceed %.3f for variant %s' % (min_l1, variant_key))
        return None
    beam_length = calculate_beam_length(l1, end_overhang, variant_key)
    if beam_length > MAX_BEAM_LENGTH:
        _log('L2 %.1f exceeds maximum %.1f' %
             (beam_length, MAX_BEAM_LENGTH))
        return None

    old_values = _apply_variant_to_base(variant_key)
    try:
        components = base.create_end_welded_triangle_bracket(
            l1, end_overhang, origin)
    except Exception as error:
        _log('create exception for variant %s: %r' % (variant_key, error))
        return None
    finally:
        _restore_base(old_values)

    if components is not None:
        _log('created variant=%s, L1=%.3f, E=%.3f, L2=%.0f, ids=%s' %
             (variant_key, l1, end_overhang, beam_length,
              tuple(element.GetElementId() for element in components)))
    return components


def export_end_welded_triangle_bracket_bom_json(output_path=None):
    """Export only ItemTypes created by this multi-variant bracket tool."""
    old_prefix = base.ITEM_TYPE_PREFIX
    base.ITEM_TYPE_PREFIX = ITEM_TYPE_PREFIX
    try:
        if output_path is None:
            output_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                u'\u7aef\u710a\u4e09\u89d2\u67b6_bom.json')
        return base.export_triangle_bracket_bom_json(output_path)
    finally:
        base.ITEM_TYPE_PREFIX = old_prefix


ACTIVE_TRIANGLE_BRACKET_PLACEMENT_TOOL = None


class TriangleBracketPlacementTool(base.DgnPrimitiveTool):
    """Pick the centre of the H-beam's left welded end face."""

    def __init__(self, l1, end_overhang, variant_key):
        base.DgnPrimitiveTool.__init__(self, 0, 0)
        self.l1 = l1
        self.end_overhang = end_overhang
        self.variant_key = variant_key
        self.m_self = self

    def _GetToolName(self, name):
        return base.WString('EndWeldedTriangleBracketPlacementTool')

    def _OnPostInstall(self):
        base.AccuSnap.GetInstance().EnableSnap(True)
        base.DgnPrimitiveTool._OnPostInstall(self)
        base.NotificationManager.OutputPrompt(
            u'\u8bf7\u70b9\u53d6\u6a2a\u62c5\u5de6\u7aef\u4e0e\u65e2\u6709\u94a2\u7ed3\u6784\u710a\u63a5\u9762\u7684\u4e2d\u5fc3\u3002')

    def _OnDataButton(self, ev):
        point = ev.GetPoint()
        uor_per_mm = base._uor_per_mm()
        origin = (point.x / uor_per_mm,
                  point.y / uor_per_mm,
                  point.z / uor_per_mm)
        components = create_end_welded_triangle_bracket(
            self.l1, self.end_overhang, self.variant_key, origin)
        if components is None:
            base.MessageCenter.ShowErrorMessage(
                u'\u7aef\u710a\u4e09\u89d2\u67b6\u751f\u6210\u5931\u8d25\uff0c\u8bf7\u67e5\u770b\u8c03\u8bd5\u65e5\u5fd7\u3002', '', False)
        else:
            base.MessageCenter.ShowInfoMessage(
                u'\u7aef\u710a\u4e09\u89d2\u67b6\u5df2\u751f\u6210\uff1a%s\u3002' %
                _variant_description(self.variant_key), '', False)
        return True

    def _OnResetButton(self, ev):
        base.NotificationManager.OutputPrompt(
            u'\u5df2\u53d6\u6d88\u7aef\u710a\u4e09\u89d2\u67b6\u5b9a\u4f4d\u3002')
        return True

    @staticmethod
    def InstallNewInstance(l1, end_overhang, variant_key):
        global ACTIVE_TRIANGLE_BRACKET_PLACEMENT_TOOL
        ACTIVE_TRIANGLE_BRACKET_PLACEMENT_TOOL = TriangleBracketPlacementTool(
            l1, end_overhang, variant_key)
        ACTIVE_TRIANGLE_BRACKET_PLACEMENT_TOOL.InstallTool()


def show_triangle_bracket_dialog():
    """Show the variant selector and the L1/E input dialog."""
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except Exception as error:
        _log('tkinter unavailable: %r' % error)
        return None

    root = tk.Tk()
    root.title(u'\u7aef\u710a\u4e09\u89d2\u67b6\u751f\u6210')
    root.resizable(False, False)
    form = ttk.Frame(root, padding=16)
    form.grid(row=0, column=0, sticky='nsew')

    variant_value = tk.StringVar(value='A')
    l1_value = tk.StringVar(value='1000')
    end_overhang_value = tk.StringVar(value='150')
    h_beam_value = tk.StringVar()
    angle_value = tk.StringVar()
    calculated_l2_value = tk.StringVar()

    ttk.Label(form, text=u'\u5b50\u9879').grid(
        row=0, column=0, sticky='w', pady=5)
    variant_box = ttk.Combobox(form, textvariable=variant_value, width=28,
                               values=tuple(VARIANTS.keys()), state='readonly')
    variant_box.grid(row=0, column=1, columnspan=2, sticky='ew',
                     padx=(12, 0), pady=5)

    ttk.Label(form, text=u'\u6784\u4ef6A\uff08\u6a2a\u62c5\uff09').grid(
        row=1, column=0, sticky='w', pady=5)
    ttk.Label(form, textvariable=h_beam_value).grid(
        row=1, column=1, columnspan=2, sticky='w', padx=(12, 0), pady=5)
    ttk.Label(form, text=u'\u6784\u4ef6B\uff08\u659c\u6491\uff09').grid(
        row=2, column=0, sticky='w', pady=5)
    ttk.Label(form, textvariable=angle_value).grid(
        row=2, column=1, columnspan=2, sticky='w', padx=(12, 0), pady=5)

    ttk.Label(form, text=u'L1\uff08\u710a\u63a5\u7aef\u9762\u81f3\u659c\u6491\u4e0a\u7aef\u4e2d\u5fc3\uff09').grid(
        row=3, column=0, sticky='w', pady=5)
    ttk.Entry(form, textvariable=l1_value, width=18).grid(
        row=3, column=1, sticky='ew', padx=(12, 6), pady=5)
    ttk.Label(form, text='mm').grid(row=3, column=2, sticky='w', pady=5)

    ttk.Label(form, text=u'E\uff08\u6a2a\u62c5\u6700\u8fdc\u7aef\u81f3\u659c\u6491\u4e0a\u7aef\u5916\u4fa7\u659c\u89d2\uff09').grid(
        row=4, column=0, sticky='w', pady=5)
    ttk.Entry(form, textvariable=end_overhang_value, width=18).grid(
        row=4, column=1, sticky='ew', padx=(12, 6), pady=5)
    ttk.Label(form, text=u'mm\uff08\u2265150\uff09').grid(
        row=4, column=2, sticky='w', pady=5)

    ttk.Label(form, text=u'\u8ba1\u7b97\u6a2a\u62c5\u603b\u957f L2').grid(
        row=5, column=0, sticky='w', pady=5)
    ttk.Label(form, textvariable=calculated_l2_value).grid(
        row=5, column=1, sticky='w', padx=(12, 6), pady=5)
    ttk.Label(form, text='mm').grid(row=5, column=2, sticky='w', pady=5)

    note = tk.StringVar()
    ttk.Label(form, textvariable=note, foreground='#505050', justify='left').grid(
        row=6, column=0, columnspan=3, sticky='w', pady=(10, 6))

    def update_display(*unused):
        variant_key = variant_value.get()
        if variant_key not in VARIANTS:
            return
        variant = VARIANTS[variant_key]
        h_beam_value.set(variant['h_beam_specification'])
        angle_value.set(variant['angle_specification'])
        angle_width = variant['angle'][0]
        note.set(
            u'%s\uff1b%s\u3002\nL2 = ceil(L1 + %.0f\u00d7\u221a2/2 + E)\uff1bL2 \u4e0d\u5f97\u5927\u4e8e %.0f mm\u3002' %
            (COMPONENT_A_NAME, COMPONENT_B_NAME, angle_width, MAX_BEAM_LENGTH))
        try:
            l2 = calculate_beam_length(float(l1_value.get()),
                                        float(end_overhang_value.get()),
                                        variant_key)
            calculated_l2_value.set('%d' % l2)
        except ValueError:
            calculated_l2_value.set(u'\u2014')

    variant_value.trace_add('write', update_display)
    l1_value.trace_add('write', update_display)
    end_overhang_value.trace_add('write', update_display)
    update_display()

    def generate():
        try:
            variant_key = variant_value.get()
            l1 = float(l1_value.get())
            end_overhang = float(end_overhang_value.get())
            minimum_l1 = VARIANTS[variant_key]['angle'][0] * math.sqrt(2.0) / 2.0
            if l1 <= minimum_l1:
                raise ValueError(u'L1 \u5fc5\u987b\u5927\u4e8e %.3f mm\u3002' % minimum_l1)
            if end_overhang < MIN_END_OVERHANG:
                raise ValueError(u'E \u4e0d\u5f97\u5c0f\u4e8e %.0f mm\u3002' % MIN_END_OVERHANG)
            beam_length = calculate_beam_length(l1, end_overhang, variant_key)
            if beam_length > MAX_BEAM_LENGTH:
                raise ValueError(u'\u8ba1\u7b97\u5f97\u5230 L2=%d mm\uff0c\u4e0d\u80fd\u5927\u4e8e %.0f mm\u3002' %
                                 (beam_length, MAX_BEAM_LENGTH))
        except (KeyError, ValueError) as error:
            messagebox.showerror(u'\u8f93\u5165\u6709\u8bef', str(error), parent=root)
            return
        root.destroy()
        TriangleBracketPlacementTool.InstallNewInstance(
            l1, end_overhang, variant_key)

    def export_bom():
        output_path = export_end_welded_triangle_bracket_bom_json()
        if output_path is not None:
            messagebox.showinfo(
                u'\u5bfc\u51fa\u5b8c\u6210',
                u'\u7aef\u710a\u4e09\u89d2\u67b6\u6e05\u5355\u5df2\u5bfc\u51fa\uff1a\n%s' % output_path,
                parent=root)

    buttons = ttk.Frame(form)
    buttons.grid(row=7, column=0, columnspan=3, sticky='e', pady=(8, 0))
    ttk.Button(buttons, text=u'\u53d6\u6d88', command=root.destroy).grid(
        row=0, column=0, padx=(0, 8))
    ttk.Button(buttons, text=u'\u5bfc\u51fa JSON \u6e05\u5355', command=export_bom).grid(
        row=0, column=1, padx=(0, 8))
    ttk.Button(buttons, text=u'\u4e0b\u4e00\u6b65\uff1a\u70b9\u53d6\u710a\u63a5\u9762', command=generate).grid(
        row=0, column=2)
    root.mainloop()


if __name__ == '__main__':
    show_triangle_bracket_dialog()
