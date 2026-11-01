# -*- coding: utf-8 -*-
"""A1 U 型管卡**入口插件**的桩件自测（不需要 OPM / MicroStation）。

入口插件 ``A1-[U型管卡].py`` 里的 :func:`build_on_pick` 是"点选 → 定位 → 建模"
的分派中枢，它的两条口径必须写死不能漂：

* 点选**管道**：管径由 EC 公称直径自动查表 1；**放置中心 = 点击点在管轴上的投影**；
* 点选**辅助线（普通直线段）**：**点击点本身就是放置中心（管中心）**，不做投影；
  管径改用面板下拉的 DN。

本文件把 MSPy / bentley_ui / tkinter 的最小替身装好后导入入口插件，把
``builder.build_clamp`` 与 ``builder.attach_support_items`` 换成记录器，然后直接
调用 ``build_on_pick`` 断言**真正传给建模库的坐标与管径**。同时检查面板参数
解析（角度规整、DN 兜底、状态持久化键）与管道号透传。

运行：``python -B 管道支吊架/模块/tests/test_u_bolt_clamp_entry_selftest.py``
"""

from __future__ import division

import os
import sys
import types
import unittest


_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(_TESTS_DIR))
_GEOM_DIR = os.path.join(_PLUGIN_ROOT, '模块', 'U型管卡')
_UI_DIR = os.path.join(_PLUGIN_ROOT, '模块', '公共')
_ENTRY = os.path.join(_PLUGIN_ROOT, 'A1-[U型管卡].py')


# ---------------------------------------------------------------------------
# 替身：#1 MSPy（直接复用建模库那套桩件）
# ---------------------------------------------------------------------------

if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

import test_u_bolt_clamp_builder_selftest as _stub  # noqa: E402  装好 MSPy 替身
import U型管卡_几何 as geom  # noqa: E402


# ---------------------------------------------------------------------------
# 替身：#2 管道信息读取库（入口按文件路径加载它，这里换成内存模块）
# ---------------------------------------------------------------------------


def _install_fake_pipe_reader():
    """在入口的加载路径上放一个假 ``管道信息_读取.py``。

    入口用 ``importlib.util.spec_from_file_location`` 按文件加载，所以这里先在
    ``sys.modules`` 里塞一个同名模块 —— 入口的 ``_load_pipe_reader`` 会先查
    ``sys.modules`` 并 ``reload`` 它，从而拿到我们的替身。
    """
    module = types.ModuleType('管道信息_读取')
    module.fill_mspy_symbols = lambda names, namespace=None: []
    module.read_element_id = lambda handle: getattr(handle, 'element_id', None)

    def element_handle_by_id(element_id):
        return _FAKE_ELEMENTS.get(element_id)

    def project_onto_axis(point_mm, start_mm, end_mm):
        if point_mm is None or not start_mm or not end_mm:
            return point_mm
        dx = end_mm[0] - start_mm[0]
        dy = end_mm[1] - start_mm[1]
        dz = end_mm[2] - start_mm[2]
        length2 = dx * dx + dy * dy + dz * dz
        if length2 <= 1e-9:
            return point_mm
        t = ((point_mm[0] - start_mm[0]) * dx
             + (point_mm[1] - start_mm[1]) * dy
             + (point_mm[2] - start_mm[2]) * dz) / length2
        return (start_mm[0] + t * dx, start_mm[1] + t * dy, start_mm[2] + t * dz)

    module.element_handle_by_id = element_handle_by_id
    module.project_onto_axis = project_onto_axis
    module.pipe_placement_info = lambda handle, unit_override=None: (
        _FAKE_PLACEMENTS[handle.element_id])
    sys.modules['管道信息_读取'] = module
    return module


#: 假元素 ID -> 句柄；与 ``_FAKE_PLACEMENTS`` 配对使用。
_FAKE_ELEMENTS = {}
_FAKE_PLACEMENTS = {}


class _FakeHandle(object):
    def __init__(self, element_id):
        self.element_id = element_id


class _FakeAccuSnap(object):
    @staticmethod
    def GetInstance():
        return _FakeAccuSnap()

    @staticmethod
    def EnableSnap(_enabled):
        return None


def _install_extra_mspy_symbols():
    """补上入口在导入期需要的 MSPy 符号（PyCommandState / PyCadInputQueue / …）。"""
    import types as _types
    extra = {
        'PyCommandState': type('PyCommandState', (), {
            'StartDefaultCommand': staticmethod(lambda: None)})(),
        'PyCadInputQueue': type('PyCadInputQueue', (), {
            'PythonMainLoop': staticmethod(lambda: None)})(),
        'AccuSnap': _FakeAccuSnap,
        'ElementHandle': _FakeHandle,
        'WString': lambda value: value,
        'BentleyStatus': type('BentleyStatus', (), {'eSUCCESS': 0})(),
        'DgnElementSetTool': type('DgnElementSetTool', (), {
            'eUSES_SS_None': 0,
            '__init__': lambda self, tool_id=0: None,
            'InstallTool': lambda self: None,
            'GetToolId': lambda self: 0,
        }),
    }
    for name in ('MSPyBentley', 'MSPyBentleyGeom', 'MSPyDgnPlatform',
                 'MSPyDgnView', 'MSPyMstnPlatform'):
        module = sys.modules[name]
        for key, value in extra.items():
            setattr(module, key, value)


# ---------------------------------------------------------------------------
# 替身：#3 bentley_ui（只需玻璃面板的几个常量与控件名）
# ---------------------------------------------------------------------------


def _install_fake_bentley_ui():
    package = types.ModuleType('bentley_ui')
    package.__path__ = []
    names = ('BORDER', 'CARD', 'CARD_SOFT', 'FIELD', 'INK', 'MUTED',
             'UI_FONT', 'UI_FONT_BOLD', 'UI_FONT_SMALL')

    class _Widget(object):
        def pack(self, *args, **kwargs):
            return None

        def grid(self, *args, **kwargs):
            return None

    class GlassDialog(object):
        def __init__(self, title=''):
            self.title_text = title
            self.ui_state = {}

        def build_shell(self, title, subtitle):
            import tkinter as tk
            return tk.Frame()

        def restore_position(self):
            return None

        def protocol(self, *_args):
            return None

        def minsize(self, *_args):
            return None

    class RoundButton(_Widget):
        def __init__(self, *args, **kwargs):
            pass

    class SlimScrollbar(_Widget):
        def __init__(self, *args, **kwargs):
            pass

    for name in names:
        setattr(package, name, '#000000' if name.isupper() else ('TkDefaultFont', 9))
    package.GlassDialog = GlassDialog
    package.RoundButton = RoundButton
    package.SlimScrollbar = SlimScrollbar
    sys.modules['bentley_ui'] = package

    glass = types.ModuleType('bentley_ui.glass')
    sys.modules['bentley_ui.glass'] = glass
    return package


_install_fake_pipe_reader()
_install_extra_mspy_symbols()
_install_fake_bentley_ui()

if _GEOM_DIR not in sys.path:
    sys.path.insert(0, _GEOM_DIR)
if _UI_DIR not in sys.path:
    sys.path.insert(0, _UI_DIR)
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)


def _load_entry():
    """按文件路径加载入口插件（文件名含 '[' ']'，不能直接 import）。"""
    import importlib.util
    name = 'a1_u_bolt_clamp_entry'
    spec = importlib.util.spec_from_file_location(name, _ENTRY)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


entry = _load_entry()


# ---------------------------------------------------------------------------
# 记录建模库的调用
# ---------------------------------------------------------------------------


class _Recorder(object):
    """替换 ``builder.build_clamp`` / ``builder.attach_support_items``。"""

    def __init__(self):
        self.builds = []
        self.attaches = []
        self._real_build = entry.builder.build_clamp
        self._real_attach = entry.builder.attach_support_items

    def install(self):
        entry.builder.build_clamp = self.build_clamp
        entry.builder.attach_support_items = self.attach_support_items

    def uninstall(self):
        entry.builder.build_clamp = self._real_build
        entry.builder.attach_support_items = self._real_attach

    def build_clamp(self, center_mm, axis, dn=None, angle_deg=None,
                    insulation_mm=0.0, note=''):
        self.builds.append({'center': center_mm, 'axis': axis, 'dn': dn,
                            'angle': angle_deg, 'insulation': insulation_mm,
                            'note': note})
        return ('CELL-%d' % len(self.builds), '已生成（桩件）')

    def attach_support_items(self, cell, dn, geometry, angle_deg,
                             pipe_number='', nut_count=4):
        self.attaches.append({'cell': cell, 'dn': dn, 'angle': angle_deg,
                              'pipe_number': pipe_number})
        return 3


def _pipe_placement(element_id=1, nominal=100.0, start=(0.0, 0.0, 0.0),
                    end=(1000.0, 0.0, 0.0), insulation=None,
                    linenumber='P-1001-4"-A1A', warnings=()):
    """造一个"读到了 OpenPlant EC 实例"的管道 placement。"""
    axis = (1.0, 0.0, 0.0)
    values = {'nominal_diameter': nominal}
    if linenumber:
        values['linenumber'] = linenumber
    placement = {
        'ok': True, 'exact': True, 'elementId': element_id,
        'start_mm': start, 'end_mm': end, 'axis': axis,
        'center_mm': ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0,
                      (start[2] + end[2]) / 2.0),
        'source': 'geometry', 'orientation': '水平', 'slope_percent': 0.0,
        'nominal_diameter_mm': nominal, 'outside_diameter_mm': 114.3,
        'wall_thickness_mm': 6.02, 'insulation_thickness_mm': insulation,
        'warnings': list(warnings),
        'snapshot': {'ec': {'found': True}, 'values': values},
    }
    return placement


def _line_placement(element_id=2, start=(0.0, 0.0, 0.0),
                    end=(1000.0, 0.0, 0.0), warnings=()):
    """造一个"普通直线段（辅助线）"的 placement：没有 EC 实例。"""
    return {
        'ok': True, 'exact': True, 'elementId': element_id,
        'start_mm': start, 'end_mm': end, 'axis': (1.0, 0.0, 0.0),
        'center_mm': (500.0, 0.0, 0.0), 'source': 'geometry',
        'orientation': '水平', 'slope_percent': 0.0,
        'nominal_diameter_mm': None, 'outside_diameter_mm': None,
        'wall_thickness_mm': None, 'insulation_thickness_mm': None,
        'warnings': list(warnings),
        'snapshot': {'ec': {'found': False}, 'values': {}},
    }


class DispatchTests(unittest.TestCase):
    """点选分派：管道走投影、辅助线走点击点。"""

    def setUp(self):
        self.recorder = _Recorder()
        self.recorder.install()

    def tearDown(self):
        self.recorder.uninstall()

    def test_pipe_uses_nominal_diameter_and_projection(self):
        """管道：管径查表来自 EC 公称直径；放置中心 = 点击点在轴上的投影。"""
        placement = _pipe_placement(nominal=100.0)
        # 点击点在管外一点（y=200），投影后应落到轴上 (300, 0, 0)。
        _result, message = entry.build_on_pick(
            placement, (300.0, 200.0, 0.0), fallback_dn=50, angle_deg=0.0)
        build = self.recorder.builds[-1]
        self.assertEqual(build['dn'], 100)          # 自动查表，忽略兜底 50
        self.assertAlmostEqual(build['center'][0], 300.0)
        self.assertAlmostEqual(build['center'][1], 0.0)
        self.assertAlmostEqual(build['center'][2], 0.0)
        self.assertIn('DN100', build['note'])
        self.assertIn('管道公称直径', build['note'])
        # 管道号透传到清单写入。
        self.assertEqual(self.recorder.attaches[-1]['pipe_number'],
                         'P-1001-4"-A1A')
        self.assertEqual(self.recorder.attaches[-1]['dn'], 100)

    def test_pipe_falls_back_when_diameter_unmatched(self):
        """管道公称直径匹配不到表 1 时，退回面板 DN 并给出提示。"""
        placement = _pipe_placement(nominal=2000.0)
        _result, message = entry.build_on_pick(
            placement, (100.0, 0.0, 0.0), fallback_dn=150, angle_deg=0.0)
        self.assertEqual(self.recorder.builds[-1]['dn'], 150)
        self.assertIn('未匹配到表 1', self.recorder.builds[-1]['note'])

    def test_auxiliary_line_uses_click_point_verbatim(self):
        """辅助线：点击点**不投影**，原样作为放置中心；管径取面板 DN。"""
        placement = _line_placement()
        # 故意点一个明显偏离轴线的点（y=250）：辅助线口径下它必须原样成为中心。
        _result, message = entry.build_on_pick(
            placement, (300.0, 250.0, 0.0), fallback_dn=80, angle_deg=90.0)
        build = self.recorder.builds[-1]
        self.assertEqual(build['dn'], 80)
        self.assertAlmostEqual(build['center'][0], 300.0)
        self.assertAlmostEqual(build['center'][1], 250.0)
        self.assertAlmostEqual(build['center'][2], 0.0)
        self.assertAlmostEqual(build['angle'], 90.0)
        self.assertIn('点击点为放置中心', build['note'])
        self.assertEqual(self.recorder.attaches[-1]['dn'], 80)

    def test_auxiliary_line_filters_pipe_only_warnings(self):
        """直线段上"没有 EC / 没有公称直径"的提示属正常，不应转给用户。"""
        placement = _line_placement(warnings=(
            '没有找到 OpenPlant 管道实例。',
            '没有读到公称直径（NOMINAL_DIAMETER），管夹选型需人工确认。',
            '该元素确实有问题。'))
        _result, _message = entry.build_on_pick(
            placement, (0.0, 0.0, 0.0), fallback_dn=100, angle_deg=0.0)
        build = self.recorder.builds[-1]
        self.assertNotIn('没有找到 OpenPlant', build['note'])
        self.assertNotIn('没有读到公称直径', build['note'])
        self.assertIn('该元素确实有问题', build['note'])

    def test_missing_axis_rejected(self):
        placement = _line_placement()
        placement['axis'] = None
        with self.assertRaises(ValueError) as context:
            entry.build_on_pick(placement, (0.0, 0.0, 0.0), fallback_dn=100)
        self.assertIn('轴线', str(context.exception))

    def test_attach_can_be_disabled(self):
        """逃生开关 ITEM_TYPE_ATTACH=False：只出几何，不写清单。"""
        placement = _pipe_placement()
        entry.build_on_pick(placement, (100.0, 0.0, 0.0), fallback_dn=100,
                            angle_deg=0.0, attach=False)
        self.assertEqual(self.recorder.attaches, [])

    def test_insulation_passed_through(self):
        placement = _pipe_placement(insulation=60.0)
        entry.build_on_pick(placement, (100.0, 0.0, 0.0), fallback_dn=100,
                            angle_deg=0.0)
        self.assertAlmostEqual(self.recorder.builds[-1]['insulation'], 60.0)


class PanelParameterTests(unittest.TestCase):
    """面板参数解析（不建窗口，直接绕开 ``__init__`` 造一个面板替身）。

    替身**继承真正的面板类**，因此 ``current_dn`` / ``current_angle`` /
    ``persist_state`` 之间的内部调用关系（``self.current_dn()``）与实机一致，
    只把两个下拉的 ``StringVar`` 换成最简单的取值替身。
    """

    class _Var(object):
        def __init__(self, value=''):
            self._value = value

        def get(self):
            return self._value

        def set(self, value):
            self._value = value

    class _Panel(entry._ClampPanel):
        def __init__(self):
            # 刻意不调用 GlassDialog.__init__：本组测试只碰参数解析。
            self._dn_by_label = dict(
                (label, dn) for dn, label in geom.dn_choices())
            self._angle_by_label = dict(
                (label, value) for value, label in geom.angle_choices())
            self._dn = PanelParameterTests._Var()
            self._angle = PanelParameterTests._Var()

        def _label_for_dn(self, dn):
            return [text for text, key in self._dn_by_label.items()
                    if key == dn][0]

        def _label_for_angle(self, angle):
            return [text for text, value in self._angle_by_label.items()
                    if abs(value - angle) < 1e-9][0]

    def test_current_dn_falls_back(self):
        panel = self._Panel()
        panel._dn = self._Var('不存在的标签')
        self.assertEqual(panel.current_dn(), entry.DN)

    def test_current_dn_reads_selection(self):
        panel = self._Panel()
        panel._dn = self._Var(panel._label_for_dn(150))
        self.assertEqual(panel.current_dn(), 150)

    def test_current_angle_default_and_selection(self):
        panel = self._Panel()
        panel._angle = self._Var('不存在')
        self.assertEqual(panel.current_angle(), geom.DEFAULT_ANGLE_DEG)
        panel._angle = self._Var(panel._label_for_angle(270.0))
        self.assertAlmostEqual(panel.current_angle(), 270.0)

    def test_defaults_match_geometry_module(self):
        self.assertEqual(entry.DN, geom.DEFAULT_DN)
        self.assertEqual(entry.SUPPORT_TYPE, 'A1-[U型管卡]')
        self.assertEqual(entry.SUPPORT_CODE, 'A1_U_BOLT_CLAMP')
        self.assertEqual(entry._ClampPanel.STATE_KEY, 'A1UBoltClamp')

    def test_persist_state_keys(self):
        panel = self._Panel()
        panel._dn = self._Var(panel._label_for_dn(200))
        panel._angle = self._Var(panel._label_for_angle(45.0))
        state = {}
        panel.persist_state(state)
        self.assertEqual(state['dn'], 200)
        self.assertAlmostEqual(state['angle'], 45.0)

    def test_restore_state_reads_saved_values(self):
        panel = self._Panel()
        panel.ui_state = {'dn': 300, 'angle': 180.0}
        panel.restore_state()
        self.assertEqual(panel.current_dn(), 300)
        self.assertAlmostEqual(panel.current_angle(), 180.0)

    def test_restore_state_tolerates_garbage(self):
        panel = self._Panel()
        panel.ui_state = {'dn': '乱七八糟', 'angle': '不是数字'}
        panel.restore_state()
        self.assertEqual(panel.current_dn(), entry.DN)
        self.assertAlmostEqual(panel.current_angle(), geom.DEFAULT_ANGLE_DEG)

if __name__ == '__main__':
    unittest.main(verbosity=2)
