# -*- coding: utf-8 -*-
"""管道信息读取库的纯逻辑单测（不依赖 Bentley 运行时 / Qt）。

覆盖：属性单位标定与兜底、长度换算、由外径反查公称直径、走向判定、
报告排版（分组 / 单位 / 缺项 / 备注）与提示文字；并用假 EC 实例验证
属性读取与"管道实例"挑选逻辑（数值属性不会被当成文本、反之亦然）。
"""

from __future__ import division

import os
import sys
import unittest


_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULE_DIR = os.path.dirname(_TESTS_DIR)
_PLUGIN_DIR = os.path.dirname(_MODULE_DIR)
_INFO_DIR = os.path.join(_MODULE_DIR, '管道信息')
if _INFO_DIR not in sys.path:
    sys.path.insert(0, _INFO_DIR)

import 管道信息_读取 as reader  # noqa: E402


class ReaderApiSurfaceTests(unittest.TestCase):
    """入口脚本依赖的读取库接口必须齐全（防止两边改动不同步）。

    这里特别覆盖"MicroStation 会话里拿到旧模块对象"那次故障：入口脚本既依赖
    ``fill_mspy_symbols`` 这类新接口，也靠 ``READER_API_VERSION`` 判断磁盘上
    的文件是不是新版。
    """

    REQUIRED_API = (
        'READER_API_VERSION',
        'fill_mspy_symbols',
        'MSPY_SYMBOLS',
        'MSPY_OPTIONAL_SYMBOLS',
        'MSPY_MISSING',
        'UNIT_OPTIONS',
        'collect_pipe_info',
        'reapply_unit',
        'read_element_id',
        'element_handle_by_id',
        'active_dgn_model',
        'effective_centerline_z',
        'collect_instance_records',
        'pick_piping_record',
        'range_from_records',
        'dump_instances',
        'instance_property_names',
        'dump_element',
        'build_report_rows',
        'format_report_text',
        'pipe_placement_info',
        'extract_placement_info',
        'project_onto_axis',
        'placement_anchor',
    )

    def test_required_api_present(self):
        for name in self.REQUIRED_API:
            self.assertTrue(hasattr(reader, name),
                            '读取库缺少入口脚本依赖的接口：%s' % name)

    def test_api_version_matches_entry_expectation(self):
        with open(os.path.join(_PLUGIN_DIR, '管道信息查询.py'),
                  encoding='utf-8') as stream:
            source = stream.read()
        self.assertIn('REQUIRED_READER_API = %d' % reader.READER_API_VERSION,
                      source)


class DetectLengthScaleTests(unittest.TestCase):
    """属性长度 ↔ 几何长度标定。"""

    def test_stored_in_millimetres(self):
        result = reader.detect_length_scale(168.3, 168.3)
        self.assertIsNotNone(result)
        self.assertEqual(result['scale'], reader.SCALE_MM)
        self.assertEqual(result['label'], '毫米')
        self.assertAlmostEqual(result['error'], 0.0)

    def test_stored_in_metres(self):
        result = reader.detect_length_scale(0.1683, 168.3)
        self.assertIsNotNone(result)
        self.assertEqual(result['scale'], reader.SCALE_M)
        self.assertEqual(result['label'], '米')

    def test_small_deviation_still_calibrates(self):
        # 弯头 / 带坡度的管段，属性长度与几何长度略有出入仍应标定成功。
        result = reader.detect_length_scale(0.158, 168.3)
        self.assertIsNotNone(result)
        self.assertEqual(result['scale'], reader.SCALE_M)

    def test_unmatched_returns_none(self):
        self.assertIsNone(reader.detect_length_scale(0.1683, 500.0))

    def test_degenerate_inputs(self):
        self.assertIsNone(reader.detect_length_scale(None, 168.3))
        self.assertIsNone(reader.detect_length_scale(0.0, 168.3))
        self.assertIsNone(reader.detect_length_scale(168.3, 0.0))
        self.assertIsNone(reader.detect_length_scale('abc', 168.3))


class GuessLengthScaleTests(unittest.TestCase):

    def test_small_value_treated_as_metres(self):
        result = reader.guess_length_scale(0.1683)
        self.assertEqual(result['scale'], reader.SCALE_M)
        self.assertEqual(result['source'], 'heuristic')

    def test_large_value_treated_as_millimetres(self):
        result = reader.guess_length_scale(168.3)
        self.assertEqual(result['scale'], reader.SCALE_MM)
        self.assertEqual(result['source'], 'default')

    def test_missing_or_zero_value_defaults_to_millimetres(self):
        for value in (None, 0.0):
            result = reader.guess_length_scale(value)
            self.assertEqual(result['scale'], reader.SCALE_MM)
            self.assertEqual(result['source'], 'default')


class ResolveLengthUnitTests(unittest.TestCase):

    def test_auto_calibrated(self):
        result = reader.resolve_length_unit(0.1683, 168.3, 'auto')
        self.assertEqual(result['scale'], reader.SCALE_M)
        self.assertEqual(result['source'], 'calibrated')
        self.assertIsNone(result['warning'])

    def test_manual_override_wins(self):
        result = reader.resolve_length_unit(0.1683, 168.3, 'mm')
        self.assertEqual(result['scale'], reader.SCALE_MM)
        self.assertEqual(result['source'], 'manual')
        result = reader.resolve_length_unit(168.3, 168.3, 'm')
        self.assertEqual(result['scale'], reader.SCALE_M)
        self.assertEqual(result['source'], 'manual')

    def test_heuristic_fallback_warns(self):
        result = reader.resolve_length_unit(0.15, 800.0)
        self.assertEqual(result['scale'], reader.SCALE_M)
        self.assertEqual(result['source'], 'heuristic')
        self.assertIn('手动确认', result['warning'])

    def test_missing_length_warns(self):
        result = reader.resolve_length_unit(None, 168.3)
        self.assertIsNotNone(result['warning'])

    def test_to_mm(self):
        self.assertAlmostEqual(reader.to_mm(0.1683, reader.SCALE_M), 168.3)
        self.assertAlmostEqual(reader.to_mm(168.3, reader.SCALE_MM), 168.3)
        self.assertIsNone(reader.to_mm(None, reader.SCALE_MM))


class NearestDnTests(unittest.TestCase):

    def test_exact_series_values(self):
        self.assertEqual(reader.nearest_dn(168.3)['dn'], 150)
        self.assertEqual(reader.nearest_dn(219.1)['dn'], 200)
        self.assertEqual(reader.nearest_dn(609.6)['dn'], 600)
        self.assertEqual(reader.nearest_dn(558.8)['dn'], 550)

    def test_tolerance_boundary(self):
        # 175 mm 距 DN150（168.3）约 4%，超出 3% 容差 → 不是标准系列。
        self.assertIsNone(reader.nearest_dn(175.0))

    def test_invalid_inputs(self):
        self.assertIsNone(reader.nearest_dn(None))
        self.assertIsNone(reader.nearest_dn(0.0))
        self.assertIsNone(reader.nearest_dn(-10.0))

    def test_text_contains_dn_and_od(self):
        self.assertIn('DN150', reader.nearest_dn(168.3)['text'])


class OrientationTests(unittest.TestCase):

    def test_horizontal(self):
        self.assertEqual(reader.classify_orientation((0, 0, 0), (1000, 0, 0)),
                         ('水平', 0.0))

    def test_vertical(self):
        orientation, slope = reader.classify_orientation((0, 0, 0), (0, 0, 900))
        self.assertEqual(orientation, '竖直')
        self.assertIsNone(slope)

    def test_inclined_reports_slope(self):
        orientation, slope = reader.classify_orientation((0, 0, 0),
                                                         (1000, 0, 100))
        self.assertEqual(orientation, '倾斜')
        self.assertAlmostEqual(slope, 10.0)

    def test_degenerate(self):
        self.assertEqual(reader.classify_orientation((0, 0, 0), (0, 0, 0))[0],
                         '零长度')
        self.assertEqual(reader.classify_orientation(None, (0, 0, 0))[0],
                         '未知')


def _sample_info():
    """一份典型的"读到全部属性"的报告，用于排版测试。"""
    return {
        'elementId': 1234,
        'ec': {'schema': 'OpenPlant_3D', 'class': 'PIPE',
               'instanceId': 'abc', 'found': True},
        'unit': {'scale': reader.SCALE_M, 'label': '米',
                 'source': 'calibrated', 'warning': None},
        'raw': {'nominal_diameter': 0.15, 'outside_diameter': 0.1683,
                'wall_thickness': 0.0071, 'insulation_thickness': 0.05,
                'length': 0.5},
        'values': {'nominal_diameter': 150.0, 'outside_diameter': 168.3,
                   'wall_thickness': 7.1, 'insulation_thickness': 50.0,
                   'length': 500.0, 'linenumber': 'P-1001-6"-A1A',
                   'specification': 'mA1-OPM', 'material': 'ASTM A106 Gr.B',
                   'name': 'PIPE-01', 'insulation_material': 'Fiber Glass',
                   'nominal_diameter_run_end': None, 'elevation': None,
                   'component_name': None, 'nominal_size': None,
                   'material_mark': None, 'grade': None, 'spool_id': None,
                   'pipe_flange_type': None, 'shop_field': None},
        'geometry': {'start_mm': (1000.0, 2000.0, 3000.0),
                     'end_mm': (1500.0, 2000.0, 3000.0),
                     'length_mm': 500.0, 'centerline_z_mm': 3000.0,
                     'z_span_mm': 0.0, 'orientation': '水平',
                     'slope_percent': 0.0, 'length_confidence': 'high'},
        'derived': {'od_with_insulation_mm': 268.3,
                    'insulation_outer_radius_mm': 134.15,
                    'dn_from_od': 150,
                    'dn_from_od_text': 'DN150（外径 168.3 mm）',
                    'dn_consistent': True},
        'warnings': [],
        'notes': ['属性单位按……标定为米（误差 0.0%）。'],
        'baseWarnings': [],
    }


# ---------------------------------------------------------------------------
# 单位切换：在快照上纯计算，不再访问元素（面板切换单位走的就是这条路）
# ---------------------------------------------------------------------------


def _snapshot(raw_length=0.5, geometric_length=500.0):
    return {
        'elementId': 1,
        'ec': {'schema': 'OpenPlant_3D', 'class': 'PIPE',
               'instanceId': 'x', 'found': True},
        'raw': {'length': raw_length, 'nominal_diameter': 0.15,
                'nominal_diameter_run_end': None, 'outside_diameter': 0.1683,
                'wall_thickness': 0.0071, 'insulation_thickness': 0.05,
                'elevation': None},
        'values': {'linenumber': 'P-1001'},
        'geometry': {'length_mm': geometric_length, 'centerline_z_mm': 3000.0},
        'derived': {},
        'warnings': [],
        'notes': [],
        'baseWarnings': ['示例基础提示'],
    }


class FillMspySymbolsTests(unittest.TestCase):
    """MSPy 符号补齐：常见坑是 ``from MSPyX import *`` 不导出 ISessionMgr 这类符号。"""

    def setUp(self):
        import types
        self._saved = {name: sys.modules.get(name)
                       for name in reader.MSPY_MODULES}
        fake = types.ModuleType('MSPyFake')
        fake.ISessionMgr = 'FAKE_SESSION'
        fake.EditElementHandle = 'FAKE_HANDLE'
        fake.NoneValuedSymbol = None
        sys.modules['MSPyDgnView'] = fake

    def tearDown(self):
        for name, module in self._saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    def test_binds_symbols_found_in_loaded_modules(self):
        namespace = {}
        bound = reader.fill_mspy_symbols(
            ('ISessionMgr', 'EditElementHandle'), namespace)
        self.assertEqual(sorted(bound), ['EditElementHandle', 'ISessionMgr'])
        self.assertEqual(namespace['ISessionMgr'], 'FAKE_SESSION')
        self.assertEqual(namespace['EditElementHandle'], 'FAKE_HANDLE')

    def test_unknown_symbol_is_left_unbound(self):
        namespace = {}
        bound = reader.fill_mspy_symbols(('NoSuchSymbol',), namespace)
        self.assertEqual(bound, [])
        self.assertNotIn('NoSuchSymbol', namespace)

    def test_none_valued_attribute_is_not_treated_as_found(self):
        # 有的模块对未知属性返回 None 而不抛异常——那不是"找到了"。
        namespace = {}
        bound = reader.fill_mspy_symbols(('NoneValuedSymbol',), namespace)
        self.assertEqual(bound, [])
        self.assertNotIn('NoneValuedSymbol', namespace)

    def test_existing_binding_is_kept(self):
        namespace = {'ISessionMgr': 'KEEP_ME'}
        bound = reader.fill_mspy_symbols(('ISessionMgr',), namespace)
        self.assertEqual(bound, [])
        self.assertEqual(namespace['ISessionMgr'], 'KEEP_ME')

    def test_reports_missing_when_no_module_loaded(self):
        for name in reader.MSPY_MODULES:
            sys.modules.pop(name, None)
        namespace = {}
        self.assertEqual(
            reader.fill_mspy_symbols(('ISessionMgr',), namespace), [])
        self.assertNotIn('ISessionMgr', namespace)

    def test_reader_symbol_list_covers_what_it_uses(self):
        # 读取库里用到的 Bentley 符号都必须在补齐清单里，否则会漏绑。
        with open(os.path.join(_INFO_DIR, '管道信息_读取.py'),
                  encoding='utf-8') as stream:
            source = stream.read()
        for name in ('ISessionMgr', 'EditElementHandle', 'ICurvePathQuery',
                     'DgnECManager', 'ECValue', 'ECValuesCollection',
                     'WString', 'ECObjectsStatus', 'DgnECHostType'):
            self.assertIn(name, reader.MSPY_SYMBOLS)
            self.assertIn(name, source)


class ActiveDgnModelTests(unittest.TestCase):
    """活动 DGN 模型的两种取法（不同版本"标准写法"不一样）都要能走通。"""

    def setUp(self):
        self._had = hasattr(reader, 'ISessionMgr')
        self._saved = getattr(reader, 'ISessionMgr', None)

    def tearDown(self):
        if self._had:
            reader.ISessionMgr = self._saved
        elif hasattr(reader, 'ISessionMgr'):
            delattr(reader, 'ISessionMgr')

    def test_prefers_get_active_dgn_model(self):
        class Session(object):
            @staticmethod
            def GetActiveDgnModel():
                return 'MODEL-A'

            class ActiveDgnModelRef(object):
                @staticmethod
                def GetDgnModel():
                    return 'MODEL-B'

        reader.ISessionMgr = Session
        self.assertEqual(reader.active_dgn_model(), 'MODEL-A')

    def test_falls_back_to_model_ref(self):
        class Ref(object):
            @staticmethod
            def GetDgnModel():
                return 'MODEL-B'

        class Session(object):
            @staticmethod
            def GetActiveDgnModel():
                raise RuntimeError('这个版本没有该接口')

            ActiveDgnModelRef = Ref

        reader.ISessionMgr = Session
        self.assertEqual(reader.active_dgn_model(), 'MODEL-B')

    def test_returns_none_when_session_has_no_such_api(self):
        class Session(object):
            pass

        reader.ISessionMgr = Session
        self.assertIsNone(reader.active_dgn_model())

    def test_returns_none_when_symbol_missing(self):
        # 这正是之前那次故障：ISessionMgr 整个没绑上，应该是"取不到"而不是崩掉。
        if hasattr(reader, 'ISessionMgr'):
            delattr(reader, 'ISessionMgr')
        self.assertIsNone(reader.active_dgn_model())


class ReadElementIdTests(unittest.TestCase):
    def test_attribute_style_handle(self):
        class Handle(object):
            ElementId = 42
        self.assertEqual(reader.read_element_id(Handle()), 42)

    def test_method_style_handle(self):
        class Handle(object):
            def GetElementId(self):
                return 77
        self.assertEqual(reader.read_element_id(Handle()), 77)

    def test_unreadable_handle_returns_none(self):
        class Handle(object):
            @property
            def ElementId(self):
                raise RuntimeError('无效句柄')
        self.assertIsNone(reader.read_element_id(Handle()))


class ReapplyUnitTests(unittest.TestCase):

    def test_auto_calibrates_to_metres(self):
        snapshot = reader.reapply_unit(_snapshot(), 'auto')
        self.assertEqual(snapshot['unit']['label'], '米')
        self.assertAlmostEqual(snapshot['values']['outside_diameter'], 168.3)
        self.assertAlmostEqual(snapshot['values']['length'], 500.0)
        self.assertTrue(snapshot['notes'])

    def test_manual_override_to_millimetres(self):
        snapshot = reader.reapply_unit(_snapshot(), 'mm')
        self.assertEqual(snapshot['unit']['source'], 'manual')
        self.assertAlmostEqual(snapshot['values']['outside_diameter'], 0.1683)

    def test_switching_back_and_forth_is_stable(self):
        snapshot = _snapshot()
        reader.reapply_unit(snapshot, 'mm')
        first = list(snapshot['warnings'])
        reader.reapply_unit(snapshot, 'auto')
        reader.reapply_unit(snapshot, 'mm')
        # 反复切换不叠加提示、不丢基础提示。
        self.assertEqual(snapshot['warnings'], first)
        self.assertIn('示例基础提示', snapshot['warnings'])

    def test_base_warnings_survive(self):
        snapshot = reader.reapply_unit(_snapshot(), 'auto')
        self.assertIn('示例基础提示', snapshot['warnings'])

    def test_text_values_preserved(self):
        snapshot = reader.reapply_unit(_snapshot(), 'm')
        self.assertEqual(snapshot['values']['linenumber'], 'P-1001')

    def test_derived_recomputed(self):
        snapshot = reader.reapply_unit(_snapshot(), 'auto')
        self.assertAlmostEqual(
            snapshot['derived']['od_with_insulation_mm'], 268.3)
        self.assertIs(snapshot['derived']['dn_consistent'], True)

    def test_uncalibratable_length_falls_back_with_warning(self):
        snapshot = reader.reapply_unit(_snapshot(raw_length=0.5,
                                                geometric_length=900.0), 'auto')
        self.assertEqual(snapshot['unit']['source'], 'heuristic')
        self.assertTrue(any('手动确认' in text
                            for text in snapshot['warnings']))

    def test_no_geometry_still_works(self):
        snapshot = _snapshot()
        snapshot['geometry'] = None
        reader.reapply_unit(snapshot, 'auto')
        self.assertIsNotNone(snapshot['unit'])


class PlacementInfoTests(unittest.TestCase):
    """放置接口：管段起点 + 公称直径 + 保温厚度，供管夹等放置类插件调用。"""

    def test_extracts_axis_size_and_anchor(self):
        info = reader.extract_placement_info(_sample_info())
        self.assertTrue(info['ok'])
        self.assertTrue(info['exact'])
        self.assertEqual(info['start_mm'], (1000.0, 2000.0, 3000.0))
        self.assertEqual(info['end_mm'], (1500.0, 2000.0, 3000.0))
        self.assertEqual(info['axis'], (1.0, 0.0, 0.0))
        self.assertEqual(info['center_mm'], (1250.0, 2000.0, 3000.0))
        self.assertEqual(info['source'], 'geometry')
        self.assertAlmostEqual(info['nominal_diameter_mm'], 150.0)
        self.assertAlmostEqual(info['outside_diameter_mm'], 168.3)
        self.assertAlmostEqual(info['wall_thickness_mm'], 7.1)
        self.assertAlmostEqual(info['insulation_thickness_mm'], 50.0)
        self.assertEqual(info['orientation'], '水平')
        self.assertEqual(info['slope_percent'], 0.0)

    def test_step_slope_passed_through(self):
        snapshot = _sample_info()
        snapshot['geometry'].update(
            {'start_mm': (0.0, 0.0, 0.0), 'end_mm': (100.0, 0.0, 10.0),
             'orientation': '倾斜', 'slope_percent': 10.0})
        info = reader.extract_placement_info(snapshot)
        self.assertEqual(info['orientation'], '倾斜')
        self.assertAlmostEqual(info['slope_percent'], 10.0)

    def test_project_onto_axis_returns_click_anchor(self):
        info = reader.extract_placement_info(_sample_info())
        # 点击点稍偏离轴线（Y=2500），投影后落在轴线上（Y=2000）。
        anchor = reader.placement_anchor(info, (1200.0, 2500.0, 3000.0))
        self.assertEqual(anchor, (1200.0, 2000.0, 3000.0))

    def test_anchor_falls_back_to_center_without_click_point(self):
        info = reader.extract_placement_info(_sample_info())
        self.assertEqual(reader.placement_anchor(info), info['center_mm'])

    def test_missing_axis_falls_back_to_bbox_axis(self):
        # 单元格（Cell）类管道没有中心线曲线：按包围盒最长边近似管轴。
        snapshot = _sample_info()
        snapshot['geometry'] = None
        snapshot['bbox'] = {'center_mm': (0.0, 0.0, 2500.0),
                            'span_mm': (300.0, 160.0, 200.0),
                            'max_span_mm': 300.0, 'source': '实例 1（PIPE）'}
        info = reader.extract_placement_info(snapshot)
        self.assertTrue(info['ok'])
        self.assertFalse(info['exact'])
        self.assertEqual(info['source'], 'bbox')
        self.assertEqual(info['axis'], (1.0, 0.0, 0.0))
        self.assertEqual(info['start_mm'], (-150.0, 0.0, 2500.0))
        self.assertEqual(info['end_mm'], (150.0, 0.0, 2500.0))
        self.assertEqual(info['center_mm'], (0.0, 0.0, 2500.0))
        self.assertEqual(info['orientation'], '水平')
        self.assertEqual(info['slope_percent'], 0.0)
        self.assertTrue(any('包围盒' in text for text in info['warnings']))

    def test_no_axis_and_no_bbox_warns_and_is_not_ok(self):
        snapshot = _sample_info()
        snapshot['geometry'] = None
        info = reader.extract_placement_info(snapshot)
        self.assertFalse(info['ok'])
        self.assertIsNone(info['axis'])
        self.assertIsNone(info['start_mm'])
        self.assertIsNone(info['orientation'])
        self.assertIsNone(info['slope_percent'])
        self.assertTrue(any('无法定位' in text for text in info['warnings']))

    def test_axis_from_bbox_picks_longest_edge(self):
        start, end, axis = reader.axis_from_bbox(
            {'center_mm': (10.0, 20.0, 30.0), 'span_mm': (5.0, 80.0, 5.0)})
        self.assertEqual(axis, (0.0, 1.0, 0.0))
        self.assertEqual(start, (10.0, -20.0, 30.0))
        self.assertEqual(end, (10.0, 60.0, 30.0))
        self.assertEqual(reader.axis_from_bbox({}), (None, None, None))

    def test_missing_nominal_diameter_warns(self):
        snapshot = _sample_info()
        snapshot['values']['nominal_diameter'] = None
        info = reader.extract_placement_info(snapshot)
        self.assertIsNone(info['nominal_diameter_mm'])
        self.assertTrue(any('公称直径' in text for text in info['warnings']))

    def test_uninsulated_pipe_has_none_thickness_without_warning(self):
        snapshot = _sample_info()
        snapshot['values']['insulation_thickness'] = None
        info = reader.extract_placement_info(snapshot)
        self.assertIsNone(info['insulation_thickness_mm'])
        self.assertFalse(any('保温' in text for text in info['warnings']))

    def test_project_onto_axis_degenerate_returns_input(self):
        point = (1.0, 2.0, 3.0)
        self.assertEqual(reader.project_onto_axis(point, None, None), point)
        self.assertEqual(
            reader.project_onto_axis(point, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            point)

    def test_axis_direction_is_normalised(self):
        self.assertEqual(
            reader._axis_direction((0.0, 0.0, 0.0), (0.0, 0.0, 100.0)),
            (0.0, 0.0, 1.0))
        self.assertIsNone(reader._axis_direction(None, (0.0, 0.0, 0.0)))


class ReportRowsTests(unittest.TestCase):

    def _row_map(self, rows):
        return {(group, item): (value, note)
                for group, item, value, note in rows}

    def test_groups_in_expected_order(self):
        rows = reader.build_report_rows(_sample_info())
        groups = []
        for group, _item, _value, _note in rows:
            if not groups or groups[-1] != group:
                groups.append(group)
        self.assertEqual(groups, ['元素', '单位', '管道属性', '几何', '推算'])

    def test_length_values_and_raw_note(self):
        rows = self._row_map(reader.build_report_rows(_sample_info()))
        self.assertEqual(rows[('管道属性', '外径')], ('168.3 mm', '原值 0.1683'))
        self.assertEqual(rows[('管道属性', '保温厚度')], ('50.0 mm', '原值 0.05'))
        self.assertEqual(rows[('管道属性', '公称直径')], ('150.0 mm', '原值 0.15'))

    def test_text_values_only_when_present(self):
        rows = self._row_map(reader.build_report_rows(_sample_info()))
        self.assertEqual(rows[('管道属性', '管线号')][0], 'P-1001-6"-A1A')
        self.assertNotIn(('管道属性', '材质代号'), rows)

    def test_geometry_rows(self):
        rows = self._row_map(reader.build_report_rows(_sample_info()))
        self.assertEqual(rows[('几何', '中心线标高')][0], '3000.0 mm')
        self.assertEqual(rows[('几何', '起点')][0], '(1000.0, 2000.0, 3000.0)')
        self.assertEqual(rows[('几何', '走向')][0], '水平')

    def test_derived_rows(self):
        rows = self._row_map(reader.build_report_rows(_sample_info()))
        self.assertEqual(rows[('推算', '保温后外径')][0], '268.3 mm')
        self.assertEqual(rows[('推算', '保温层外半径')][0], '134.2 mm')
        self.assertEqual(rows[('推算', '由外径反查公称直径')][0],
                         'DN150（外径 168.3 mm）')
        self.assertEqual(rows[('推算', '由外径反查公称直径')][1],
                         '与属性公称直径一致')

    def test_missing_values_render_dash(self):
        info = _sample_info()
        info['values']['outside_diameter'] = None
        info['raw']['outside_diameter'] = None
        rows = self._row_map(reader.build_report_rows(info))
        self.assertEqual(rows[('管道属性', '外径')], ('—', ''))

    def test_no_ec_instance(self):
        info = _sample_info()
        info['ec'] = {'schema': None, 'class': None, 'instanceId': None,
                      'found': False}
        info['values'] = {}
        info['raw'] = {}
        rows = self._row_map(reader.build_report_rows(info))
        self.assertEqual(rows[('元素', 'EC 实例')][0], '未找到管道实例')

    def test_no_geometry(self):
        info = _sample_info()
        info['geometry'] = None
        rows = self._row_map(reader.build_report_rows(info))
        self.assertEqual(rows[('几何', '轴线几何')][0], '读取失败')

    def test_unit_source_text(self):
        info = _sample_info()
        rows = self._row_map(reader.build_report_rows(info))
        self.assertEqual(rows[('单位', '属性长度单位')],
                         ('米', '由几何长度自动标定'))
        info['unit'] = {'scale': reader.SCALE_M, 'label': '米',
                        'source': 'heuristic', 'warning': 'w'}
        rows = self._row_map(reader.build_report_rows(info))
        self.assertEqual(rows[('单位', '属性长度单位')][1],
                         '兜底规则判断，建议手动确认')


class FormatReportTextTests(unittest.TestCase):

    def test_contains_groups_and_warnings(self):
        info = _sample_info()
        info['warnings'] = ['示例提示']
        text = reader.format_report_text(info)
        self.assertIn('[管道属性] 外径：168.3 mm（原值 0.1683）', text)
        self.assertIn('[提示] 示例提示', text)

    def test_contains_notes(self):
        text = reader.format_report_text(_sample_info())
        self.assertIn('[说明] 属性单位按', text)


# ---------------------------------------------------------------------------
# 假 EC 运行时：在纯 CPython 下验证属性读取与实例挑选
# ---------------------------------------------------------------------------


class _FakeStatus(object):
    """状态码替身：成功状态为单例，失败状态与之不相等。"""

    def __init__(self, ok=False):
        self.ok = ok

    def __eq__(self, other):
        return isinstance(other, _FakeStatus) and self.ok == other.ok

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.ok)


# 与被测代码里 ECValue / ECObjectsStatus 的用法保持一致。
_FakeStatus.eECOBJECTS_STATUS_Success = _FakeStatus(True)


class _FakeECValue(object):
    """ECValue 替身：只保留被测代码用到的取值接口。"""

    def __init__(self):
        self.value = None

    def IsNull(self):
        return self.value is None

    def GetDouble(self):
        if isinstance(self.value, bool) or not isinstance(self.value,
                                                          (int, float)):
            raise TypeError('不是数值属性')
        return float(self.value)

    def GetInteger(self):
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise TypeError('不是整数属性')
        return self.value

    def GetString(self):
        if isinstance(self.value, (int, float)) and not isinstance(
                self.value, bool):
            raise TypeError('不是文本属性')
        return str(self.value)


class _FakeSchema(object):

    def __init__(self, name):
        self._name = name

    def GetName(self):
        return self._name


class _FakeClass(object):

    def __init__(self, schema, class_name):
        self._schema = _FakeSchema(schema)
        self._name = class_name

    def GetName(self):
        return self._name

    def GetSchema(self):
        return self._schema


class _FakeInstance(object):

    def __init__(self, schema, class_name, properties):
        self._class = _FakeClass(schema, class_name)
        self.properties = properties

    def GetClass(self):
        return self._class

    def GetValue(self, ec_value, property_name):
        if property_name not in self.properties:
            return _FakeStatus()
        ec_value.value = self.properties[property_name]
        return _FakeStatus.eECOBJECTS_STATUS_Success

    def property_names(self):
        """模拟"实例上实际存在的属性名"。"""
        return set(self.properties)


class _FakeAccessor(object):

    def __init__(self, name):
        self._name = name

    def GetManagedAccessString(self):
        return self._name


class _FakeValue(object):

    def __init__(self, raw):
        self._raw = raw

    def IsStruct(self):
        return False

    def IsArray(self):
        return False

    def ToString(self):
        return str(self._raw)


class _FakePropertyValue(object):

    def __init__(self, name, raw=None):
        self._name = name
        self._raw = raw

    def GetValueAccessor(self):
        return _FakeAccessor(self._name)

    def GetValue(self):
        return _FakeValue(self._raw)


class _FakeECValuesCollection(object):
    """ECValuesCollection 替身：只支持枚举属性名与文本取值。"""

    @staticmethod
    def Create(instance):
        return [_FakePropertyValue(name, instance.properties[name])
                for name in sorted(instance.property_names())]


class _FakeRuntime(unittest.TestCase):
    """把 MSPy 的 ECValue / ECObjectsStatus / ECValuesCollection 换成替身。"""

    def setUp(self):
        self._saved = (getattr(reader, 'ECValue', None),
                       getattr(reader, 'ECObjectsStatus', None),
                       getattr(reader, 'ECValuesCollection', None))
        reader.ECValue = _FakeECValue
        reader.ECObjectsStatus = _FakeStatus
        reader.ECValuesCollection = _FakeECValuesCollection

    def tearDown(self):
        (reader.ECValue, reader.ECObjectsStatus,
         reader.ECValuesCollection) = self._saved


class _FakeQueryRuntime(_FakeRuntime):
    """在 _FakeRuntime 之上再装一套 EC 查询链路替身。"""

    QUERY_NAMES = ('DgnECManager', 'ECQuery', 'ECQueryProcessFlags',
                   'FindInstancesScope', 'FindInstancesScopeOption',
                   'DgnECHostType')

    def setUp(self):
        super().setUp()
        self._saved_query = {name: getattr(reader, name, None)
                             for name in self.QUERY_NAMES}
        # 记录遍历时取过哪些下标，用来验证"直接遍历、不物化"。
        self.iterated = []

    def tearDown(self):
        for name, value in self._saved_query.items():
            if value is None:
                if hasattr(reader, name):
                    delattr(reader, name)
            else:
                setattr(reader, name, value)
        super().tearDown()

    def install_instances(self, instances, collection=None):
        """装好查询替身；``collection`` 为 None 时用可枚举对象包住实例列表。"""
        test = self

        class Enumerable(object):
            """模拟 ``collection[0]``：按下标取值，越界抛 IndexError。"""

            def __init__(self, items):
                self._items = list(items)

            def __getitem__(self, index):
                # 越界探测也记录：遍历两遍会看到两组 0/1，据此验证"只遍历一次"。
                test.iterated.append(index)
                if index >= len(self._items):
                    raise IndexError(index)
                return self._items[index]

        payload = (Enumerable(instances),) if collection is None else collection

        class Manager(object):
            def FindInstances(self, scope, query):
                return payload

        class FakeDgnECManager(object):
            @staticmethod
            def GetManager():
                return Manager()

        class FakeECQuery(object):
            @staticmethod
            def CreateQuery(flag):
                return 'QUERY'

        class FakeFlags(object):
            eECQUERY_PROCESS_SearchAllClasses = 'FLAG'

        class FakeScope(object):
            @staticmethod
            def CreateScope(handle, option):
                return 'SCOPE'

        reader.DgnECManager = FakeDgnECManager
        reader.ECQuery = FakeECQuery
        reader.ECQueryProcessFlags = FakeFlags
        reader.FindInstancesScope = FakeScope
        reader.FindInstancesScopeOption = lambda host_type: ('OPT', host_type)
        reader.DgnECHostType = type('FakeHostType', (), {'eElement': 'ELEM'})


class CollectInstanceRecordsTests(_FakeQueryRuntime):
    """查询 + 遍历 + 取值必须在同一个函数里完成，且把实例读成纯 Python 记录。

    这是多轮崩溃后定下的铁律：实例只在**那次遍历**内有效，一旦被 ``list()``
    物化或带出遍历，再访问 ``GetClass()`` / 枚举属性就会让 OPM 直接崩溃。
    """

    def test_reads_each_instance_into_plain_records(self):
        cell = _FakeInstance('DgnElementSchema', 'NormalCellElement', {
            'RangeLow': '1715.7mm, 1376.5mm, -134.1mm',
            'RangeHigh': '4487.3mm, 1644.8mm, 134.2mm'})
        pipe = _FakeInstance('OpenPlant_3D', 'PIPE', {
            'NOMINAL_DIAMETER': 150.0, 'OUTSIDE_DIAMETER': 168.3,
            'LENGTH': 2771.57, 'LINENUMBER': 'P-1'})
        self.install_instances([cell, pipe])

        records = reader.collect_instance_records('HANDLE')

        self.assertEqual(len(records), 2)
        self.assertEqual([r['class'] for r in records],
                         ['NormalCellElement', 'PIPE'])
        # 记录里绝不能残留 Bentley 实例对象。
        for record in records:
            self.assertNotIn('instance', record)
            self.assertIsInstance(record['available'], set)
        self.assertAlmostEqual(records[1]['raw']['outside_diameter'], 168.3)
        self.assertEqual(records[1]['values']['linenumber'], 'P-1')
        self.assertEqual(records[1]['schema'], 'OpenPlant_3D')

    def test_range_texts_are_captured(self):
        cell = _FakeInstance('DgnElementSchema', 'NormalCellElement', {
            'RangeLow': '0mm, 0mm, -134.1mm',
            'RangeHigh': '100mm, 10mm, 134.2mm'})
        self.install_instances([cell])
        records = reader.collect_instance_records('HANDLE')
        self.assertEqual(records[0]['rangeTexts']['RangeLow'],
                         '0mm, 0mm, -134.1mm')

    def test_iterates_without_materialising(self):
        pipe = _FakeInstance('OpenPlant_3D', 'PIPE', {'LENGTH': 100.0})
        self.install_instances([pipe])
        reader.collect_instance_records('HANDLE')
        # 直接遍历（0、1 依次取，1 越界结束），不是 list() 先物化。
        self.assertEqual(self.iterated, [0, 1])

    def test_no_collection_yields_no_records(self):
        self.install_instances([], collection=None)
        self.assertEqual(reader.collect_instance_records('HANDLE'), [])

    def test_query_failure_yields_no_records(self):
        self.install_instances([], collection=None)
        reader.DgnECManager = type('Broken', (), {
            'GetManager': staticmethod(
                lambda: type('M', (), {'FindInstances': lambda s, sc, q:
                                       (_ for _ in ()).throw(
                                           RuntimeError('查询炸了'))})())})
        self.assertEqual(reader.collect_instance_records('HANDLE'), [])


class RangeFromRecordsTests(unittest.TestCase):
    """包围盒从记录里取（纯函数），供 Cell 类管道兜底。"""

    def test_builds_range_from_record_texts(self):
        records = [{'index': 1, 'class': 'NormalCellElement',
                    'rangeTexts': {'RangeLow': '1715.7mm, 1376.5mm, -134.1mm',
                                   'RangeHigh': '4487.3mm, 1644.8mm, 134.2mm'}}]
        info = reader.range_from_records(records)
        self.assertAlmostEqual(info['max_span_mm'], 2771.6)
        self.assertAlmostEqual(info['center_mm'][2], 0.05)
        self.assertIn('NormalCellElement', info['source'])

    def test_none_when_no_range_texts(self):
        self.assertIsNone(reader.range_from_records(
            [{'index': 1, 'class': 'PIPE', 'rangeTexts': {}}]))


class LengthTextParsingTests(unittest.TestCase):
    """元素范围属性是"数值 + 单位"的文本，要连单位一起换算。"""

    def test_parses_real_range_text(self):
        # 取自实际导出：元素 6029 的 RangeLow。
        self.assertEqual(
            reader.parse_length_values('1715.7mm, 1376.5mm, -134.1mm'),
            [1715.7, 1376.5, -134.1])

    def test_millimetre_suffix_is_not_read_as_metre(self):
        # "mm" 必须先于 "m" 匹配，否则 1000mm 会变成 1000m。
        self.assertEqual(reader.parse_length_values('1000 mm'), [1000.0])

    def test_metre_and_inch_suffixes(self):
        self.assertEqual(reader.parse_length_values('1.5m'), [1500.0])
        self.assertAlmostEqual(reader.parse_length_values('2 in')[0], 50.8)

    def test_unit_letters_inside_words_are_ignored(self):
        # "unknown" 里的 m 不能被当成米。
        self.assertEqual(reader.detect_text_unit_scale('unknown'), 1.0)

    def test_empty_or_none(self):
        self.assertEqual(reader.parse_length_values(''), [])
        self.assertEqual(reader.parse_length_values(None), [])

    def test_build_range_info(self):
        info = reader.build_range_info('1715.7mm, 1376.5mm, -134.1mm',
                                       '4487.3mm, 1644.8mm, 134.2mm')
        self.assertAlmostEqual(info['center_mm'][0], 3101.5)
        self.assertAlmostEqual(info['center_mm'][2], 0.05)
        # X 跨度 = 管段长度；另两轴 = 外径 + 2×保温厚度。
        self.assertAlmostEqual(info['span_mm'][0], 2771.6)
        self.assertAlmostEqual(info['span_mm'][1], 268.3)
        self.assertAlmostEqual(info['max_span_mm'], 2771.6)

    def test_build_range_info_rejects_bad_text(self):
        self.assertIsNone(reader.build_range_info('无', '无'))
        self.assertIsNone(reader.build_range_info(None, None))


class FiniteValueTests(unittest.TestCase):
    """GetDouble 对字符串属性返回 nan（实测 LINENUMBER），必须归一成"没有值"。"""

    def test_nan_and_inf_become_none(self):
        self.assertIsNone(reader._finite_or_none(float('nan')))
        self.assertIsNone(reader._finite_or_none(float('inf')))
        self.assertIsNone(reader._finite_or_none(None))

    def test_normal_values_pass_through(self):
        self.assertEqual(reader._finite_or_none(168.3), 168.3)
        self.assertEqual(reader._finite_or_none(0.0), 0.0)

    def test_to_mm_drops_nan(self):
        self.assertIsNone(reader.to_mm(float('nan'), 1.0))
        self.assertIsNone(reader.to_mm(0.0, 1.0) or None)


def _real_pipe_snapshot():
    """按元素 6029 的**真实**导出数据构造（单位是毫米）。

    来源：EC 属性导出 20260919_135527.txt
        RangeLow  = 1715.7mm, 1376.5mm, -134.1mm
        RangeHigh = 4487.3mm, 1644.8mm, 134.2mm
        OUTSIDE_DIAMETER = 168.3 / NOMINAL_DIAMETER = 150.0
        INSULATION_THICKNESS = 50.0 / WALL_THICKNESS = 7.1
        LENGTH = 2771.5660912882795 / UNIT_OF_MEASURE = MM
    """
    return {
        'elementId': 6029,
        'ec': {'schema': 'OpenPlant_3D', 'class': 'PIPE',
               'instanceId': 'x', 'found': True},
        'raw': {'length': 2771.5660912882795, 'outside_diameter': 168.3,
                'nominal_diameter': 150.0, 'nominal_diameter_run_end': 150.0,
                'wall_thickness': 7.1, 'insulation_thickness': 50.0,
                'elevation': 0.0},
        'values': {'linenumber': '?-?-SS-0001-A1B-150-COLD_CONSERVATION',
                   'material': '20#', 'specification': 'A1B',
                   'insulation_material': 'COLD_CONSERVATION'},
        'geometry': None,
        'bbox': reader.build_range_info('1715.7mm, 1376.5mm, -134.1mm',
                                        '4487.3mm, 1644.8mm, 134.2mm'),
        'derived': {}, 'warnings': [], 'notes': [], 'baseWarnings': [],
    }


class RealElement6029Tests(unittest.TestCase):
    """用真实元素 6029 的数据回归：单位标定、推算、包围盒兜底。"""

    def test_calibrates_to_millimetres_from_bbox(self):
        # 没有曲线时用包围盒最长边（≈管段长度）当标定基准。
        snapshot = reader.reapply_unit(_real_pipe_snapshot(), 'auto')
        self.assertEqual(snapshot['unit']['source'], 'calibrated')
        self.assertEqual(snapshot['unit']['label'], '毫米')

    def test_length_values_are_millimetres(self):
        snapshot = reader.reapply_unit(_real_pipe_snapshot(), 'auto')
        values = snapshot['values']
        self.assertAlmostEqual(values['outside_diameter'], 168.3)
        self.assertAlmostEqual(values['nominal_diameter'], 150.0)
        self.assertAlmostEqual(values['wall_thickness'], 7.1)
        self.assertAlmostEqual(values['insulation_thickness'], 50.0)
        self.assertAlmostEqual(values['length'], 2771.566, places=2)

    def test_derived_values(self):
        snapshot = reader.reapply_unit(_real_pipe_snapshot(), 'auto')
        derived = snapshot['derived']
        self.assertAlmostEqual(derived['od_with_insulation_mm'], 268.3)
        self.assertEqual(derived['dn_from_od'], 150)
        self.assertIs(derived['dn_consistent'], True)
        self.assertEqual(snapshot['warnings'], [])

    def test_bbox_cross_check_confirms_diameters(self):
        snapshot = reader.reapply_unit(_real_pipe_snapshot(), 'auto')
        self.assertIn('吻合', snapshot['bbox_cross_note'] or '')

    def test_report_shows_bbox_centerline_elevation(self):
        snapshot = reader.reapply_unit(_real_pipe_snapshot(), 'auto')
        rows = {(group, item): value
                for group, item, value, _note
                in reader.build_report_rows(snapshot)}
        # 包围盒中心 Z = (−134.1 + 134.2) / 2 = 0.05 mm ≈ 0（与 ELEVATION 一致）。
        # 不直接断言舍入后的字符串，避免浮点误差把 0.05 舍成 0.0 / 0.1 的争议。
        value = rows[('几何', '中心线标高（近似）')]
        self.assertTrue(value.endswith(' mm'))
        self.assertLess(abs(float(value.split()[0])), 0.1)
        self.assertIn(('几何', '包围盒中心'), rows)
        # 中心点应对应管段几何中点：(1715.7+4487.3)/2 = 3101.5
        self.assertAlmostEqual(
            float(rows[('几何', '包围盒中心')].strip('()').split(',')[0]),
            3101.5)
        # 没有曲线时不应再报"轴线几何读取失败"。
        self.assertNotIn(('几何', '轴线几何'), rows)

    def test_pipe_bottom_and_insulation_bottom_elevations(self):
        snapshot = reader.reapply_unit(_real_pipe_snapshot(), 'auto')
        derived = snapshot['derived']
        self.assertAlmostEqual(derived['centerline_z_mm'], 0.05, places=2)
        # 管底 = 中心线 − 外径/2 = 0.05 − 84.15
        self.assertAlmostEqual(derived['pipe_bottom_z_mm'], -84.10, places=2)
        # 保温层底 = 中心线 − 外径/2 − 保温 = −134.10
        self.assertAlmostEqual(derived['insulation_bottom_z_mm'], -134.10,
                               places=2)
        # 交叉验证：保温层底 = 包围盒最低点 Z（真实数据自洽）
        self.assertAlmostEqual(derived['insulation_bottom_z_mm'],
                               snapshot['bbox']['low_mm'][2], places=2)

    def test_report_shows_bottom_elevations(self):
        snapshot = reader.reapply_unit(_real_pipe_snapshot(), 'auto')
        rows = {(group, item): value
                for group, item, value, _note
                in reader.build_report_rows(snapshot)}
        self.assertIn(('几何', '管底标高'), rows)
        self.assertIn(('几何', '保温层底标高'), rows)
        self.assertTrue(rows[('几何', '管底标高')].endswith(' mm'))

    def test_elevations_missing_without_diameter(self):
        snapshot = _real_pipe_snapshot()
        snapshot['raw']['outside_diameter'] = None
        snapshot = reader.reapply_unit(snapshot, 'auto')
        self.assertIsNone(snapshot['derived']['pipe_bottom_z_mm'])
        self.assertIsNone(snapshot['derived']['insulation_bottom_z_mm'])

    def test_centerline_source_prefers_curve(self):
        snapshot = _real_pipe_snapshot()
        _z, source = reader.effective_centerline_z(snapshot)
        self.assertIn('包围盒', source)
        snapshot['geometry'] = {'centerline_z_mm': 3000.0}
        z, source = reader.effective_centerline_z(snapshot)
        self.assertEqual(z, 3000.0)
        self.assertIn('曲线', source)

    def test_reference_length_prefers_curve_then_bbox(self):
        snapshot = _real_pipe_snapshot()
        length, source = reader.reference_length_mm(snapshot)
        self.assertAlmostEqual(length, 2771.6)
        self.assertIn('包围盒', source)
        snapshot['geometry'] = {'length_mm': 500.0}
        length, source = reader.reference_length_mm(snapshot)
        self.assertEqual(length, 500.0)
        self.assertIn('曲线', source)


class PointOfTests(unittest.TestCase):
    """几何类的点成员在属性 / 方法两种写法下都要取得到。"""

    def test_property_style(self):
        class Obj(object):
            StartPoint = 'P'

        self.assertEqual(reader._point_of(Obj(), 'StartPoint'), 'P')

    def test_method_style(self):
        class Obj(object):
            @staticmethod
            def StartPoint():
                return 'P'

        self.assertEqual(reader._point_of(Obj(), 'StartPoint'), 'P')

    def test_missing_member_returns_none(self):
        self.assertIsNone(reader._point_of(object(), 'StartPoint'))

    def test_raising_member_returns_none(self):
        class Obj(object):
            @staticmethod
            def StartPoint():
                raise RuntimeError('取不到')

        self.assertIsNone(reader._point_of(Obj(), 'StartPoint'))


class InstancePropertyNamesTests(_FakeRuntime):
    """枚举"实例实际存在哪些属性"——本轮崩溃修复的核心接口。"""

    def test_returns_existing_names(self):
        instance = _FakeInstance('OpenPlant_3D', 'PIPE',
                                 {'OUTSIDE_DIAMETER': 0.1683,
                                  'LINENUMBER': 'P-1'})
        self.assertEqual(reader.instance_property_names(instance),
                         {'OUTSIDE_DIAMETER', 'LINENUMBER'})

    def test_empty_when_collection_unavailable(self):
        saved = reader.ECValuesCollection

        class Broken(object):
            @staticmethod
            def Create(instance):
                raise RuntimeError('取不到属性集合')

        reader.ECValuesCollection = Broken
        try:
            self.assertEqual(
                reader.instance_property_names(
                    _FakeInstance('OpenPlant_3D', 'PIPE', {})), set())
        finally:
            reader.ECValuesCollection = saved


class ScoreInstanceTests(unittest.TestCase):
    """判分是纯函数：只依赖"实际存在的属性名"，不碰任何 Bentley 对象。"""

    def test_openplant_schema_scores_higher(self):
        self.assertGreater(
            reader._score_instance(set(), 'OpenPlant_3D', 'SOMETHING'),
            reader._score_instance(set(), 'Other', 'OTHER'))

    def test_piping_class_name_adds_score(self):
        self.assertGreater(
            reader._score_instance(set(), 'OpenPlant_3D', 'PIPE_ELBOW'),
            reader._score_instance(set(), 'OpenPlant_3D', 'SOMETHING'))

    def test_diameter_property_adds_more_than_text_property(self):
        with_diameter = reader._score_instance({'OUTSIDE_DIAMETER': 1.0},
                                               'OpenPlant_3D', 'X')
        with_text = reader._score_instance({'LINENUMBER': 'P-1'},
                                           'OpenPlant_3D', 'X')
        self.assertGreater(with_diameter, with_text)

    def test_itemtype_instance_scores_nothing(self):
        available = {'ComponentName', 'Specification', 'DesignLengthMm'}
        self.assertEqual(
            reader._score_instance(available, 'PipeSupportComponents',
                                   'PipeSupportComponent_X'), 0)


class ReadPropertyTests(_FakeRuntime):

    def test_reads_number(self):
        instance = _FakeInstance('OpenPlant_3D', 'PIPE',
                                 {'OUTSIDE_DIAMETER': 0.1683})
        self.assertAlmostEqual(reader.read_number(instance, 'OUTSIDE_DIAMETER'),
                               0.1683)

    def test_reads_integer_property(self):
        instance = _FakeInstance('OpenPlant_3D', 'PIPE', {'SPOOL_NUMBER': 7})
        self.assertAlmostEqual(reader.read_number(instance, 'SPOOL_NUMBER'), 7.0)

    def test_missing_property_returns_none(self):
        instance = _FakeInstance('OpenPlant_3D', 'PIPE', {})
        self.assertIsNone(reader.read_number(instance, 'OUTSIDE_DIAMETER'))
        self.assertIsNone(reader.read_text(instance, 'LINENUMBER'))

    def test_null_property_returns_none(self):
        instance = _FakeInstance('OpenPlant_3D', 'PIPE',
                                 {'INSULATION_THICKNESS': None})
        self.assertIsNone(reader.read_number(instance,
                                             'INSULATION_THICKNESS'))

    def test_text_property_is_not_read_as_number(self):
        # LINENUMBER 是字符串，不能当成数值属性读出来。
        instance = _FakeInstance('OpenPlant_3D', 'PIPE',
                                 {'LINENUMBER': 'P-1001-6"-A1A'})
        self.assertIsNone(reader.read_number(instance, 'LINENUMBER'))
        self.assertEqual(reader.read_text(instance, 'LINENUMBER'),
                         'P-1001-6"-A1A')

    def test_number_property_is_not_read_as_text(self):
        instance = _FakeInstance('OpenPlant_3D', 'PIPE',
                                 {'OUTSIDE_DIAMETER': 168.3})
        self.assertIsNone(reader.read_text(instance, 'OUTSIDE_DIAMETER'))

    def test_empty_text_treated_as_missing(self):
        instance = _FakeInstance('OpenPlant_3D', 'PIPE', {'MATERIAL': '   '})
        self.assertIsNone(reader.read_text(instance, 'MATERIAL'))


def _record(index, schema, class_name, available=()):
    """构造一条实例记录（与 collect_instance_records 的产物同形）。"""
    return {'index': index, 'schema': schema, 'class': class_name,
            'available': set(available), 'rangeTexts': {},
            'values': {}, 'raw': {}}


class PickPipingRecordTests(unittest.TestCase):
    """挑选是纯函数：只吃纯 Python 记录，不碰 Bentley 对象。"""

    def test_prefers_piping_component_over_itemtype(self):
        # 元素上同时挂着本插件写的 ItemType 实例和 OPM 管道实例。
        item_type = _record(1, 'PipeSupportComponents',
                            'PipeSupportComponent_X', ['ComponentName'])
        pipe = _record(2, 'OpenPlant_3D', 'PIPE',
                       ['OUTSIDE_DIAMETER', 'NOMINAL_DIAMETER', 'LINENUMBER'])
        picked = reader.pick_piping_record([item_type, pipe])
        self.assertIsNotNone(picked)
        self.assertEqual(picked['class'], 'PIPE')
        self.assertEqual(picked['schema'], 'OpenPlant_3D')
        self.assertEqual(picked['index'], 2)

    def test_itemtype_record_is_rejected(self):
        # 只有 ItemType 时不能把支吊架属性当成管径读出来。
        item_type = _record(1, 'PipeSupportComponents',
                            'PipeSupportComponent_X', ['DesignLengthMm'])
        self.assertIsNone(reader.pick_piping_record([item_type]))

    def test_piping_class_hint_beats_plain_class(self):
        other = _record(1, 'OpenPlant_3D', 'SOMETHING', ['LINENUMBER'])
        elbow = _record(2, 'OpenPlant_3D', 'PIPE_ELBOW', ['NOMINAL_DIAMETER'])
        picked = reader.pick_piping_record([other, elbow])
        self.assertEqual(picked['class'], 'PIPE_ELBOW')

    def test_non_openplant_schema_is_rejected_even_with_diameter(self):
        # 资格只由 schema 决定：非 OpenPlant 即便带 OUTSIDE_DIAMETER 也不认，
        # 否则容易把别的插件写的属性当成管径。
        foreign = _record(1, 'MyPipingSchema', 'PIPE_SEGMENT',
                          ['OUTSIDE_DIAMETER'])
        self.assertIsNone(reader.pick_piping_record([foreign]))

    def test_returns_none_without_piping_record(self):
        self.assertIsNone(reader.pick_piping_record([]))
        blank = _record(1, 'SomeOtherSchema', 'ANNOTATION')
        self.assertIsNone(reader.pick_piping_record([blank]))

    def test_picked_record_carries_available_names(self):
        # 调用方靠 available 判断该不该读某个属性，绝不再拿不存在的名字去问。
        pipe = _record(1, 'OpenPlant_3D', 'PIPE',
                       ['OUTSIDE_DIAMETER', 'LINENUMBER'])
        picked = reader.pick_piping_record([pipe])
        self.assertEqual(picked['available'],
                         {'OUTSIDE_DIAMETER', 'LINENUMBER'})

    def test_logs_each_candidate(self):
        lines = []
        pipe = _record(1, 'OpenPlant_3D', 'PIPE', ['NOMINAL_DIAMETER'])
        reader.pick_piping_record([pipe], log=lines.append)
        self.assertTrue(any('候选实例 1' in line for line in lines))

    def test_record_needs_its_own_attributes_to_read(self):
        # 记录里没有实例对象，只有纯数据 —— 这正是"不可能再崩"的原因。
        pipe = _record(1, 'OpenPlant_3D', 'PIPE', ['LENGTH'])
        pipe['raw']['length'] = 2771.57
        picked = reader.pick_piping_record([pipe])
        self.assertEqual(picked['raw']['length'], 2771.57)
        self.assertNotIn('instance', picked)


class FillDerivedTests(unittest.TestCase):

    def _report(self, od=None, thickness=None, nominal=None):
        return {
            'values': {'outside_diameter': od,
                       'insulation_thickness': thickness,
                       'nominal_diameter': nominal},
            'derived': {},
            'unit': {'scale': reader.SCALE_MM, 'label': '毫米'},
            'warnings': [],
        }

    def test_insulation_outer_diameter(self):
        report = self._report(od=168.3, thickness=50.0, nominal=150.0)
        reader._fill_derived(report, report['warnings'])
        self.assertAlmostEqual(report['derived']['od_with_insulation_mm'], 268.3)
        self.assertAlmostEqual(report['derived']['insulation_outer_radius_mm'],
                               134.15)
        self.assertIs(report['derived']['dn_consistent'], True)
        self.assertEqual(report['warnings'], [])

    def test_mismatched_nominal_diameter_warns(self):
        report = self._report(od=168.3, thickness=0.0, nominal=300.0)
        reader._fill_derived(report, report['warnings'])
        self.assertIs(report['derived']['dn_consistent'], False)
        self.assertTrue(any('不一致' in text for text in report['warnings']))

    def test_non_series_outer_diameter_warns(self):
        report = self._report(od=175.0, thickness=0.0, nominal=150.0)
        reader._fill_derived(report, report['warnings'])
        self.assertIsNone(report['derived']['dn_from_od'])
        self.assertTrue(any('常用钢管外径系列' in text
                            for text in report['warnings']))

    def test_missing_values_do_not_raise(self):
        report = self._report()
        reader._fill_derived(report, report['warnings'])
        self.assertIsNone(report['derived']['od_with_insulation_mm'])
        self.assertIsNone(report['derived']['dn_consistent'])


if __name__ == '__main__':
    unittest.main()
