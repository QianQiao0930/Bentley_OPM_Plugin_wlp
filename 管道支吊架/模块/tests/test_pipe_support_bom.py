# -*- coding: utf-8 -*-
from __future__ import division

import os
import sys
import tempfile
import unittest
import zipfile


_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_MODULE_DIR = os.path.dirname(_TESTS_DIR)
_COMMON_DIR = os.path.join(_MODULE_DIR, '公共')
if _COMMON_DIR not in sys.path:
    sys.path.insert(0, _COMMON_DIR)

import 支吊架公共库 as psb  # noqa: E402


def _assembly(support_type, tag, quantity=1):
    return {
        'recordKind': 'Assembly', 'supportType': support_type,
        'assemblyTag': tag, 'componentName': '支吊架',
        'specification': '', 'unit': '套',
        'quantity': quantity, 'designLengthMm': 0.0,
    }


def _component(support_type, name, specification, quantity, length, unit='件'):
    return {
        'recordKind': 'Component', 'supportType': support_type,
        'assemblyTag': '', 'componentName': name,
        'specification': specification, 'unit': unit,
        'quantity': quantity, 'designLengthMm': length,
    }


class NamingTests(unittest.TestCase):
    def test_ascii_token(self):
        self.assertEqual('L_PIPE_RACK', psb._ascii_token('L_PIPE_RACK'))
        self.assertEqual('A_B', psb._ascii_token('A/B'))
        self.assertEqual('X', psb._ascii_token('构件'))  # 全非 ASCII -> X

    def test_component_item_type_name(self):
        name = psb._component_item_type_name('L_PIPE_RACK', 'Post', 1200.0)
        self.assertTrue(name.startswith(psb.COMPONENT_PREFIX + '_L_PIPE_RACK_Post'))
        self.assertTrue(name.endswith('_L1200_000'))

    def test_assembly_item_type_name(self):
        name = psb._assembly_item_type_name(
            'TRIANGLE_BRACKET', 'D5-1-A-1000-1500', 'H125x125x6.5x9')
        self.assertTrue(
            name.startswith(psb.ASSEMBLY_PREFIX + '_TRIANGLE_BRACKET_'))

    def test_assembly_name_is_stable_and_distinct(self):
        first = psb._assembly_item_type_name('T', 'tag-1', 'spec-a')
        again = psb._assembly_item_type_name('T', 'tag-1', 'spec-a')
        other = psb._assembly_item_type_name('T', 'tag-2', 'spec-a')
        self.assertEqual(first, again)
        self.assertNotEqual(first, other)


class SummariseTests(unittest.TestCase):
    def _records(self):
        return [
            _assembly('端焊三角架', 'D5-1-A-1000-1500'),
            _assembly('端焊三角架', 'D5-1-B-1000-1500'),
            _assembly('L型管架', 'D1-1-A-1200-800'),
            _component('端焊三角架', '横担', 'H125×125×6.5×9', 1, 1200.0),
            _component('端焊三角架', '横担', 'H125×125×6.5×9', 1, 1200.0),
            _component('端焊三角架', '膨胀锚栓', 'M16×100', 4, 100.0),
            _component('L型管架', '立杆', '∠50×6', 1, 1200.0),
            _component('L型管架', '横担', '∠50×6', 1, 800.0),
        ]

    def test_counts_assemblies_by_type(self):
        supports, _ = psb._summarise(self._records())
        by_type = {entry['supportType']: entry for entry in supports}
        self.assertEqual(2, by_type['端焊三角架']['assemblyCount'])
        self.assertEqual(1, by_type['L型管架']['assemblyCount'])
        self.assertEqual(
            ['D5-1-A-1000-1500', 'D5-1-B-1000-1500'],
            by_type['端焊三角架']['assemblyTags'])

    def test_materials_are_grouped_and_totalled(self):
        _, materials = psb._summarise(self._records())
        by_key = {(m['supportType'], m['componentName'], m['specification']): m
                  for m in materials}
        h_beam = by_key[('端焊三角架', '横担', 'H125×125×6.5×9')]
        self.assertEqual(2, h_beam['quantity'])
        self.assertAlmostEqual(2400.0, h_beam['totalDesignLengthMm'])
        bolt = by_key[('端焊三角架', '膨胀锚栓', 'M16×100')]
        self.assertEqual(4, bolt['quantity'])
        self.assertAlmostEqual(400.0, bolt['totalDesignLengthMm'])
        self.assertIn(('L型管架', '立杆', '∠50×6'), by_key)

    def test_empty_records(self):
        supports, materials = psb._summarise([])
        self.assertEqual([], supports)
        self.assertEqual([], materials)


class ExcelTests(unittest.TestCase):
    def test_write_xlsx_is_a_valid_zip_with_sheets(self):
        sheets = [
            (u'支吊架表', [[u'序号', u'类型'], [1, u'端焊三角架']], {1}),
            (u'材料汇总表', [[u'构件', u'数量'], [u'横担', 2]], {1}),
        ]
        handle, path = tempfile.mkstemp(suffix='.xlsx')
        os.close(handle)
        try:
            psb.write_xlsx(path, sheets)
            self.assertTrue(zipfile.is_zipfile(path))
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                for part in ('[Content_Types].xml', '_rels/.rels',
                             'xl/workbook.xml', 'xl/_rels/workbook.xml.rels',
                             'xl/styles.xml', 'xl/worksheets/sheet1.xml',
                             'xl/worksheets/sheet2.xml'):
                    self.assertIn(part, names)
                workbook = archive.read('xl/workbook.xml').decode('utf-8')
                self.assertIn(u'支吊架表', workbook)
                sheet1 = archive.read('xl/worksheets/sheet1.xml').decode('utf-8')
                self.assertIn(u'端焊三角架', sheet1)
        finally:
            os.remove(path)

    def test_build_excel_sheets_contains_three_sheets(self):
        statistics = {
            'assemblyCount': 2,
            'componentRecordCount': 3,
            'supportsByType': [
                {'supportType': u'端焊三角架', 'assemblyCount': 2,
                 'assemblyTags': [u'D5-1-A-1000-1500', u'D5-1-B-1000-1500']},
            ],
            'materials': [
                {'supportType': u'端焊三角架', 'componentName': u'横担',
                 'specification': u'H125', 'unit': u'件', 'quantity': 2,
                 'totalDesignLengthMm': 2400.0},
            ],
            'records': [
                {'recordKind': 'Assembly', 'supportType': u'端焊三角架',
                 'assemblyTag': u'D5-1-A-1000-1500', 'componentName': u'支吊架',
                 'specification': u'H125 + L100', 'unit': u'套',
                 'quantity': 1, 'designLengthMm': 0.0, 'elementId': 11},
                {'recordKind': 'Component', 'supportType': u'端焊三角架',
                 'assemblyTag': '', 'componentName': u'横担',
                 'specification': u'H125', 'unit': u'件',
                 'quantity': 1, 'designLengthMm': 1200.0, 'elementId': 11},
            ],
        }
        sheets = psb.build_excel_sheets(statistics, '2026-01-01 00:00:00')
        names = [name for name, _rows, _headers in sheets]
        self.assertEqual([u'汇总', u'支吊架表', u'材料汇总表'], names)
        support_rows = sheets[1][1]
        self.assertEqual(u'序号', support_rows[0][0])
        self.assertEqual(1, support_rows[1][0])
        self.assertIn(u'横担', support_rows[1][4])


if __name__ == '__main__':
    unittest.main()
