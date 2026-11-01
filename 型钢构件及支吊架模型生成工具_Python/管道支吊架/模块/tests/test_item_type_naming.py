# -*- coding: utf-8 -*-
"""支吊架公共库 ItemType 命名（稳定族名）纯逻辑单测。

锁定：

* 稳定名只由「类型 + 构件代号」决定，不含哈希 / 单次长度 / tag —— 同类型
  反复放置复用同一批类，不再每放一次新建 2~3 个类；
* 旧命名（内容寻址，回退分支用）行为与改造前逐字一致；
* 中性默认值覆盖全部公共属性；
* 无 Bentley 运行时（纯 CPython）下模块可导入：单测不触原生路径。
"""

import os
import sys
import unittest

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_COMMON_DIR = os.path.join(os.path.dirname(_TEST_DIR), '公共')
if _COMMON_DIR not in sys.path:
    sys.path.insert(0, _COMMON_DIR)

import 支吊架公共库 as psb  # noqa: E402


class StableNamingTests(unittest.TestCase):

    def test_assembly_name_stable(self):
        """Assembly 类名只看支吊架类型：tag / 规格 / 管道号都不进名字。"""
        first = psb._stable_assembly_item_type_name('F2_VERTICAL_ELBOW_TRUNNION')
        second = psb._stable_assembly_item_type_name('F2_VERTICAL_ELBOW_TRUNNION')
        self.assertEqual(first, second)
        self.assertEqual(
            first, 'PipeSupportAssembly_F2_VERTICAL_ELBOW_TRUNNION')

    def test_component_name_stable(self):
        """Component 类名 = 类型 + 构件代号：同样数据（长度等）不进名字。"""
        first = psb._stable_component_item_type_name(
            'F2_VERTICAL_ELBOW_TRUNNION', 'TRUNNION_DN600_W9_53_C1_PIPE')
        second = psb._stable_component_item_type_name(
            'F2_VERTICAL_ELBOW_TRUNNION', 'TRUNNION_DN600_W9_53_C1_PIPE')
        self.assertEqual(first, second)
        self.assertEqual(
            first,
            'PipeSupportComponent_F2_VERTICAL_ELBOW_TRUNNION'
            '_TRUNNION_DN600_W9_53_C1_PIPE')

    def test_different_types_differ(self):
        self.assertNotEqual(
            psb._stable_component_item_type_name('ELBOW_PAD', 'ElbowPad'),
            psb._stable_component_item_type_name('ELBOW_PAD', 'OTHER'))
        self.assertNotEqual(
            psb._stable_assembly_item_type_name('ELBOW_PAD'),
            psb._stable_assembly_item_type_name('F2_VERTICAL_ELBOW_TRUNNION'))

    def test_chinese_code_flattened_to_ascii(self):
        """中文类型代号（如调用方误传）压成 ASCII，不抛异常。"""
        name = psb._stable_assembly_item_type_name('弯头垫板')
        self.assertTrue(name.startswith('PipeSupportAssembly_'))
        self.assertTrue(name.isascii())


class LegacyNamingTests(unittest.TestCase):
    """旧机制（回退分支）命名必须与改造前逐字一致。"""

    def test_assembly_content_addressed(self):
        first = psb._legacy_assembly_item_type_name(
            'ELBOW_PAD', '弯头垫板-D1060-1.0', 'R530×D1060×T6；L1387')
        same = psb._legacy_assembly_item_type_name(
            'ELBOW_PAD', '弯头垫板-D1060-1.0', 'R530×D1060×T6；L1387')
        other = psb._legacy_assembly_item_type_name(
            'ELBOW_PAD', '弯头垫板-D1060-1.0', '别的规格')
        self.assertEqual(first, same)
        self.assertNotEqual(first, other)
        self.assertRegex(first, r'^PipeSupportAssembly_ELBOW_PAD_'
                                  r'[0-9a-f]{10}$')

    def test_component_content_addressed(self):
        first = psb._legacy_component_item_type_name('ELBOW_PAD', 'ElbowPad',
                                                     1387.5)
        other = psb._legacy_component_item_type_name('ELBOW_PAD', 'ElbowPad',
                                                     2049.25)
        self.assertEqual(
            first, 'PipeSupportComponent_ELBOW_PAD_ElbowPad_L1387_500')
        self.assertNotEqual(first, other)

    def test_negative_length_key(self):
        name = psb._legacy_component_item_type_name('X', 'Y', -12.5)
        self.assertIn('LN12_500', name)


class NeutralDefaultsTests(unittest.TestCase):

    def test_covers_all_public_properties(self):
        for name, _type in psb.PROPERTY_DEFINITIONS:
            self.assertIn(name, psb._NEUTRAL_DEFAULTS)

    def test_neutral_values(self):
        for name, value in psb._NEUTRAL_DEFAULTS.items():
            if name == 'Quantity':
                self.assertEqual(value, 1)
            elif name == 'DesignLengthMm':
                self.assertEqual(value, 0.0)
            else:
                self.assertEqual(value, '')

    def test_short_hash_shape(self):
        digest = psb._short_hash('任何内容')
        self.assertEqual(len(digest), 10)
        self.assertRegex(digest, r'^[0-9a-f]{10}$')


class ModuleImportTests(unittest.TestCase):

    def test_import_without_bentley(self):
        """纯 CPython 下可导入（原生层缺席不炸），属性类型占位为 None。"""
        self.assertTrue(hasattr(psb, 'attach_components'))
        self.assertIn(psb.SUPPORT_LIBRARY_NAME, 'PipeSupportComponents')


if __name__ == '__main__':
    unittest.main()
