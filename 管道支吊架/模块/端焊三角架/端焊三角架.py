# -*- coding: utf-8 -*-
"""端焊三角架放置工具（A–D 变体）。

在面板中选择子项（A–D）、输入 L1 与 E，然后在活动三维 DGN 模型中点取
横担左端与既有钢结构焊接面的中心；整组构件（横担 + 斜撑）写成一个普通
单元（Normal Cell），可整体选中、移动、复制或删除，两个构件的清单属性
（ItemType）附加在单元上。

改参数会自动重建预览并替换上一版，点【确定】保留，点【取消】或右键放弃。
面板沿用 端焊三角架_基础.py 中的 PyQt5 自绘风格。

variant A 的规格即类型 1 端焊三角架（H125×125×6.5×9 + ∠100×10），因此
两个脚本生成的单元完全一致；本文件只负责在导入后覆盖子项表和 ItemType
前缀，其余逻辑（几何、单元封装、面板）都复用基础模块。
"""

from __future__ import division

import importlib
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# 本文件位于 模块/端焊三角架/，插件根目录需上溯两级；公共库在 模块/公共/。
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(HERE))
_COMMON_DIR = os.path.join(_PLUGIN_ROOT, '模块', '公共')
if _COMMON_DIR not in sys.path:
    sys.path.insert(0, _COMMON_DIR)

import 端焊三角架_基础 as base


def _reload_base(module):
    """每次运行都强制重新读取基础模块。

    MicroStation 的 Python 会话会把已导入的模块留在 sys.modules 里：改完
    端焊三角架_基础.py 后只重跑本文件，拿到的仍是上一次的模块，
    面板不会更新，必须重启 MicroStation。这里显式重载，规避该缓存。
    """
    name = module.__name__
    try:
        return importlib.reload(module)
    except Exception:
        pass
    try:
        sys.modules.pop(name, None)
        return importlib.import_module(name)
    except Exception:
        return module


base = _reload_base(base)


DEBUG_LOG = os.path.join(
    _PLUGIN_ROOT, '模块', '日志', '端焊三角架_debug_log.txt')

# 与类型 1 工具区分开的 ItemType 前缀，即使两个工具用在同一 DGN 里也不会
# 把清单混在一起。
ITEM_TYPE_PREFIX = 'EndWeldedTriangleBracketComponent'

# 子项规格：h_beam = (高, 宽, 腹板厚, 翼缘厚)，angle = (肢宽, 肢厚)。
VARIANTS = {
    'A': {
        'h_beam': (125.0, 125.0, 6.5, 9.0),
        'angle': (100.0, 10.0),
        'h_beam_specification': 'H125×125×6.5×9',
        'angle_specification': '∠100×10',
    },
    'B': {
        'h_beam': (150.0, 150.0, 7.0, 10.0),
        'angle': (125.0, 10.0),
        'h_beam_specification': 'H150×150×7×10',
        'angle_specification': '∠125×10',
    },
    'C': {
        'h_beam': (200.0, 200.0, 8.0, 12.0),
        'angle': (160.0, 12.0),
        'h_beam_specification': 'H200×200×8×12',
        'angle_specification': '∠160×12',
    },
    'D': {
        'h_beam': (250.0, 250.0, 9.0, 14.0),
        'angle': (200.0, 14.0),
        'h_beam_specification': 'H250×250×9×14',
        'angle_specification': '∠200×14',
    },
}

COMPONENT_A_NAME = '构件A（横担）'
COMPONENT_B_NAME = '构件B（斜撑）'

# 交付给基础模块的覆盖项：子项表、构件名、ItemType 前缀与日志文件。
base.VARIANTS = VARIANTS
base.DEFAULT_VARIANT = 'A'
base.ITEM_TYPE_PREFIX = ITEM_TYPE_PREFIX
base.H_BEAM_COMPONENT_NAME = COMPONENT_A_NAME
base.ANGLE_COMPONENT_NAME = COMPONENT_B_NAME
base.CELL_NAME = 'END_WELDED_TRIANGLE_BRACKET'
base.DEBUG_LOG = DEBUG_LOG

MIN_END_OVERHANG = base.MIN_END_OVERHANG
MAX_BEAM_LENGTH = base.MAX_BEAM_LENGTH

DEFAULT_VARIANT = base.DEFAULT_VARIANT


def calculate_beam_length(l1, end_overhang, variant_key=DEFAULT_VARIANT):
    """横担总长 L2，向上取整至整毫米。"""
    angle_width = VARIANTS[variant_key]['angle'][0]
    return float(math.ceil(
        float(l1) + angle_width * math.sqrt(2.0) / 2.0 + float(end_overhang)))


def create_end_welded_triangle_bracket(l1, end_overhang,
                                       variant_key=DEFAULT_VARIANT,
                                       origin=(0.0, 0.0, 0.0)):
    """按子项创建整组单元并写入模型，返回 (cell, 统计字典)。

    参数顺序沿用旧接口 (l1, end_overhang, variant_key, origin)。
    """
    return base.draw_end_welded_triangle_bracket(
        l1, end_overhang, origin, variant_key)


def export_end_welded_triangle_bracket_bom_json(output_path=None):
    """只导出本插件的 ItemType，写 JSON 并返回文件路径。"""
    if output_path is None:
        output_path = os.path.join(
            _PLUGIN_ROOT, '模块', '输出', '端焊三角架_bom.json')
    return base.export_triangle_bracket_bom_json(output_path)


def show_triangle_bracket_dialog():
    """显示子项 / L1 / E 面板并安装放置工具。"""
    return base.show_triangle_bracket_dialog()


def PyMain():
    """供 MicroStation Python 管理器调用的入口。"""
    return base.show_triangle_bracket_dialog()


if __name__ == '__main__':
    PyMain()
