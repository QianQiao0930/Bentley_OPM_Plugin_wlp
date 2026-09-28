# -*- coding: utf-8 -*-
"""三角架放置工具（D5 端焊 / D6 侧焊 / G12 锚固 / D19 双槽钢；辅助线路径版）。

本文件是**另写的一版**，用于替换绘图思路；不修改也不依赖老入口
``D5_D6-[三角架].py``（它只实现了 D5），只复用
``模块/端焊三角架/端焊三角架_选线_几何.py``
里已经验证过的底层原语（扫掠、布尔剪切、形状创建、直线提取）。

==============================
零、架型（面板顶部先选）
==============================
* **D5 端焊**   —— H 型钢横担 + 角钢斜撑，端面直接焊在既有钢结构上；L2 ≤ 2500。
* **D6 侧焊**   —— 单片槽钢横担 / 斜撑，腹板外表面与所选平面平齐、根部不剪切；
  L2 ≤ 1500，面板显示表 1 允许荷载。
* **G12 混凝土锚固** —— D6 同形 + 构件C 4 根膨胀锚栓锚在既有混凝土上。
* **D19 双槽钢** —— 横担 / 斜撑各**两片、背靠背**（腹板外表面相对、净距 S，
  整体关于所选竖直平面对称），端部用**构件C 矩形钢板**连成整体；
  L2 ≤ 2000，表 1 只有垂直荷载。
D5 另有"混凝土上生根（G2 端板）"可选；其余三种架型都不设端板。

==============================
一、用法（与旧版一致的部分）
==============================
在模型中点选一条**水平直线段**，该直线即**管道底标高**：

    P0 = 直线起点（贴既有钢结构的焊接端面）
    P2 = 直线终点（横担最远端）
    直线长 L2 = 横担总长（D5 ≤ 2500 mm）

==============================
二、新逻辑：四个辅助点 + 输入 L1
==============================
用户直接输入 **L1**（不再由 E 反算），据此算出四个点（局部坐标，mm，
+X 沿直线方向、+Y 为水平法向、+Z 向上，原点在 P0）：

    类型 1（斜撑在下）
        P1 = P0 沿直线方向移动 L1，Z 下移构件A 的截面高 hA  → 横担下翼缘底面上的交点
        P3 = P0 的 XY 不变，Z = P0.Z − hA − L1            → 斜撑底部（贴墙面，只有 Z 与 P0 不同）
    类型 2（斜撑在上）—— 即类型 1 关于横担半高平面镜像
        P1 = P0 沿直线方向移动 L1，Z = P0.Z                → 横担上翼缘顶面上的交点
        P3 = P0 的 XY 不变，Z = P0.Z + L1                 → 斜撑顶部（贴墙面）

两种类型的斜撑轴线都是 45°：水平投影 = 竖直投影 = L1。

==============================
三、新逻辑：先画辅助线再拉伸
==============================
建模前**先绘制一条不可见的辅助线**，它只作为拉伸（扫掠）的路径：

    横担：辅助线为 P0→P2 向下平移 hA/2（**过截面形心／翼缘中心**）的直线，
          这样按形心居中扫掠出的 H 型钢，顶面正好落在用户所选直线上，
          即"用户选的线就是管道底标高"。
    斜撑：辅助线为 P3→P1 的轴线，两端各延长一段（端部剪切面才完整）。

扫掠向量**从这条辅助线元素里读回**（直线路径下与矢量扫掠完全等价）。
无论建模成功还是失败，辅助线都在 ``finally`` 里无条件删除，不留在模型中。

==============================
四、保留的部分
==============================
* 端面布尔剪切：斜撑底部按**竖直面**（贴墙面，局部 x=0）剪切；
  斜撑与横担接触端按**水平面**剪切（类型 1 在横担下翼缘底面，类型 2 在上翼缘顶面）。
* 斜撑为 45° 角钢，斜面（倾斜的四十五度面）沿轴线扫掠生成，非竖直板。
* 整组写成一个普通单元，清单写入 ``支吊架公共库``（可导出 JSON）。

编号：``名称-类型-子项-L1-L2``（默认名称按架型取 ``D5`` / ``D6`` / ``G12`` /
``D19``；D19 图集编号的末段筋板尺寸 ``h×w`` 见注 3，本版不建筋板、该段留空）。
运行环境：Bentley Power Platform Python（MSPy）。
"""

from __future__ import division

import faulthandler
import importlib
import math
import os
import sys
import time
import tkinter as tk
import traceback
from tkinter import ttk

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyECObjects import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *

# 通配导入不一定导出这两个符号，显式再导入一次。
from MSPyBentley import WString  # noqa: E402,F811


HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
# 公共库在 模块/公共/；底层几何原语在 模块/端焊三角架/；仓库根提供 bentley_ui。
COMMON_DIR = os.path.join(HERE, '模块', '公共')
GEOM_DIR = os.path.join(HERE, '模块', '端焊三角架')
for _path in (REPO_ROOT, COMMON_DIR, GEOM_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

# 共享 UI 工具箱在导入前强制重读一次，避免拿到 MicroStation 缓存的旧模块。
try:
    import bentley_ui.glass as _glass_module
    import bentley_ui as _bentley_ui_module
    importlib.reload(_glass_module)
    importlib.reload(_bentley_ui_module)
except Exception:
    pass

from bentley_ui import (  # noqa: E402
    ACCENT,
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
)

import 端焊三角架_选线_几何 as geom  # noqa: E402
import 混凝土锚板 as anchor  # noqa: E402
import 支吊架公共库 as psb  # noqa: E402


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

UI_TITLE = 'D5 端焊 / D6 侧焊 / G12 锚固 / D19 双槽钢三角架'
UI_REVISION = 'path-7-connector-center'

DEBUG_LOG = os.path.join(HERE, '模块', '日志', 'D5_D6_G12_D19三角架_debug_log.txt')
try:
    os.makedirs(os.path.dirname(DEBUG_LOG), exist_ok=True)
except Exception:
    pass

# 参数变化后延迟重建预览的毫秒数。
REGENERATE_DELAY_MS = 150
TEXT_REGENERATE_DELAY_MS = 750

# ---------------------------------------------------------------------------
# 清单写库（共享支吊架库 ItemType）策略
# ---------------------------------------------------------------------------
# 背景：把构件写进 ``支吊架公共库`` 走的是 MicroStation 原生 EC 调用
# （``CustomItemHost.ApplyCustomItem``）。该调用在本插件里偶发"卡死十几秒后
# access violation"（见 模块/日志/D5_D6_G12_D19三角架_fault.log），与几何、清单数据
# 都无关：同一份代码、同一组参数可能这次成功、下次卡死。
#
# 因此这里做两件事降低暴露面：
#   1) ATTACH_ON_CONFIRM：**只在点【确定】时写库**。预览阶段每次改参数都会重建
#      整组，如果每次都写库，就会反复新建 / 复用 ItemType 并触发原生 EC 写入；
#      改到【确定】一次，调用次数降一到两个数量级，也不会再为"取消掉的预览"
#      在公共库里留下垃圾 ItemType。
#   2) ITEM_TYPE_ATTACH：逃生开关。万一本机环境下这个原生调用持续崩溃，置
#      False 后几何照常生成、照常落图，只是这批支架不进清单统计。
ATTACH_ON_CONFIRM = True
ITEM_TYPE_ATTACH = True

# 横担端部余量 E = L2 − L1 的最小值、L1 的最小值、横担总长上限（mm）。
MIN_END_OVERHANG = float(geom.MIN_END_OVERHANG)     # 150
MIN_L1 = 150.0
MAX_BEAM_LENGTH = float(geom.MAX_BEAM_LENGTH)       # 2500
DEFAULT_L1 = 600.0

# 构件名称（写清单用）。混凝土生根时端板 / 锚栓单独列项，与支架本体分开统计。
COMPONENT_A_NAME = '构件A（横担）'
COMPONENT_B_NAME = '构件B（斜撑）'
# D19 构件C：端部连接（加固）钢板，把两片槽钢横担连成整体。
COMPONENT_C_NAME = '构件C（端部连接板）'
COMPONENT_PLATE_NAME = 'G2 端板（横担）'
COMPONENT_BRACE_PLATE_NAME = 'G2 端板（斜撑）'
COMPONENT_BOLT_NAME = 'G2 膨胀锚栓（横担）'
COMPONENT_BRACE_BOLT_NAME = 'G2 膨胀锚栓（斜撑）'

# G2 混凝土锚板默认子项（A/B/C/D，见 混凝土锚板.ANCHOR_TABLE）。
DEFAULT_PLATE_SUBTYPE = 'A'

# 整组构件写入的普通单元名 / 共享支吊架清单的类型标识（D5 默认值；
# 实际使用时按架型取 KIND_CONFIG 里的值，见下方 KIND_CONFIG）。
CELL_NAME = 'END_WELDED_TRIANGLE_BRACKET_PATH'
SUPPORT_TYPE = 'D5-端焊三角架'
SUPPORT_CODE = 'D5_END_WELDED_TRIANGLE_BRACKET'

# 类型：1 斜撑在下（向上撑），2 斜撑在上（向下拉）。
TYPE_OPTIONS = (
    (1, '类型 1  |  斜撑在下（向上撑）'),
    (2, '类型 2  |  斜撑在上（向下拉）'),
)
TYPE_KEYS = tuple(key for key, _label in TYPE_OPTIONS)

# ---------------------------------------------------------------------------
# D6 侧焊 / G12 混凝土锚固 / D19 双槽钢：槽钢截面（GB/T 706）与表 1 / 表 2
# ---------------------------------------------------------------------------

# 架型：面板顶部先选，决定下面的子项表、名称默认值、L2 上限与清单类型。
BRACKET_KINDS = (
    ('D5', 'D5 端焊三角架'),
    ('D6', 'D6 侧焊三角架'),
    ('G12', 'G12 混凝土锚固'),
    ('D19', 'D19 双槽钢三角架'),
)
KIND_KEYS = tuple(key for key, _label in BRACKET_KINDS)
KIND_LABELS = dict(BRACKET_KINDS)
# 用槽钢（D6：腹板外表面与所选平面平齐）+ 根部不剪切 的架型。
CHANNEL_KINDS = ('D6', 'G12', 'D19')
# 两片槽钢**背靠背**（腹板外表面相对、净距 S、关于所选竖直平面对称）
# + 端部连接板（构件C）的架型。
DOUBLE_CHANNEL_KINDS = ('D19',)

# 槽钢截面：规格 -> (高 H, 翼缘宽 B, 腹板厚 tw, 翼缘厚 tf)，均为 mm。
CHANNEL_SECTIONS = {
    '[10': (100.0, 48.0, 5.3, 8.5),
    '[12.6': (126.0, 53.0, 5.5, 9.0),
    '[14a': (140.0, 58.0, 6.0, 9.5),
    '[16a': (160.0, 63.0, 6.5, 10.0),
    '[20a': (200.0, 73.0, 7.0, 11.0),
    '[25a': (250.0, 78.0, 7.0, 12.0),
}

# 表 2：子项 -> 构件A（横担）/ 构件B（斜撑）的槽钢规格。
D6_VARIANTS = {
    'A': {'comp_a': '[12.6', 'comp_b': '[10'},
    'B': {'comp_a': '[16a', 'comp_b': '[12.6'},
    'C': {'comp_a': '[20a', 'comp_b': '[14a'},
    'D': {'comp_a': '[25a', 'comp_b': '[20a'},
}
D6_DEFAULT_VARIANT = 'A'
# D6 / G12 横担总长上限 1500（图中 "L2 (MAX. 1 500)"）。
D6_MAX_BEAM_LENGTH = 1500.0

# 表 1 的 L1 档位（mm）：允许的垂直荷载按子项 + L1 落在哪一档查。
LOAD_COLUMNS = (500.0, 750.0, 1000.0, 1250.0)
# 允许的水平荷载 = 管架编号 D3 中相同构件允许的垂直荷载 × 0.3（表 1 附注）。
D6_HORIZONTAL_FACTOR = 0.3

# 表 1（D6 侧焊）：允许的垂直荷载 / kN，按 LOAD_COLUMNS 顺序；None = 该档无值。
D6_LOAD_TABLE = {
    'A': (8.9, 6.0, 4.5, None),
    'B': (14.0, 9.8, 7.4, None),
    'C': (21.0, 14.0, 10.0, 8.6),
    'D': (26.0, 18.0, 13.0, 11.0),
}

# ---------------------------------------------------------------------------
# G12 混凝土锚固三角架（与 D6 同形，另加 4 根膨胀锚栓 构件C）
# ---------------------------------------------------------------------------

# 表 2：子项 -> 构件A / 构件B 槽钢 + 构件C 膨胀锚栓 + C、S 尺寸。
# bolt_subtype 指向 混凝土锚板.ANCHOR_TABLE 里同规格的一行（做法与 G2 一致）。
G12_VARIANTS = {
    'A': {'comp_a': '[12.6', 'comp_b': '[10', 'bolt_subtype': 'B',
          'bolt_spec': 'M12×120', 'c': 100.0, 's': 100.0},
    'B': {'comp_a': '[16a', 'comp_b': '[12.6', 'bolt_subtype': 'C',
          'bolt_spec': 'M16×140', 'c': 100.0, 's': 125.0},
    'C': {'comp_a': '[20a', 'comp_b': '[14a', 'bolt_subtype': 'D',
          'bolt_spec': 'M20×180', 'c': 200.0, 's': 150.0},
    'D': {'comp_a': '[25a', 'comp_b': '[20a', 'bolt_subtype': 'D',
          'bolt_spec': 'M20×180', 'c': 200.0, 's': 150.0},
}
G12_DEFAULT_VARIANT = 'A'
G12_MAX_BEAM_LENGTH = 1500.0

# 表 1（G12）：允许的垂直荷载 / kN，按 LOAD_COLUMNS 顺序；None = 该档无值。
G12_LOAD_TABLE = {
    'A': (6.0, 4.0, 3.0, None),
    'B': (10.0, 6.0, 6.0, None),
    'C': (None, 10.0, 7.0, 5.0),
    'D': (None, 20.0, 10.0, 8.0),
}

# 构件C：第一根锚栓自起点沿辅助线（或斜撑轴线）的距离（mm）。
G12_FIRST_BOLT_OFFSET = 75.0
G12_ANCHOR_NAME = '构件C（膨胀锚栓）'

# ---------------------------------------------------------------------------
# D19 双槽钢三角架（两片槽钢背靠背 + 端部连接板 构件C）
# ---------------------------------------------------------------------------

# 表 2：子项 -> 构件A / 构件B 槽钢（与 D6 表 2 完全相同）
# + 构件C 矩形钢板 (长 Ly, 高 Hc, 厚 T) + 两片槽钢**腹板外表面（背面）间距** S。
D19_VARIANTS = {
    'A': {'comp_a': '[12.6', 'comp_b': '[10', 'comp_c': (100.0, 60.0, 10.0),
          's': 60.0},
    'B': {'comp_a': '[16a', 'comp_b': '[12.6', 'comp_c': (120.0, 80.0, 10.0),
          's': 70.0},
    'C': {'comp_a': '[20a', 'comp_b': '[14a', 'comp_c': (150.0, 100.0, 10.0),
          's': 80.0},
    'D': {'comp_a': '[25a', 'comp_b': '[20a', 'comp_c': (150.0, 120.0, 10.0),
          's': 90.0},
}
D19_DEFAULT_VARIANT = 'A'
# 图中横担总长 "2 000 (MAX.)"。
D19_MAX_BEAM_LENGTH = 2000.0

# 表 1（D19）：允许的垂直荷载 / kN；比 D6 / G12 多 "L1≤1 500" 一档。
# 表内没有水平荷载一栏，所以面板上不显示水平荷载。
D19_LOAD_COLUMNS = (500.0, 750.0, 1000.0, 1250.0, 1500.0)
D19_LOAD_TABLE = {
    'A': (60.0, 40.0, 30.0, None, None),
    'B': (100.0, 70.0, 50.0, None, None),
    'C': (150.0, 100.0, 70.0, 50.0, None),
    'D': (220.0, 160.0, 120.0, 100.0, 80.0),
}

# 表 1 的档位按**架型**取：D19 五档，D6 / G12 四档。查表一律用该架型自己的
# 档位元组，避免"档位比表长"造成越界（见 describe_load）。
LOAD_COLUMNS_OF = {
    'D6': LOAD_COLUMNS,
    'G12': LOAD_COLUMNS,
    'D19': D19_LOAD_COLUMNS,
}
# 允许水平荷载 = 管架编号 D3 中相同构件允许的垂直荷载 × 0.3（D6 / G12 表 1
# 附注）；D19 表 1 没有这一栏 → None = 不计算也不显示。
HORIZONTAL_FACTOR_OF = {
    'D6': D6_HORIZONTAL_FACTOR,
    'G12': D6_HORIZONTAL_FACTOR,
    'D19': None,
}

# 构件C（端部连接板）：**竖直钢板、法向沿梁轴 +X**，长 Ly 沿 +Y 在两片槽钢
# **正中间**对称跨过去、高 Hc 厚 T 沿 X。
# 竖直方向**中心对齐**：板高中心与槽钢**截面高度中心**（z = −hA/2）重合
# （不是顶面与横担顶面平齐）；沿梁轴放在横担末端的**外侧** x ∈ [L2, L2 + T]，
# 内表面与两片槽钢的端面贴合焊接，**不跟腹板/翼缘硬碰撞**。
# 若图纸改为"水平盖板 / 往内缩一段 / 每端多块"，只改 _connector_box()。
D19_CONNECTOR_COUNT = 1
# D19 斜撑根部按**竖直面**剪切（端面与焊接面 x = 0 平齐），与 D6 侧焊的
# "根部不剪切、保留 45° 自然端面"不同。
D19_BRACE_ROOT_CUT = True

# 架型配置：名称默认值、L2 上限、清单类型标识、单元名。
KIND_CONFIG = {
    'D5': {
        'max_length': float(geom.MAX_BEAM_LENGTH),
        'default_name': 'D5',
        'default_variant': geom.DEFAULT_VARIANT,
        'support_type': 'D5-端焊三角架',
        'support_code': 'D5_END_WELDED_TRIANGLE_BRACKET',
        'cell_name': 'END_WELDED_TRIANGLE_BRACKET_PATH',
    },
    'D6': {
        'max_length': D6_MAX_BEAM_LENGTH,
        'default_name': 'D6',
        'default_variant': D6_DEFAULT_VARIANT,
        'support_type': 'D6-侧焊三角架',
        'support_code': 'D6_SIDE_WELDED_TRIANGLE_BRACKET',
        'cell_name': 'SIDE_WELDED_TRIANGLE_BRACKET_PATH',
    },
    'G12': {
        'max_length': G12_MAX_BEAM_LENGTH,
        'default_name': 'G12',
        'default_variant': G12_DEFAULT_VARIANT,
        'support_type': 'G12-混凝土锚固三角架',
        'support_code': 'G12_CONCRETE_ANCHORED_BRACKET',
        'cell_name': 'CONCRETE_ANCHORED_TRIANGLE_BRACKET',
    },
    'D19': {
        'max_length': D19_MAX_BEAM_LENGTH,
        'default_name': 'D19',
        'default_variant': D19_DEFAULT_VARIANT,
        'support_type': 'D19-双槽钢三角架',
        'support_code': 'D19_DOUBLE_CHANNEL_TRIANGLE_BRACKET',
        'cell_name': 'DOUBLE_CHANNEL_TRIANGLE_BRACKET',
    },
}
DEFAULT_KIND = 'D5'

# 槽钢架型的表 2（D6 / G12 各一张；D19 多 构件C 与 S 两列）。
CHANNEL_VARIANTS = {
    'D6': D6_VARIANTS,
    'G12': G12_VARIANTS,
    'D19': D19_VARIANTS,
}


def kind_config(kind):
    return KIND_CONFIG.get(kind, KIND_CONFIG[DEFAULT_KIND])


def kind_max_length(kind):
    return float(kind_config(kind)['max_length'])


def kind_default_name(kind):
    return kind_config(kind)['default_name']


def variant_keys_of(kind):
    """该架型的子项键（D5 为 H 型钢+角钢；其余为表 2 的槽钢行）。"""
    if kind in CHANNEL_VARIANTS:
        return tuple(sorted(CHANNEL_VARIANTS[kind]))
    return tuple(sorted(geom.VARIANTS))


def default_variant_of(kind):
    return kind_config(kind)['default_variant']


def channel_variant_of(kind, key):
    """槽钢架型的表 2 行（D6 没有构件C；G12 有锚栓；D19 有构件C 与 S）。"""
    return CHANNEL_VARIANTS.get(kind, D6_VARIANTS)[key]


def variant_label_of(kind, key):
    """子项下拉里的显示文本。"""
    if kind in CHANNEL_KINDS:
        variant = channel_variant_of(kind, key)
        spec_a = CHANNEL_SECTIONS[variant['comp_a']]
        spec_b = CHANNEL_SECTIONS[variant['comp_b']]
        text = ('%s  |  构件A %s（%g×%g×%g×%g）  |  构件B %s'
                % (key, variant['comp_a'], spec_a[0], spec_a[1], spec_a[2],
                   spec_a[3], variant['comp_b']))
        if kind == 'G12':
            text += '  |  构件C %s' % variant['bolt_spec']
        elif kind == 'D19':
            plate = variant['comp_c']
            text += ('  |  构件C %.0f×%.0f×%.0f 钢板  |  S=%.0f'
                     % (plate[0], plate[1], plate[2], variant['s']))
        return text
    return geom.variant_label(key)


def variant_specs(kind, key):
    """返回 (构件A 截面元组, 构件B 截面元组, A 规格文字, B 规格文字)。

    D5：A 为 H 型钢 (h, b, tw, tf)、B 为角钢 (肢宽, 肢厚)；
    D6 / G12 / D19：A、B 均为槽钢 (H, B, tw, tf)。
    """
    if kind in CHANNEL_KINDS:
        variant = channel_variant_of(kind, key)
        spec_a = CHANNEL_SECTIONS[variant['comp_a']]
        spec_b = CHANNEL_SECTIONS[variant['comp_b']]
        return spec_a, spec_b, variant['comp_a'], variant['comp_b']
    variant = geom.VARIANTS[key]
    return (variant['h_beam'], variant['angle'],
            variant['h_beam_specification'], variant['angle_specification'])


def load_table_of(kind, key):
    """该子项的允许垂直荷载行（按该架型自己的档位顺序）；D5 无此表。"""
    if kind == 'D6':
        return D6_LOAD_TABLE.get(key, ())
    if kind == 'G12':
        return G12_LOAD_TABLE.get(key, ())
    if kind == 'D19':
        return D19_LOAD_TABLE.get(key, ())
    return ()


def load_columns_of(kind):
    """该架型表 1 的 L1 档位（D19 比 D6 / G12 多 "L1≤1500" 一档）。"""
    return LOAD_COLUMNS_OF.get(kind, LOAD_COLUMNS)


def load_cell(kind, key, l1_mm):
    """返回 (档位上限, 荷载值)；(档位, None) 表示该档无值；越界返回 (None, None)。"""
    table = load_table_of(kind, key)
    if not table:
        return None, None
    try:
        l1 = float(l1_mm)
    except (TypeError, ValueError):
        return None, None
    for limit, value in zip(load_columns_of(kind), table):
        if l1 <= limit + 1.0e-9:
            return limit, value
    return None, None


def allowable_load(kind, key, l1_mm, horizontal=False):
    """按 L1 查表 1 的允许垂直荷载（kN）。

    返回 None 表示"该 L1 档位在表里无值"或"超出表范围"（用
    :func:`load_cell` 区分）；``horizontal=True`` 时按该架型的表 1 附注折算
    水平荷载，表里没有这一栏（D19）则返回 None。
    """
    _limit, value = load_cell(kind, key, l1_mm)
    if value is None:
        return None
    if horizontal:
        factor = HORIZONTAL_FACTOR_OF.get(kind)
        return None if factor is None else value * factor
    return value


def load_limit_of(kind, key, l1_mm):
    """L1 对应的档位上限（如 500 / 750 …）；超出返回 None。"""
    limit, _value = load_cell(kind, key, l1_mm)
    return limit


def describe_bolt_line(kind, key):
    """G12 构件C（膨胀锚栓）的位置说明；其它架型返回空串。"""
    if kind != 'G12':
        return ''
    variant = G12_VARIANTS[key]
    first = G12_FIRST_BOLT_OFFSET
    second = first + float(variant['s'])
    return ('%s %s ×4：横担 / 斜撑 均按水平距离起量 %.0f / %.0f mm'
            '（S=%.0f；斜撑 45°，沿轴线量取 = 水平距离 ×√2） ｜ C=%.0f'
            % (G12_ANCHOR_NAME, variant['bolt_spec'], first, second,
               variant['s'], variant['c']))


def describe_connector(kind, key):
    """D19 构件C（端部连接板）与两片间距 S 的说明；其它架型返回空串。"""
    if kind != 'D19':
        return ''
    variant = D19_VARIANTS[key]
    plate = variant['comp_c']
    return ('%s %.0f×%.0f×%.0f 钢板 ×%d：竖直板、法向沿梁轴，贴在横担末端'
            '**外侧**（内表面与两片端面贴合焊接，不与槽钢硬碰撞）；'
            '竖直方向与槽钢**截面高度中心对齐**、长边在两片正中间对称跨过；'
            '两片槽钢**背靠背**（腹板外表面间距 S=%.0f），整体关于所选竖直平面'
            '对称（斜撑根部按竖直面剪切）'
            % (COMPONENT_C_NAME, plate[0], plate[1], plate[2],
               D19_CONNECTOR_COUNT, variant['s']))


def describe_load(kind, key, l1_mm):
    """面板上的允许荷载说明文字（D6 / G12 / D19 查表 1；D5 无表）。

    档位一律按**该架型自己的**表 1 列（D19 五档、D6 / G12 四档），所以
    "档位比表长"也不会越界；表里没有水平荷载一栏（D19）时不显示水平荷载。
    """
    if kind not in CHANNEL_KINDS:
        return ''
    columns = load_columns_of(kind)
    limit, value = load_cell(kind, key, l1_mm)
    if limit is None:
        return ('允许垂直荷载：超出表 1 范围（本子项 L1 应 ≤ %g）'
                % columns[-1])
    if value is None:
        table = load_table_of(kind, key)
        index = columns.index(limit)
        for step in range(index + 1, min(len(columns), len(table))):
            if table[step] is not None:
                return ('允许垂直荷载：表 1 中本子项 L1≤%g 这一档无值'
                        '（L1≤%g 起才给出荷载）' % (limit, columns[step]))
        return '允许垂直荷载：表 1 中本子项无可用档位'
    factor = HORIZONTAL_FACTOR_OF.get(kind)
    if factor is None:
        return ('允许垂直荷载 %.1f kN（表 1，L1≤%g）　水平荷载：表 1 未给出'
                % (value, limit))
    return ('允许垂直荷载 %.1f kN（表 1，L1≤%g）　允许水平荷载 %.1f kN'
            '（＝D3 × %.1f）' % (value, limit, value * factor, factor))


# 使用说明（放在弹窗里看，避免占面板高度）。
HELP_TEXT = """\
【架型】

先在面板顶部选【架型】，下面的子项 / 规格 / 上限会跟着换：

· D5 端焊三角架：横担 H 型钢 + 斜撑角钢，子项 A~D，L2 ≤ 2500。
· D6 侧焊三角架：横担、斜撑均为槽钢（GB/T 706），子项 A~D 见下表，
  L2 ≤ 1500，面板显示表 1 的允许垂直荷载；**不提供 G2 端板（生根方式）**。
  两根槽钢的**腹板外表面平齐**（同在所选直线所在的竖直平面内）。
· G12 混凝土锚固三角架：与 D6 同形（横担、斜撑都是槽钢、腹板外表面平齐、
  根部不剪切），**另加构件C —— 4 根膨胀锚栓**把构件锚在既有混凝土上；
  L2 ≤ 1500，不提供 G2 端板。
· D19 双槽钢三角架：横担、斜撑都是槽钢，但**每样两片、背靠背**（腹板外表面
  相对，净距 S），整体关于所选竖直平面对称；端部用**构件C 矩形钢板**把两片
  连成整体。子项 A~D 见下表，L2 ≤ 2000，类型 1 / 2 都有，不提供 G2 端板、
  表 1 也没有水平荷载。

【怎么用】

1. 在模型中绘制 / 点选一条水平直线段，它就是管道底标高：
   起点 P0 ＝ 焊接端面（贴墙那一端），终点 P2 ＝ 横担末端，
   直线长度 ＝ 横担总长 L2。
2. 输入 L1（P0 到斜撑交点的水平距离），预览自动重建：
   P1 ＝ P0 沿线方向 +L1，Z 移到横担边缘 ＝ 斜撑与横担的交点；
   P3 ＝ P0 的 XY 不变、Z 下移(类型1)/上移(类型2) hA+L1 ＝ 斜撑根部。
3. 点【确定】保留，点【取消】或右键放弃。
   **清单（共享支吊架库）在点【确定】时写入**：预览阶段只出几何，改参数重建
   不会反复写库。
   编号规则：名称-类型-子项-L1-L2（默认名称按架型取 D5 / D6 / G12 / D19；
   D19 图集编号末段是筋板尺寸 h×w，见注 3 —— 本版不建筋板，该段留空）。

【D6 侧焊子项与允许荷载】

  子项  构件A（横担）  构件B（斜撑）
   A     [12.6          [10
   B     [16a           [12.6
   C     [20a           [14a
   D     [25a           [20a

  允许垂直荷载 /kN（表 1，按 L1 查）：
  子项   L1≤500   L1≤750   L1≤1000   L1≤1250
   A      8.9       6        4.5        —
   B      14       9.8        7.4        —
   C      21       14         10        8.6
   D      26       18         13        11
  允许水平荷载 ＝ 管架编号 D3 中相同构件允许的垂直荷载 × 0.3。

【G12 混凝土锚固子项与允许荷载】

  子项  构件A    构件B    构件C（膨胀锚栓）   C     S
   A     [12.6    [10      M12×120           100   100
   B     [16a     [12.6    M16×140           100   125
   C     [20a     [14a     M20×180           200   150
   D     [25a     [20a     M20×180           200   150

  允许垂直荷载 /kN（表 1，按 L1 查）：
  子项   L1≤500   L1≤750   L1≤1000   L1≤1250
   A       6        4         3         —
   B      10        6         6         —
   C       —       10         7         5
   D       —       20        10         8

  构件C 共 4 根，全部沿 **-Y（垂直构件平面）** 穿过槽钢腹板埋入既有混凝土：
   · 横担上 2 根：自起点 P0 沿辅助线量 75 与 75+S，落在腹板高度中心；
   · 斜撑上 2 根：自斜撑根部 P3 沿**水平方向**量 75 与 75+S（与横担锚栓
     上下对齐）——斜撑是 45°，所以沿斜撑轴线量取的距离 = 水平距离 × √2。
  垫圈 / 螺母贴在腹板内侧，膨胀套管在混凝土里（做法与 G2 混凝土锚板一致）。

【D19 双槽钢子项与允许荷载】

  两片槽钢**背靠背**：腹板外表面相对、净距 S，翼缘朝外；整体关于所选竖直
  平面（管底标高所在平面）对称 —— 也就是**组合截面形心在该平面内**，而不是
  D6 那种"单片腹板外表面与该平面平齐"。横担两片的顶面仍同在所选直线上。

  构件C 是**竖直矩形钢板、法向沿梁轴**：长边沿水平法向在两片槽钢的正中间
  对称跨过去、高度与槽钢**截面高度中心对齐**（不是顶面平齐）、板厚沿梁轴；
  板贴在横担末端的**外侧**（内表面与两片端面贴合焊接，不与槽钢硬碰撞），
  两端焊在两片槽钢的腹板上，把两片连成整体。
  两片斜撑的**根部按竖直面剪切**（端面与焊接面 x = 0 平齐）。

  子项  构件A    构件B    构件C（端部连接板）   S
   A     [12.6    [10      100×60×10            60
   B     [16a     [12.6    120×80×10            70
   C     [20a     [14a     150×100×10           80
   D     [25a     [20a     150×120×10           90

  允许垂直荷载 /kN（表 1，按 L1 查；表 1 没有水平荷载一栏）：
  子项   L1≤500   L1≤750   L1≤1000   L1≤1250   L1≤1500
   A      60        40        30         —         —
   B      100       70        50         —         —
   C      150      100        70        50         —
   D      220      160       120       100        80

  类型 2（斜撑在上）与类型 1 关于横担半高平面镜像，同 D5。

【反向】
   直线画反了（起点落在横担末端）时勾选【反向】：起点改用直线另一端、
   朝向反转 180°，整组构件一起翻到正确一侧。

【生根方式】
   · **仅 D5 端焊可用**：D6 侧焊是两根槽钢的腹板外表面直接侧焊在既有钢结构
     上，G12 用构件C 膨胀锚栓锚在既有混凝土上，D19 是两片槽钢端面现场焊接
     （配筋板，见管架编号 D1）——不设端板，选中这三种架型时这一项自动禁用
     （端板、外移都不可改）。
   · 不勾选：端面直接焊接在既有钢结构 / 钢梁上。
   · 勾选【混凝土上生根】：横担、斜撑端面各加一块 G2 混凝土锚板
     （每块 4 根膨胀锚栓）。
     - 端板**背面贴在混凝土表面**（默认就是所选直线的起点平面），
       **板身完全在混凝土外侧**（沿 +X 伸向空气侧）；膨胀锚栓埋入
       端板的 -X 侧（混凝土内）。
     - 横担、斜撑**自端板正面起算**，即整体向外挪了一个板厚：
       横担实体长 = L2 − 板厚（末端仍在 P2）；斜撑根部也落到端板正面。
     - 【外移】= 端板背面相对直线起点的外移量（默认 0 mm）。如果辅助线
       起点画在混凝土面里侧，填一个外移值即可把端板连同横担、斜撑根部
       一起挪到混凝土外侧；填负值会被拒绝（那会把端板埋进混凝土）。
     - 清单里端板、锚栓与支架本体分项统计。

【尺寸约束】
   · L1 ≥ 该子项的最小 L1（保证端部切面完整）。
   · 端部余量 E ≥ 150：E 是自**斜撑上端外角**量到横担末端的距离
     （D5：E = L2−L1−√2×肢宽；D6 / G12 / D19：E = L2−L1−hB×√2/4）。
     否则斜撑上端会伸出横担末端，所以大截面时 L1 要相应减小。
   · 直线长 L2：D5 ≤ 2500，D6 / G12 ≤ 1500，D19 ≤ 2000。

【其它】
   · 子项 A~D：规格见面板；D5 为 H 型钢 + 角钢，D6 / G12 / D19 为槽钢
     （D19 每种两片，另加构件C 端部连接板）。
   · 类型 1 斜撑在下、类型 2 斜撑在上（关于横担半高平面镜像）。
   · 横担顶面正好落在所选直线上（＝管道底标高）；槽钢腹板竖直。
   · 用料可用【导出 JSON 清单】或 00-[支吊架统计] 查看。
"""

# 尚未删除的临时辅助线句柄；每次建模结束后再兜底清一遍。
_LIVE_PATHS = []


# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------


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


_FAULT_FILE = None


def _enable_fault_logging():
    """崩溃诊断：原生崩溃没有 Python 堆栈，靠 faulthandler 留下线索。"""
    global _FAULT_FILE
    try:
        if _FAULT_FILE is None:
            path = os.path.join(HERE, '模块', '日志',
                                'D5_D6_G12_D19三角架_fault.log')
            os.makedirs(os.path.dirname(path), exist_ok=True)
            _FAULT_FILE = open(path, 'a', encoding='utf-8')
            faulthandler.enable(_FAULT_FILE)
        _FAULT_FILE.write(
            '=== session start %s rev=%s ===\n'
            % (time.strftime('%Y-%m-%d %H:%M:%S'), UI_REVISION))
        _FAULT_FILE.flush()
        faulthandler.dump_traceback_later(8.0, repeat=True, file=_FAULT_FILE)
    except Exception:
        pass


def _disable_fault_logging():
    try:
        faulthandler.cancel_dump_traceback_later()
    except Exception:
        pass


def _reload_runtime_modules():
    """强制重读底层几何模块，规避 MicroStation 的模块缓存。"""
    importlib.invalidate_caches()
    try:
        importlib.reload(geom)
    except Exception:
        _log_exception('reload geom failed')


# ---------------------------------------------------------------------------
# 低层工具（直接复用底层几何模块）
# ---------------------------------------------------------------------------


def _uor_per_mm(dgn_model=None):
    return geom._uor_per_mm(dgn_model)


def mm(value, dgn_model=None):
    return geom.mm(value, dgn_model)


def _succeeded(status):
    return geom._succeeded(status)


# ---------------------------------------------------------------------------
# 临时辅助线（拉伸路径）
# ---------------------------------------------------------------------------


# 注：不再调用 ElementPropertiesSetter 之类的原生属性接口去"隐藏"辅助线——
# 该 API 未经本仓库验证，反复调用有崩溃风险。辅助线在同一个建模调用内
# 创建并删除（见 _sweep_profile_along_path 的 finally），不会留存到模型里。


def _create_path_line(dgn_model, start_local, end_local, to_world):
    """在模型中创建一条**临时辅助线**（拉伸路径）。

    返回 EditElementHandle；创建失败返回 None（调用方会退回按端点计算扫掠向量，
    建模逻辑不受影响）。
    """
    try:
        a = to_world(start_local)
        b = to_world(end_local)
        point_a = DPoint3d(mm(a[0], dgn_model), mm(a[1], dgn_model),
                           mm(a[2], dgn_model))
        point_b = DPoint3d(mm(b[0], dgn_model), mm(b[1], dgn_model),
                           mm(b[2], dgn_model))
        handle = EditElementHandle()
        status = LineHandler.CreateLineElement(
            handle, None, DSegment3d(point_a, point_b), dgn_model.Is3d(),
            dgn_model)
    except Exception:
        _log_exception('create path line failed')
        return None
    if not _succeeded(status):
        return None
    try:
        if not _succeeded(handle.AddToModel()):
            return None
    except Exception:
        _log_exception('add path line failed')
        return None
    return handle


def _discard_path(handle):
    """无条件删除辅助线；成功与否都返回布尔值，不抛异常。"""
    deleted = False
    if handle is not None:
        try:
            if handle.IsValid():
                handle.DeleteFromModel()
                deleted = True
        except Exception:
            _log_exception('delete path line failed')
    try:
        _LIVE_PATHS.remove(handle)
    except Exception:
        pass
    return deleted


def _purge_paths():
    """建模结束后的兜底清理：把还没删掉的辅助线全部删掉。"""
    while _LIVE_PATHS:
        _discard_path(_LIVE_PATHS[-1])


def _segment_from_path(handle):
    """从刚创建的辅助线元素里读回路径线段；读不到返回 None。"""
    if handle is None:
        return None
    try:
        curve = ICurvePathQuery.ElementToCurveVector(handle)
        if curve is None:
            return None
        for primitive in curve:
            if (primitive.GetCurvePrimitiveType()
                    == ICurvePrimitive.eCURVE_PRIMITIVE_TYPE_Line):
                return primitive.GetLine()
    except Exception:
        _log_exception('read path line failed')
    return None


def _sweep_vector_from_path(dgn_model, path_handle, start_local, end_local,
                            to_world_vector):
    """扫掠向量：**优先从辅助线元素读回**；读不到再按端点计算。"""
    segment = _segment_from_path(path_handle)
    if segment is not None:
        try:
            return DVec3d(segment.EndPoint.x - segment.StartPoint.x,
                          segment.EndPoint.y - segment.StartPoint.y,
                          segment.EndPoint.z - segment.StartPoint.z)
        except Exception:
            _log_exception('build sweep vector failed')
    delta = (end_local[0] - start_local[0],
             end_local[1] - start_local[1],
             end_local[2] - start_local[2])
    return geom._sweep_vector(delta, dgn_model, to_world_vector)


def _sweep_profile_along_path(dgn_model, profile_points, path_start,
                              path_end, to_world, to_world_vector,
                              component_name, cutter_boxes=()):
    """先画辅助线 → 沿该路径拉伸轮廓 → 按需要布尔剪切 → **无条件删除辅助线**。

    ``profile_points`` 为局部坐标（mm）闭合轮廓；``path_start`` / ``path_end``
    为辅助线两端的局部坐标；``cutter_boxes`` 为若干 ``(最小点, 最大点)`` 局部
    包围盒，用于端面剪切。返回实体元素；任一步失败返回 None。
    """
    path_handle = _create_path_line(dgn_model, path_start, path_end, to_world)
    _LIVE_PATHS.append(path_handle)
    try:
        profile = geom._create_shape(profile_points, dgn_model, to_world)
        if profile is None:
            _log('%s: profile shape failed' % component_name)
            return None
        body_result = SolidUtil.Convert.ElementToBody(profile, True, True,
                                                      False)
        try:
            profile.DeleteFromModel()
        except Exception:
            pass
        if body_result is None or not _succeeded(body_result[0]):
            _log('%s: profile to body failed' % component_name)
            return None
        body = body_result[1]

        sweep = _sweep_vector_from_path(dgn_model, path_handle, path_start,
                                        path_end, to_world_vector)
        if not _succeeded(SolidUtil.Modify.SweepBody(body, sweep)):
            _log('%s: sweep failed' % component_name)
            return None

        for index, box in enumerate(cutter_boxes):
            cutter = geom._create_box_body(box[0], box[1], dgn_model,
                                           to_world)
            if cutter is None:
                _log('%s: cutter %d failed' % (component_name, index))
                return None
            if not geom._subtract_body(body, cutter):
                _log('%s: boolean cut %d failed' % (component_name, index))
                return None
        return geom._body_to_element(body, dgn_model, component_name)
    finally:
        # 无论成功与否，辅助线一律删除。
        _discard_path(path_handle)


# ---------------------------------------------------------------------------
# 参数与辅助点
# ---------------------------------------------------------------------------


def min_l1(variant_key):
    """该子项允许的最小 L1：保证端部剪切后斜撑仍有完整截面。"""
    angle_width, angle_thickness = geom.VARIANTS[variant_key]['angle']
    return max(MIN_L1, (angle_width + angle_thickness) * math.sqrt(2.0) / 2.0
               + 50.0)


def min_l1_of(kind, variant_key):
    """该子项允许的最小 L1：保证端部剪切后斜撑仍有完整截面。"""
    if kind in CHANNEL_KINDS:
        brace = CHANNEL_SECTIONS[channel_variant_of(kind, variant_key)['comp_b']]
        return max(MIN_L1, brace[0] * math.sqrt(2.0) / 4.0 + 50.0)
    return min_l1(variant_key)


def toe_offset_of(kind, variant_key):
    """斜撑上端被水平面切出的端面，自交点沿 +X 向外的伸出量（mm）。

    D5（角钢）：√2×肢宽；D6 / G12 / D19（槽钢，45°，截面高 hB）：hB×√2/4。
    """
    if kind in CHANNEL_KINDS:
        brace = CHANNEL_SECTIONS[channel_variant_of(kind, variant_key)['comp_b']]
        return brace[0] * math.sqrt(2.0) / 4.0
    return math.sqrt(2.0) * geom.VARIANTS[variant_key]['angle'][0]


def brace_face_offset_of(kind, variant_key):
    """斜撑根部端面中心相对轴线的偏移（D5 角钢不对称，槽钢对称）。"""
    if kind in CHANNEL_KINDS:
        return 0.0
    return geom.VARIANTS[variant_key]['angle'][0] * math.sqrt(2.0) / 2.0


def compute_points(l2_mm, l1_mm, beam_height, brace_down):
    """四个辅助点（局部坐标，mm）。P0 为原点，+X 沿直线。"""
    p0 = (0.0, 0.0, 0.0)
    p2 = (float(l2_mm), 0.0, 0.0)
    if brace_down:
        # 类型 1：P1 在横担下翼缘底面，P3 贴墙面向下（45° 时下落 L1）。
        p1 = (float(l1_mm), 0.0, -beam_height)
        p3 = (0.0, 0.0, -beam_height - float(l1_mm))
    else:
        # 类型 2（镜像）：P1 在横担上翼缘顶面，P3 贴墙面向上。
        p1 = (float(l1_mm), 0.0, 0.0)
        p3 = (0.0, 0.0, float(l1_mm))
    return {'P0': p0, 'P1': p1, 'P2': p2, 'P3': p3}


def orient_line(line, reverse=False):
    """按「起点＝焊接端面」的口径返回辅助线**副本**（与 N3 同款）。

    辅助线约定**起点**为焊接端面、**方向**为由端面向外；直线画反了
    （起点落在横担末端）时用 ``reverse=True`` 交换两端：起点取原终点、
    朝向反转 180°，于是 P0…P3 与整组构件一起翻到正确一侧。

    ``length_mm`` / ``z_mm`` 不变；不修改传入的字典（``reverse=False`` 时也返回副本）。
    """
    oriented = dict(line)
    if not reverse:
        return oriented

    start = line.get('start_mm')
    end = line.get('end_mm')
    if start is not None and end is not None:
        oriented['start_mm'] = tuple(end)
        oriented['end_mm'] = tuple(start)

    try:
        heading = float(line.get('heading_deg') or 0.0) + 180.0
    except (TypeError, ValueError):
        heading = 0.0
    # 归一化到 (-180, 180]，与 extract_horizontal_line() 的 atan2 取值域一致。
    while heading > 180.0:
        heading -= 360.0
    while heading <= -180.0:
        heading += 360.0
    oriented['heading_deg'] = heading
    return oriented


def resolve_geometry(line, l1_mm, variant_key, rack_type, reverse=False,
                     add_plate=False, plate_subtype=DEFAULT_PLATE_SUBTYPE,
                     plate_offset_mm=0.0, kind=DEFAULT_KIND):
    """校验选项并算出本次建模需要的全部尺寸与辅助点。

    ``kind`` 为架型：``'D5'`` 端焊（H 型钢横担 + 角钢斜撑，L2 ≤ 2500）、
    ``'D6'`` 侧焊 / ``'G12'`` 混凝土锚固 / ``'D19'`` 双槽钢（横担、斜撑均为
    槽钢；L2 ≤ 1500 / 1500 / 2000，表 1 档位与水平荷载按架型取）。

    ``reverse=True`` 时先按「起点＝焊接端面」翻转所选直线（见 ``orient_line``）。
    ``add_plate=True`` 表示**混凝土上生根**：在横担、斜撑的端面各加一块
    G2 混凝土锚板（含 4 根膨胀锚栓）。端板**背面贴在混凝土表面**（默认就是
    所选直线的起点平面）、**板身在混凝土外侧**，横担 / 斜撑自端板正面起算。
    ``plate_offset_mm`` 为端板背面相对直线起点的**外移量**（mm，默认 0）：
    辅助线起点若画在混凝土面里侧，填一个外移值即可把端板（连同横担、斜撑
    根部）一起挪到混凝土外侧；不允许填负值（会把端板埋进混凝土）。
    """
    if kind not in KIND_KEYS:
        kind = DEFAULT_KIND
    keys = variant_keys_of(kind)
    if variant_key not in keys:
        raise ValueError('未知子项：%s。' % variant_key)
    beam_spec, brace_spec, spec_a_text, spec_b_text = variant_specs(kind,
                                                                   variant_key)
    max_length = kind_max_length(kind)
    reverse = bool(reverse)
    oriented_line = orient_line(line, reverse)

    l2 = float(line['length_mm'])
    if l2 > max_length + 1.0e-9:
        raise ValueError(
            '直线长 L2=%.0f mm 超出上限 %.0f mm，请缩短所选辅助线'
            '（%s 横担总长不得大于 %.0f）。'
            % (l2, max_length, kind, max_length))

    try:
        l1 = float(l1_mm)
    except (TypeError, ValueError):
        raise ValueError('L1 必须是数字（mm）。')
    lowest = min_l1_of(kind, variant_key)
    if l1 < lowest - 1.0e-9:
        raise ValueError('L1=%.0f mm 过小：该子项要求 L1 ≥ %.0f mm。'
                         % (l1, lowest))

    # 斜撑上端被水平面切出的端面，会自交点 P1 起继续向横担末端伸出一段
    # （D5 角钢 √2×肢宽；D6 槽钢 hB×√2/4）—— 端部余量必须从**斜撑上端外角**
    # 量起（与标准图 150 (MIN.) 一致），否则斜撑上端会探出横担末端。
    toe_offset = toe_offset_of(kind, variant_key)
    end_overhang = l2 - l1 - toe_offset
    if end_overhang < MIN_END_OVERHANG - 1.0e-9:
        raise ValueError(
            '端部余量 E=L2−L1−斜撑上端伸出量=%.0f mm 小于 %.0f mm（斜撑上端会'
            '伸出横担末端）：请加大直线长 L2 或减小 L1，要求 L2−L1 ≥ %.0f + %.0f'
            ' = %.0f mm。'
            % (end_overhang, MIN_END_OVERHANG, toe_offset, MIN_END_OVERHANG,
               toe_offset + MIN_END_OVERHANG))

    try:
        rack_type = int(rack_type)
    except (TypeError, ValueError):
        raise ValueError('类型必须是 1 或 2。')
    if rack_type not in TYPE_KEYS:
        raise ValueError('类型只支持 1（斜撑在下）/ 2（斜撑在上）。')
    brace_down = rack_type == 1

    # G12：斜撑上的两根锚栓按**水平距离** 75 / 75+S 定位，L1 太短时第 2 根会
    # 落到斜撑之外，这里直接拦下并给出所需 L1。
    if kind == 'G12':
        tail = (G12_FIRST_BOLT_OFFSET
                + float(G12_VARIANTS[variant_key]['s']))
        lowest_bolt = tail + 50.0
        if l1 < lowest_bolt - 1.0e-9:
            raise ValueError(
                'L1=%.0f mm 太短：斜撑上第 2 根锚栓在水平 %.0f mm 处'
                '（75+S，S=%.0f），会落到斜撑之外；该子项要求 L1 ≥ %.0f mm。'
                % (l1, tail, float(G12_VARIANTS[variant_key]['s']),
                   lowest_bolt))

    # 混凝土上生根（G2 端板）只用于 D5；D6 侧焊、G12 混凝土锚固、D19 双槽钢
    # 都不设端板（G12 用构件C 膨胀锚栓锚在既有混凝土上，D19 是两片端面现场
    # 焊接 + 筋板），传进来也一律按不加端板处理。
    add_plate = bool(add_plate) and kind not in CHANNEL_KINDS
    resolved_plate = None
    plate_t = 0.0
    plate_offset = 0.0
    if add_plate:
        try:
            resolved_plate = geom._resolve_plate_options(
                plate_subtype, oriented_line['heading_deg'], beam_spec)
        except ValueError as error:
            raise ValueError('G2 端板参数有误：%s' % error)
        plate_t = float(resolved_plate['plate_t'])
        try:
            plate_offset = float(plate_offset_mm or 0.0)
        except (TypeError, ValueError):
            raise ValueError('端板外移必须是数字（mm）。')
        if plate_offset < -1.0e-9:
            raise ValueError('端板外移不能为负值：那会把端板埋进混凝土里，'
                             '板应当留在混凝土外侧（外移 ≥ 0）。')
        # 端板背面在 x = plate_offset（默认 0，即混凝土表面），
        # 板身占 [offset, offset + T]，横担 / 斜撑根部自板正面 (offset + T) 起。
        if l2 - plate_offset - plate_t <= l1:
            raise ValueError(
                '端板外移 %.0f + 板厚 %.0f 之后横担实体只剩 %.0f mm，'
                '请加大直线长 L2 或减小外移量。'
                % (plate_offset, plate_t, l2 - plate_offset - plate_t))

    beam_start = plate_offset + plate_t
    beam_height = beam_spec[0]
    points = compute_points(l2, l1, beam_height, brace_down)
    brace_length = math.hypot(points['P1'][0] - points['P3'][0],
                              points['P1'][2] - points['P3'][2])
    # G12 构件C（膨胀锚栓）：子项对应的锚栓规格与 C、S 尺寸。
    bolt_subtype = ''
    bolt_spec = ''
    bolt_s = 0.0
    bolt_c = 0.0
    if kind == 'G12':
        g12 = G12_VARIANTS[variant_key]
        bolt_subtype = g12['bolt_subtype']
        bolt_spec = g12['bolt_spec']
        bolt_s = float(g12['s'])
        bolt_c = float(g12['c'])
    # D19 构件C（端部连接板）与两片槽钢的腹板外表面间距 S。
    connector = None
    connector_count = 0
    web_gap = 0.0
    if kind == 'D19':
        d19 = D19_VARIANTS[variant_key]
        connector = tuple(float(value) for value in d19['comp_c'])
        connector_count = int(D19_CONNECTOR_COUNT)
        web_gap = float(d19['s'])
    return {
        'kind': kind,
        'variant': variant_key,
        'rack_type': rack_type,
        'brace_down': brace_down,
        'reverse': reverse,
        'line': oriented_line,
        'L1': l1,
        'L2': l2,
        'max_length': max_length,
        'toe_offset': toe_offset,
        'end_overhang': end_overhang,
        'add_plate': add_plate,
        'plate': resolved_plate,
        'plate_t': plate_t,
        'plate_offset': plate_offset,
        'beam_start': beam_start,
        'beam_length': l2 - beam_start,
        'beam_height': beam_height,
        'points': points,
        'h_beam': beam_spec,
        'brace_section': brace_spec,
        'angle': brace_spec,
        'h_beam_specification': spec_a_text,
        'angle_specification': spec_b_text,
        'brace_face_offset': brace_face_offset_of(kind, variant_key),
        'allowable_load': allowable_load(kind, variant_key, l1),
        'brace_length': brace_length,
        'min_l1': lowest,
        'anchors': anchor_positions_of(kind, variant_key, points, beam_spec,
                                       brace_spec),
        'bolt_subtype': bolt_subtype,
        'bolt_spec': bolt_spec,
        'bolt_s': bolt_s,
        'bolt_c': bolt_c,
        # D19：两片槽钢（背靠背、净距 web_gap）+ 构件C 端部连接板。
        'connector': connector,
        'connector_count': connector_count,
        'web_gap': web_gap,
    }


def anchor_positions_of(kind, variant_key, points, beam_spec, brace_spec):
    """G12 构件C（膨胀锚栓）的定位（纯几何，便于单测）。

    返回 4 条记录，``where`` 为 ``'beam'`` / ``'brace'``，``x`` / ``z`` 为
    栓杆轴线所在的局部坐标（y 恒为 0，即构件平面）；``offset`` 为**水平距离**
    （横担：自 P0 沿辅助线；斜撑：自根部 P3 沿水平方向量），
    ``axis_offset`` 为斜撑沿自身轴线量取的距离（45° 时 = offset×√2）。
    锚栓沿 **−Y** 埋入混凝土，穿过槽钢腹板，螺母/垫圈在腹板内侧。
    """
    if kind != 'G12':
        return []
    variant = G12_VARIANTS[variant_key]
    first = G12_FIRST_BOLT_OFFSET
    second = first + float(variant['s'])
    mid_z = -float(beam_spec[0]) / 2.0          # 横担腹板高度中心
    p1, p3 = points['P1'], points['P3']
    axis = (p1[0] - p3[0], p1[2] - p3[2])
    length = math.hypot(axis[0], axis[1])
    anchors = []
    for offset in (first, second):
        anchors.append({'where': 'beam', 'offset': offset, 'axis_offset': offset,
                        'x': offset, 'z': mid_z,
                        'web_t': float(beam_spec[2])})
    if length > 0.0:
        ux, uz = axis[0] / length, axis[1] / length
        for offset in (first, second):
            # 图纸给的是**水平距离**（与横担锚栓同一量法，上下对齐），
            # 斜撑是 45°，沿自身轴线量取时要换算：d = 水平距离 / |轴线 X 分量|
            # （45° 即 水平×√2）。
            step = offset / abs(ux) if abs(ux) > 1.0e-9 else offset
            anchors.append({'where': 'brace', 'offset': offset,
                            'axis_offset': step,
                            'x': p3[0] + ux * step,
                            'z': p3[2] + uz * step,
                            'web_t': float(brace_spec[2])})
    return anchors


def build_number(name, rack_type, variant_key, l1_mm, l2_mm, stiffener=None):
    """管架编号：``名称-类型-子项-L1-L2``（D19 可再带一段 ``-h×w`` 筋板尺寸）。

    名称为空则不附加编号。``stiffener`` 是 D19 图集编号末段的筋板尺寸文字
    （注 3：不需要筋板时本项缺省）——留空则不追加该段；本版不建筋板实体，
    面板也不给输入框，先把这个接口留好。
    """
    label = str(name or '').strip()
    if not label:
        return ''
    number = '%s-%d-%s-%d-%d' % (label, int(rack_type), variant_key,
                                 int(math.floor(float(l1_mm) + 0.5)),
                                 int(math.floor(float(l2_mm) + 0.5)))
    tail = str(stiffener or '').strip()
    if tail:
        number = '%s-%s' % (number, tail)
    return number


# ---------------------------------------------------------------------------
# 构件建模
# ---------------------------------------------------------------------------


def _build_beam(dgn_model, to_world, to_world_vector, resolved):
    """横担：返回本次要加入单元的实体元素**列表**（D19 两片 → 2 个元素）。

    D5：辅助线过截面形心（翼缘中心），顶面正好落在用户所选直线上；加 G2 端板
    （混凝土生根）时，横担自端板正面起（局部 x = 外移量 + 板厚），末端仍在 P2。
    D6 / G12：单片槽钢，腹板外表面就在构件平面内（y = 0）、翼缘朝 +Y。
    D19：两片槽钢**背靠背**（腹板外表面相对、净距 S），关于所选竖直平面对称。
    """
    kind = resolved.get('kind')
    if kind in DOUBLE_CHANNEL_KINDS:
        return _build_double_channel_beam(dgn_model, to_world, to_world_vector,
                                          resolved)
    if kind in CHANNEL_KINDS:
        element = _build_channel_beam(dgn_model, to_world, to_world_vector,
                                      resolved)
        return [element] if element is not None else []
    height, width, web_t, flange_t = resolved['h_beam']
    length = resolved['L2']
    start_x = float(resolved.get('beam_start') or 0.0)
    if start_x >= length:
        return []
    half_width = width / 2.0
    half_web = web_t / 2.0
    # 轮廓画在路径起点所在的剖面内、并相对路径起点居中：
    # 辅助线在 z=-hA/2（形心）处，轮廓 z 范围取 [-hA, 0]，
    # 扫掠后顶面正好回到 z=0，即用户所选直线（管道底标高）；
    # 底面在 z=-hA，与斜撑顶端的水平剪切面（z=-hA）严丝合缝。
    top = 0.0
    bottom = -height
    top_inner = -flange_t
    bottom_inner = -height + flange_t

    profile_points = [
        (start_x, -half_width, bottom),
        (start_x, half_width, bottom),
        (start_x, half_width, bottom_inner),
        (start_x, half_web, bottom_inner),
        (start_x, half_web, top_inner),
        (start_x, half_width, top_inner),
        (start_x, half_width, top),
        (start_x, -half_width, top),
        (start_x, -half_width, top_inner),
        (start_x, -half_web, top_inner),
        (start_x, -half_web, bottom_inner),
        (start_x, -half_width, bottom_inner),
    ]
    # 辅助线 = (P0 + 板厚)→P2 下移 hA/2；沿它拉伸即得到顶面在所选直线上的横担。
    path_start = (start_x, 0.0, -height / 2.0)
    path_end = (length, 0.0, -height / 2.0)
    element = _sweep_profile_along_path(dgn_model, profile_points, path_start,
                                        path_end, to_world, to_world_vector,
                                        COMPONENT_A_NAME)
    return [element] if element is not None else []


def _build_brace(dgn_model, to_world, to_world_vector, resolved):
    """斜撑：沿 P3→P1 轴线（45°）拉伸角钢，两端各做一次布尔剪切。

    返回实体元素**列表**（D19 两片 → 2 个元素），失败返回空列表。
    """
    kind = resolved.get('kind')
    if kind in DOUBLE_CHANNEL_KINDS:
        return _build_double_channel_brace(dgn_model, to_world, to_world_vector,
                                           resolved)
    if kind in CHANNEL_KINDS:
        element = _build_channel_brace(dgn_model, to_world, to_world_vector,
                                       resolved)
        return [element] if element is not None else []
    angle_width, angle_thickness = resolved['angle']
    points = resolved['points']
    # 加 G2 端板时斜撑根部改到端板正面（局部 x = 外移量 + 板厚），与端板焊接。
    wall_cut_x = float(resolved.get('beam_start') or 0.0)
    p1 = points['P1']
    p3 = points['P3']
    brace_down = resolved['brace_down']

    axis = (p1[0] - p3[0], p1[1] - p3[1], p1[2] - p3[2])
    length = math.sqrt(axis[0] ** 2 + axis[1] ** 2 + axis[2] ** 2)
    if length <= 0.0:
        return []
    u = (axis[0] / length, axis[1] / length, axis[2] / length)
    u_h = math.hypot(u[0], u[1])
    if u_h <= 1.0e-9:
        return []
    # 竖直平面内与轴线垂直的方向：类型 1 指向"前下"，类型 2 镜像为"前上"。
    sign = 1.0 if brace_down else -1.0
    face = (sign * u[2] * u[0] / u_h, sign * u[2] * u[1] / u_h, -sign * u_h)

    # 两端各延长一段，保证剪切后端面完整（45° 时均为 肢宽+肢厚）。
    start_overrun = ((angle_width + angle_thickness) * abs(u[2])
                     / max(u_h, 1.0e-6))
    end_overrun = ((angle_width + angle_thickness) * u_h
                   / max(abs(u[2]), 1.0e-6))
    raw_length = start_overrun + length + end_overrun

    # 角钢背（外角点）沿 Y 居中于所选直线：局部 y = −肢宽/2。
    corner = (p3[0] - u[0] * start_overrun,
              -angle_width / 2.0 - u[1] * start_overrun,
              p3[2] - u[2] * start_overrun)
    path_end = (corner[0] + u[0] * raw_length,
                corner[1] + u[1] * raw_length,
                corner[2] + u[2] * raw_length)

    def shift(base, y_offset, face_offset):
        return (base[0] + face[0] * face_offset,
                base[1] + y_offset + face[1] * face_offset,
                base[2] + face[2] * face_offset)

    w = angle_width
    t = angle_thickness
    profile_points = [
        corner,
        shift(corner, w, 0.0),
        shift(corner, w, t),
        shift(corner, t, t),
        shift(corner, t, w),
        shift(corner, 0.0, w),
    ]

    # 剪切盒必须完整包住整个扫掠实体，否则端部会残留没切掉的碎块
    # （截面越大越明显：盒底曾按 肢宽+肢厚+50 取，子项 D 会差 28.7mm 切不到）。
    # 实体 = 轮廓多边形的起点与终点两套顶点，取包围盒后再给足余量。
    sweep_vec = (u[0] * raw_length, u[1] * raw_length, u[2] * raw_length)
    far_points = [(point[0] + sweep_vec[0],
                   point[1] + sweep_vec[1],
                   point[2] + sweep_vec[2]) for point in profile_points]
    all_points = list(profile_points) + far_points
    pad = (angle_width + angle_thickness) * 2.0 + 100.0
    x_min = min(point[0] for point in all_points) - pad
    x_max = max(point[0] for point in all_points) + pad
    y_min = min(point[1] for point in all_points) - pad
    y_max = max(point[1] for point in all_points) + pad
    z_min = min(point[2] for point in all_points) - pad
    z_max = max(point[2] for point in all_points) + pad
    # 剪切一：贴墙面（无端板）或贴端板正面（有端板）的竖直面。
    wall_box = ((x_min, y_min, z_min), (wall_cut_x, y_max, z_max))
    # 剪切二：与横担接触端的水平面（类型 1 取下翼缘底面，类型 2 取上翼缘顶面）。
    if brace_down:
        contact_box = ((x_min, y_min, p1[2]), (x_max, y_max, z_max))
    else:
        contact_box = ((x_min, y_min, z_min), (x_max, y_max, p1[2]))

    element = _sweep_profile_along_path(dgn_model, profile_points, corner,
                                        path_end, to_world, to_world_vector,
                                        COMPONENT_B_NAME,
                                        (wall_box, contact_box))
    return [element] if element is not None else []


# ---------------------------------------------------------------------------
# 槽钢架型（D6 侧焊 / G12 混凝土锚固 / D19 双槽钢）：槽钢横担 / 斜撑
# ---------------------------------------------------------------------------


def _channel_profile(channel, n_dir, y_outer, y_sign, path_point):
    """槽钢截面轮廓（局部坐标，mm）。

    * ``channel`` = (高 H, 翼缘宽 B, 腹板厚 tw, 翼缘厚 tf)；
    * ``n_dir`` = 截面**高度方向**的单位向量（在局部 XZ 平面内，y 分量为 0）；
    * **腹板外表面**位于局部 ``y = y_outer``（D6 / G12 取 0，即构件平面；
      D19 两片取 ∓S/2），翼缘朝 ``y_sign`` 方向伸出 ``B``。

    这样横担与斜撑的**腹板外表面落在同一个平面 y = 0 上**（相互平齐），
    与标准图中"两根槽钢腹板外表面平齐"的做法一致。
    """
    height, width, tw, tf = channel
    half = height / 2.0
    # (y, s)：y 自腹板外表面起算（朝开口方向为正），s 为截面高度方向。
    outline = (
        (0.0, -half),           # 腹板外表面 · 下
        (0.0, half),            # 腹板外表面 · 上
        (width, half),          # 上翼缘外缘 · 端部
        (width, half - tf),     # 上翼缘端面
        (tw, half - tf),        # 上翼缘内表面
        (tw, -half + tf),       # 腹板内表面
        (width, -half + tf),    # 下翼缘内表面
        (width, -half),         # 下翼缘端面
    )
    points = []
    for y, s in outline:
        points.append((path_point[0] + n_dir[0] * s,
                       y_outer + y_sign * y,
                       path_point[2] + n_dir[2] * s))
    return points


def _build_channel_beam(dgn_model, to_world, to_world_vector, resolved,
                        y_outer=0.0, y_sign=1.0):
    """槽钢横担：沿 +X 拉伸。

    辅助线过**截面形心高度**（z = −hA/2），截面高在 Z 向占 [−hA, 0]，
    因此顶面正好落在所选直线上（＝管道底标高），底面在 −hA；腹板竖直。

    ``y_outer`` / ``y_sign`` 给出**腹板外表面**的局部 y 位置与翼缘朝向：
    D6 / G12 取 (0, +1)（腹板外表面就在构件平面内）；D19 的两片分别取
    (−S/2, −1) 与 (+S/2, +1) —— 背靠背、腹板外表面相对、净距 S。
    """
    channel = resolved['h_beam']
    height = channel[0]
    start_x = float(resolved.get('beam_start') or 0.0)
    length = float(resolved['L2'])
    if start_x >= length:
        return None
    path_start = (start_x, 0.0, -height / 2.0)
    path_end = (length, 0.0, -height / 2.0)
    profile_points = _channel_profile(channel, (0.0, 0.0, 1.0), y_outer,
                                      y_sign, path_start)
    return _sweep_profile_along_path(dgn_model, profile_points, path_start,
                                     path_end, to_world, to_world_vector,
                                     COMPONENT_A_NAME)


def _build_double_channel_beam(dgn_model, to_world, to_world_vector, resolved):
    """D19 横担：两片**背靠背**槽钢（腹板外表面相对、净距 S）。

    两片都画在同一个局部坐标系里：腹板外表面分别在 y = ∓S/2、翼缘朝外，
    所以整组关于所选竖直平面（y = 0）对称 —— 即组合截面形心在该平面内，
    而不是 D6 那种"单片腹板外表面与该平面平齐"。
    """
    web_gap = float(resolved.get('web_gap') or 0.0)
    elements = []
    for sign in (-1.0, 1.0):
        element = _build_channel_beam(dgn_model, to_world, to_world_vector,
                                      resolved, sign * web_gap / 2.0, sign)
        if element is None:
            return []
        elements.append(element)
    return elements


def channel_brace_layout(channel, p1, p3, brace_down, wall_cut_x=0.0,
                         cut_root=True, y_outer=0.0, y_sign=1.0):
    """槽钢斜撑的纯几何布置（不依赖 MSPy，便于单测）。

    ``cut_root=False`` 表示**根部不做布尔剪切**（侧焊工况）：斜撑直接从
    焊接面（或端板正面）沿轴线扫出，端面就是槽钢的自然端面（与轴线垂直的
    45° 斜端面），不再切竖直面。

    ``y_outer`` / ``y_sign`` 同 :func:`_build_channel_beam`：D6 / G12 取
    (0, +1)，D19 两片分别取 (∓S/2, ∓1)。

    返回 ``dict(profile, start_point, path_end, cutters)``：
    轮廓点、辅助线两端与需要做的剪切盒（局部坐标 mm，可能只有一个）。
    """
    height = float(channel[0])
    thickness = float(channel[2])
    axis = (p1[0] - p3[0], p1[1] - p3[1], p1[2] - p3[2])
    length = math.sqrt(axis[0] ** 2 + axis[1] ** 2 + axis[2] ** 2)
    if length <= 0.0:
        return None
    u = (axis[0] / length, axis[1] / length, axis[2] / length)
    u_h = math.hypot(u[0], u[1])
    if u_h <= 1.0e-9:
        return None
    # 局部 XZ 平面内与轴线垂直的方向（截面高度方向；轮廓关于它对称）。
    n_dir = (-u[2], 0.0, u[0])
    # 上端（与横担接触端）延长一段，保证水平剪切后端面完整
    # （45° 时 0.354×hB 就够，取更保险的值）。
    overrun = height + thickness
    if cut_root:
        # 端板工况：根部按竖直面剪切，需要先延长保证切面完整。
        start_point = (p3[0] - u[0] * overrun, 0.0, p3[2] - u[2] * overrun)
    else:
        # 侧焊工况：根部不剪切，直接从焊接面（x = wall_cut_x）沿轴线起拉伸，
        # 端面即槽钢的自然端面（与轴线垂直的 45° 斜端面）。
        t0 = (float(wall_cut_x) - p3[0]) / u[0]
        start_point = (p3[0] + u[0] * t0, 0.0, p3[2] + u[2] * t0)
    path_end = (p1[0] + u[0] * overrun, 0.0, p1[2] + u[2] * overrun)
    profile_points = _channel_profile(channel, n_dir, y_outer, y_sign,
                                      start_point)

    # 剪切盒按扫掠实体的真实包围盒放大，确保完整包住（截面越大余量越要足）。
    raw_length = math.hypot(path_end[0] - start_point[0],
                            path_end[2] - start_point[2])
    sweep_vec = (u[0] * raw_length, 0.0, u[2] * raw_length)
    far_points = [(p[0] + sweep_vec[0], p[1] + sweep_vec[1],
                   p[2] + sweep_vec[2]) for p in profile_points]
    all_points = list(profile_points) + far_points
    pad = (height + thickness) * 2.0 + 100.0
    x_min = min(p[0] for p in all_points) - pad
    x_max = max(p[0] for p in all_points) + pad
    y_min = min(p[1] for p in all_points) - pad
    y_max = max(p[1] for p in all_points) + pad
    z_min = min(p[2] for p in all_points) - pad
    z_max = max(p[2] for p in all_points) + pad
    cutters = []
    # 剪切一（仅端板工况）：贴端板正面的竖直面。
    if cut_root:
        cutters.append(((x_min, y_min, z_min),
                        (float(wall_cut_x), y_max, z_max)))
    # 剪切二：与横担接触端的水平面（类型 1 取下翼缘底面，类型 2 取上翼缘顶面）。
    if brace_down:
        cutters.append(((x_min, y_min, float(p1[2])), (x_max, y_max, z_max)))
    else:
        cutters.append(((x_min, y_min, z_min), (x_max, y_max, float(p1[2]))))
    return {
        'axis': u,
        'profile': profile_points,
        'start_point': start_point,
        'path_end': path_end,
        'raw_length': raw_length,
        'cutters': cutters,
        'cut_root': bool(cut_root),
    }


def _build_channel_brace(dgn_model, to_world, to_world_vector, resolved,
                         y_outer=0.0, y_sign=1.0):
    """槽钢斜撑：沿 P3→P1 的 45° 轴线拉伸。

    腹板外表面的局部 y 位置与翼缘朝向由 ``y_outer`` / ``y_sign`` 给出：
    D6 / G12 取 (0, +1)（腹板外表面与横担平齐、同在构件平面内）；D19 两片
    分别取 (∓S/2, ∓1)，与横担两片一一对应。

    根部处理：**D19 按竖直面剪切**（端面与焊接面 x = 0 平齐，见
    ``D19_BRACE_ROOT_CUT``）；D6 / G12 侧焊**不剪切**（端面即槽钢的 45° 自然
    端面）；加 G2 端板时切在端板正面（那才是焊面）。与横担接触端始终按水平面
    剪切。
    """
    channel = resolved['brace_section']
    points = resolved['points']
    # 根部剪切：D19 要切成**竖直面**（端面与焊接面 x = 0 平齐）；D6 / G12 侧焊
    # 不剪切（端面即槽钢的 45° 自然端面）；只有加了 G2 端板时才切在端板正面。
    cut_root = (float(resolved.get('plate_t') or 0.0) > 0.0
                or (D19_BRACE_ROOT_CUT
                    and resolved.get('kind') in DOUBLE_CHANNEL_KINDS))
    layout = channel_brace_layout(channel, points['P1'], points['P3'],
                                  resolved['brace_down'],
                                  float(resolved.get('beam_start') or 0.0),
                                  cut_root, y_outer, y_sign)
    if layout is None:
        return None
    return _sweep_profile_along_path(dgn_model, layout['profile'],
                                     layout['start_point'],
                                     layout['path_end'], to_world,
                                     to_world_vector, COMPONENT_B_NAME,
                                     tuple(layout['cutters']))


def _build_double_channel_brace(dgn_model, to_world, to_world_vector, resolved):
    """D19 斜撑：与横担两片一一对应的两片 45° 槽钢（同样背靠背、净距 S）。"""
    web_gap = float(resolved.get('web_gap') or 0.0)
    elements = []
    for sign in (-1.0, 1.0):
        element = _build_channel_brace(dgn_model, to_world, to_world_vector,
                                       resolved, sign * web_gap / 2.0, sign)
        if element is None:
            return []
        elements.append(element)
    return elements


# ---------------------------------------------------------------------------
# D19 构件C：端部连接（加固）钢板
# ---------------------------------------------------------------------------


def connector_box(resolved):
    """构件C（端部连接板）的局部包围盒 ``(最小点, 最大点)``；非 D19 返回 None。

    按图：**竖直矩形钢板、法向沿梁轴 +X** —— 长 Ly 沿 +Y 在两片槽钢的正中间
    对称跨过去、高 Hc、厚 T 沿 X。

    * 竖直方向**中心对齐**：板高中心与槽钢**截面高度中心**（z = −hA/2）重合
      （不是顶面与横担顶面平齐）—— 于是板两端落在两片槽钢的**腹板**上焊接。
    * 沿梁轴放在横担末端的**外侧**（x ∈ [L2, L2 + T]），内表面与两片槽钢的
      **端面**贴合（焊接面），**不与腹板 / 翼缘硬碰撞**。

    若图纸实际是"水平盖板、顶在横担上面"或"沿梁轴内缩一段"，只改这里的
    三个分量方向即可（纯几何，便于单测）。
    """
    connector = resolved.get('connector')
    if not connector:
        return None
    length_y, height_c, thickness = (float(value) for value in connector)
    x_end = float(resolved['L2'])
    z_center = -float(resolved.get('beam_height') or 0.0) / 2.0
    return ((x_end, -length_y / 2.0, z_center - height_c / 2.0),
            (x_end + thickness, length_y / 2.0, z_center + height_c / 2.0))


def _build_double_channel_connector(dgn_model, to_world, resolved):
    """D19 构件C：把两片槽钢横担连成整体的端部钢板。"""
    box = connector_box(resolved)
    if box is None:
        return None
    body = geom._create_box_body(box[0], box[1], dgn_model, to_world)
    if body is None:
        _log('%s: body failed' % COMPONENT_C_NAME)
        return None
    return geom._body_to_element(body, dgn_model, COMPONENT_C_NAME)


# ---------------------------------------------------------------------------
# G12 构件C：膨胀锚栓（做法与 G2 混凝土锚板的锚栓一致）
# ---------------------------------------------------------------------------


def anchor_bolt_options(subtype, web_t):
    """按 ``混凝土锚板``(G2) 的口径展开一根膨胀锚栓的尺寸。

    G12 没有端板，"板厚"位置换成**槽钢腹板厚**：垫圈 / 螺母正好贴在腹板
    内侧，栓杆穿过腹板埋入混凝土；埋深相应加大（仍不小于表内最小埋深）。
    """
    resolved = dict(anchor.resolve_options({'subtype': subtype,
                                            'spacing': None,
                                            'heading_deg': 0.0}))
    web_t = float(web_t)
    resolved['plate_t'] = web_t
    out_len = (web_t + resolved['washer_t'] + resolved['nut_h']
               + anchor.BOLT_PROTRUSION)
    embed = resolved['bolt_length'] - out_len
    if embed < resolved['embedment_req'] - 1.0e-9:
        raise ValueError(
            'M%.0f 锚栓在腹板厚 %.1f mm 之下有效埋深只剩 %.1f mm，'
            '小于表内要求的 %.1f mm。'
            % (resolved['bolt_dia'], web_t, embed,
               resolved['embedment_req']))
    resolved['bolt_out_len'] = out_len
    resolved['embedment_actual'] = embed
    resolved['sleeve_len'] = embed * anchor.SLEEVE_EMBED_FRACTION
    return resolved


def _build_anchor_bolts(builder, dgn_model, to_world, resolved):
    """G12 构件C：4 根膨胀锚栓（横担 2 根 + 斜撑 2 根）。

    锚栓沿 **−Y**（垂直构件平面）埋入既有混凝土：栓杆穿过槽钢腹板，
    垫圈 / 螺母在腹板内侧，埋入端（膨胀套管）在混凝土里。
    返回实际加入的锚栓根数。
    """
    anchors = resolved.get('anchors') or []
    if not anchors:
        return 0
    # 锚栓规格：优先取 resolved 里的，取不到就回查表 2（防御性兜底）。
    subtype = (resolved.get('bolt_subtype')
               or G12_VARIANTS.get(resolved.get('variant'),
                                   {}).get('bolt_subtype'))
    if not subtype:
        raise ValueError('G12 构件C 缺少锚栓规格（bolt_subtype）。')
    # 锚栓局部 +X（G2 的"混凝土外法向"）= 构件平面的 +Y 方向。
    heading = float(resolved['line']['heading_deg']) + 90.0
    uor_per_mm = _uor_per_mm(dgn_model)
    count = 0
    for item in anchors:
        options = anchor_bolt_options(subtype, item.get('web_t', 0.0))
        origin_mm = to_world((item['x'], 0.0, item['z']))
        origin = DPoint3d(mm(origin_mm[0], dgn_model),
                          mm(origin_mm[1], dgn_model),
                          mm(origin_mm[2], dgn_model))
        frame = anchor._PlateFrame(origin, uor_per_mm, heading)
        anchor._add_bolt(builder, frame, dgn_model, options, 0.0, 0.0)
        count += 1
    return count


# ---------------------------------------------------------------------------
# 单元封装
# ---------------------------------------------------------------------------


class _BracketCellBuilder(object):
    """收集端焊三角架子元素，全部成功后一次性写入一个普通单元。"""

    def __init__(self, dgn_model, cell_name=None):
        self.dgn_model = dgn_model
        self.cell_name = cell_name or CELL_NAME
        self.cell = EditElementHandle()
        self.child_count = 0
        NormalCellHeaderHandler.CreateOrphanCellElement(
            self.cell, self.cell_name, dgn_model.Is3d(), dgn_model)

    def add(self, child):
        if child is None:
            raise RuntimeError('三角架子元素创建失败。')
        status = NormalCellHeaderHandler.AddChildElement(self.cell, child)
        if not _succeeded(status):
            raise RuntimeError('无法将三角架子元素加入普通单元。')
        self.child_count += 1

    def build(self):
        if not _succeeded(NormalCellHeaderHandler.AddChildComplete(self.cell)):
            raise RuntimeError('无法完成端焊三角架单元。')
        return self.child_count

    def commit(self):
        if not _succeeded(self.cell.AddToModel()):
            raise RuntimeError('无法将端焊三角架单元写入活动模型。')
        return self.cell


def _delete_preview(handle):
    if handle is None:
        return False
    try:
        if not handle.IsValid():
            return False
        handle.DeleteFromModel()
        return True
    except Exception:
        return False


def _element_list(value, label):
    """把 ``_build_beam`` / ``_build_brace`` 的返回值统一成元素列表。

    这两个函数按契约返回**列表**（D19 两片 → 2 个元素）。万一某个出口漏了包装、
    返回了单个元素，``for piece in 元素句柄`` 会去遍历 Bentley 元素句柄的
    linkage，抛出很难看懂的
    ``Unable to convert function return value … LinkageHeader``；
    这里先拦一道，给出能直接定位的提示。
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    raise RuntimeError('%s 建模函数返回了 %s，应为元素列表（内部错误：'
                       '某个出口忘了包成列表）。'
                       % (label, type(value).__name__))


# ---------------------------------------------------------------------------
# 构建整组
# ---------------------------------------------------------------------------


def _build_bracket_cell(line, l1_mm, variant_key, rack_type, rack_number=None,
                        reverse=False, add_plate=False,
                        plate_subtype=DEFAULT_PLATE_SUBTYPE,
                        plate_offset_mm=0.0, kind=DEFAULT_KIND):
    """按所选直线 + L1 构建整组单元但**不写入模型**，返回 (builder, 统计字典)。"""
    resolved = resolve_geometry(line, l1_mm, variant_key, rack_type, reverse,
                                add_plate, plate_subtype, plate_offset_mm,
                                kind)
    # 反向时用翻转后的直线建立局部坐标系（起点＝焊接端面）。
    oriented = resolved['line']
    plate = resolved['plate']

    dgn_model = ISessionMgr.GetActiveDgnModel()
    if not dgn_model.Is3d():
        raise RuntimeError('请先激活一个三维 DGN 模型。')

    to_world, to_world_vector = geom._make_frame(oriented['start_mm'],
                                                 oriented['heading_deg'])
    builder = _BracketCellBuilder(dgn_model,
                                  kind_config(resolved['kind'])['cell_name'])
    try:
        braces = _element_list(
            _build_brace(dgn_model, to_world, to_world_vector, resolved), '斜撑')
        if not braces:
            raise RuntimeError('斜撑实体创建失败。')
        for piece in braces:
            builder.add(piece)

        beams = _element_list(
            _build_beam(dgn_model, to_world, to_world_vector, resolved), '横担')
        if not beams:
            raise RuntimeError('横担实体创建失败。')
        for piece in beams:
            builder.add(piece)

        # G12 混凝土锚固：构件C —— 横担 2 根 + 斜撑 2 根膨胀锚栓（沿 -Y 埋入）。
        anchor_count = 0
        if resolved['kind'] == 'G12':
            anchor_count = _build_anchor_bolts(builder, dgn_model, to_world,
                                               resolved)
            if anchor_count != len(resolved.get('anchors') or []):
                raise RuntimeError('构件C 膨胀锚栓创建失败。')

        # D19：构件C —— 端部连接（加固）钢板，把两片槽钢横担连成整体。
        connector_count = 0
        if resolved['kind'] == 'D19':
            for _index in range(int(resolved.get('connector_count') or 1)):
                connector = _build_double_channel_connector(dgn_model, to_world,
                                                            resolved)
                if connector is None:
                    raise RuntimeError('构件C（端部连接板）创建失败。')
                builder.add(connector)
                connector_count += 1
            _log('D19: 两片槽钢 S=%.1f，构件C %s ×%d'
                 % (float(resolved.get('web_gap') or 0.0),
                    '×'.join('%.0f' % float(v) for v in resolved['connector']),
                    connector_count))

        # 混凝土上生根：横担、斜撑端面各一块 G2 混凝土锚板 + 4 根膨胀锚栓。
        # 端板背面在 x = plate_offset（默认 0 = 所选直线起点 = 混凝土表面），
        # 板身沿 +X 伸向空气侧（x ∈ [offset, offset+T]），**不会埋进混凝土**；
        # 横担 / 斜撑根部自板正面起，锚栓埋入端朝向 -X（混凝土一侧）。
        if plate is not None:
            face_offset = float(resolved.get('brace_face_offset') or 0.0)
            beam_height = resolved['beam_height']
            wall_cut = resolved['beam_start']
            plate_offset = resolved['plate_offset']
            p3 = resolved['points']['P3']
            # 端板中心落在斜撑根部切面上的轴线处（D5 角钢不对称，需扣掉偏心）。
            if resolved['brace_down']:
                brace_plate_z = p3[2] + wall_cut - face_offset
            else:
                brace_plate_z = p3[2] - wall_cut + face_offset
            geom._add_end_plate_at(builder, plate, oriented,
                                   (plate_offset, 0.0, -beam_height / 2.0),
                                   dgn_model, to_world)
            geom._add_end_plate_at(builder, plate, oriented,
                                   (plate_offset, 0.0, brace_plate_z),
                                   dgn_model, to_world)

        builder.build()
    finally:
        # 兜底：任何一步失败，辅助线也不能留在模型里。
        _purge_paths()

    if resolved['kind'] in CHANNEL_KINDS:
        bom_items = [
            {'code': 'ChannelBeam', 'name': COMPONENT_A_NAME,
             'specification': resolved['h_beam_specification'],
             'length': resolved['beam_length']},
            {'code': 'ChannelBrace', 'name': COMPONENT_B_NAME,
             'specification': '%s（45°）' % resolved['angle_specification'],
             'length': resolved['brace_length']},
        ]
        # D19：横担 / 斜撑各两片（构件A、构件B 数量 ×2），另加构件C 一项。
        if resolved['kind'] in DOUBLE_CHANNEL_KINDS:
            for item in bom_items:
                item['quantity'] = 2
                item['unit'] = '件'
            connector = resolved['connector']
            bom_items.append({
                'code': 'D19ConnectorPlate', 'name': COMPONENT_C_NAME,
                'specification': '%.0f×%.0f×%.0f 钢板（S=%.0f）'
                                 % (connector[0], connector[1], connector[2],
                                    float(resolved.get('web_gap') or 0.0)),
                'length': connector[2],
                'quantity': connector_count or int(
                    resolved.get('connector_count') or 1),
                'unit': '件'})
    else:
        bom_items = [
            {'code': 'HBeam', 'name': COMPONENT_A_NAME,
             'specification': resolved['h_beam_specification'],
             'length': resolved['beam_length']},
            {'code': 'AngleBrace', 'name': COMPONENT_B_NAME,
             'specification': '%s（45°）' % resolved['angle_specification'],
             'length': resolved['brace_length']},
        ]
    # G12：构件C —— 4 根膨胀锚栓（横担 2 + 斜撑 2），单列一项。
    if resolved['kind'] == 'G12':
        variant = G12_VARIANTS[variant_key]
        bolt_table = anchor.ANCHOR_TABLE[variant['bolt_subtype']]
        bom_items.append({
            'code': 'G12AnchorBolt', 'name': G12_ANCHOR_NAME,
            'specification': '%s（横担 2 + 斜撑 2，S=%.0f，C=%.0f）'
                             % (variant['bolt_spec'], variant['s'],
                                variant['c']),
            'length': float(bolt_table['length']),
            'quantity': 4, 'unit': '件'})
    # 端板 / 锚栓单独列项（统计时与支架本体分开汇总）。
    if plate is not None:
        plate_spec = '%.0f×%.0f×%.0f（S=%.0f，4-φ%.0f）' % (
            plate['plate_side'], plate['plate_side'], plate['plate_t'],
            plate['spacing'], plate['hole_dia'])
        bolt_spec = 'M%.0f×%.0f' % (plate['bolt_dia'], plate['bolt_length'])
        bom_items.extend([
            {'code': 'G2EndPlate', 'name': COMPONENT_PLATE_NAME,
             'specification': plate_spec, 'length': plate['plate_t'],
             'quantity': 1, 'unit': '件'},
            {'code': 'G2BraceEndPlate', 'name': COMPONENT_BRACE_PLATE_NAME,
             'specification': plate_spec, 'length': plate['plate_t'],
             'quantity': 1, 'unit': '件'},
            {'code': 'G2AnchorBolt', 'name': COMPONENT_BOLT_NAME,
             'specification': bolt_spec, 'length': plate['bolt_length'],
             'quantity': 4, 'unit': '件'},
            {'code': 'G2BraceAnchorBolt',
             'name': COMPONENT_BRACE_BOLT_NAME,
             'specification': bolt_spec, 'length': plate['bolt_length'],
             'quantity': 4, 'unit': '件'},
        ])

    result = {
        'kind': resolved['kind'],
        'variant': variant_key,
        'rack_type': resolved['rack_type'],
        'brace_down': resolved['brace_down'],
        'reverse': resolved['reverse'],
        'add_plate': resolved['add_plate'],
        'plate': dict(plate) if plate else None,
        'plate_t': resolved['plate_t'],
        'plate_offset': resolved['plate_offset'],
        'beam_start': resolved['beam_start'],
        'beam_length': resolved['beam_length'],
        'child_count': builder.child_count,
        'line_length': resolved['L2'],
        'l1': resolved['L1'],
        'end_overhang': resolved['end_overhang'],
        'brace_length': resolved['brace_length'],
        'allowable_load': resolved['allowable_load'],
        'anchor_count': anchor_count,
        'bolt_note': describe_bolt_line(resolved['kind'], variant_key),
        # D19：构件C（端部连接板）与两片间距 S。
        'connector': resolved.get('connector'),
        'connector_count': connector_count,
        'web_gap': resolved.get('web_gap'),
        'points': resolved['points'],
        'heading_deg': oriented['heading_deg'],
        'pipe_rack_number': rack_number or '',
        'h_beam_specification': resolved['h_beam_specification'],
        'angle_specification': resolved['angle_specification'],
        'bom_items': bom_items,
    }
    _log('bracket by path: kind=%s, variant=%s, type=%d, L2=%.1f, L1=%.1f, '
         'E=%.1f, beam=%.1f, brace=%.1f, reverse=%s, plate=%s, bolts=%d, '
         'heading=%.2f, children=%d, rack=%s'
         % (result['kind'], variant_key, result['rack_type'],
            result['line_length'], result['l1'], result['end_overhang'],
            result['beam_length'], result['brace_length'], result['reverse'],
            (plate_subtype if plate else '-'), result['anchor_count'],
            result['heading_deg'], result['child_count'],
            result['pipe_rack_number'] or '-'))
    return builder, result


def _attach_result_items(cell, result):
    """把整组三角架写入共享支吊架库（整组记录 + 各构件记录）。

    支架本体（横担 / 斜撑）与端板（G2 锚板 / 膨胀锚栓）、D19 构件C 都是
    **分开的构件记录**，统计与导出时按构件名分别汇总。
    """
    assembly_spec = '%s + %s' % (result.get('h_beam_specification', ''),
                                 result.get('angle_specification', ''))
    if result.get('kind') in DOUBLE_CHANNEL_KINDS:
        assembly_spec = '%s×2 + %s×2' % (result.get('h_beam_specification', ''),
                                         result.get('angle_specification', ''))
        connector = result.get('connector')
        if connector:
            assembly_spec += ' + %s（S=%.0f）' % (
                COMPONENT_C_NAME, float(result.get('web_gap') or 0.0))
    plate = result.get('plate')
    if plate:
        assembly_spec += ' + G2 端板×2（%s）' % plate.get('subtype', '')
    if result.get('kind') == 'G12':
        assembly_spec += ' + %s×4' % G12_ANCHOR_NAME
    config = kind_config(result.get('kind'))
    return psb.attach_components(
        cell,
        support_type=config['support_type'],
        support_code=config['support_code'],
        assembly_tag=result.get('pipe_rack_number', ''),
        assembly_spec=assembly_spec,
        components=result.get('bom_items', ()),
    )


def replace_end_welded_bracket(line, l1_mm, previous_handle,
                               variant_key=None, rack_type=1,
                               rack_number=None, reverse=False,
                               add_plate=False,
                               plate_subtype=DEFAULT_PLATE_SUBTYPE,
                               plate_offset_mm=0.0, kind=DEFAULT_KIND,
                               attach=True):
    """重建整组：先建新的一版并写入，成功后再删除上一版预览。

    ``attach=False`` 时**只出几何、不写清单库**（面板在预览阶段用，
    写库推迟到点【确定】，见 ``ATTACH_ON_CONFIRM``）。
    """
    if not variant_key:
        variant_key = default_variant_of(kind)
    builder, result = _build_bracket_cell(line, l1_mm, variant_key, rack_type,
                                          rack_number, reverse, add_plate,
                                          plate_subtype, plate_offset_mm, kind)
    new_handle = builder.commit()
    if attach and ITEM_TYPE_ATTACH:
        _attach_result_items(new_handle, result)
    deleted = _delete_preview(previous_handle)
    return new_handle, result, deleted


def export_bom_json(output_path=None):
    """导出**全部**管道支吊架的统一清单（共享库），返回文件路径。"""
    if output_path is None:
        output_path = os.path.join(HERE, '模块', '输出', '三角架_bom.json')
    return psb.export_combined_bom(output_path)


# ---------------------------------------------------------------------------
# 面板
# ---------------------------------------------------------------------------


class _BracketDialog(GlassDialog):
    """子项 / 类型 / L1 选择，预览 / 确定 / 取消面板。"""

    STATE_KEY = 'D5D6G12D19TriangleBracket'
    POLL_MS = 120

    def __init__(self):
        GlassDialog.__init__(self, title=UI_TITLE)
        self.line = None
        self.line_handle = None
        self.preview_handle = None
        self.preview_result = None
        self.confirmed = False
        # 原生回调只写 Python 状态；所有 Tk 刷新由常驻定时器 _poll_ui 完成。
        self._poll_job = None
        self._regen_deadline = None
        self._pending_result = None
        self._pending_message = None
        self._pending_is_error = False
        # 重建缓存：参数没变（含悬停反复触发）就不重复做重型建模。
        self._built_key = None
        # 当前预览是否已经写进共享支吊架库（预览阶段写库时用，避免【确定】重写）。
        self._preview_attached = False
        # 悬停预览：原生回调只写这个变量，界面刷新交给 _flush_ui。
        self._hover_line = None
        # 使用说明弹窗。
        self._help_window = None
        self._shutdown_requested = False
        self._cancel_requested = False

        self._kind = tk.StringVar()
        self._variant = tk.StringVar()
        self._rack_type = tk.StringVar()
        self._l1 = tk.StringVar(value='%.0f' % DEFAULT_L1)
        self._rack_name = tk.StringVar(value='D5')
        self._keep_line = tk.BooleanVar(value=True)
        self._reverse = tk.BooleanVar(value=False)
        self._add_plate = tk.BooleanVar(value=False)
        self._plate_subtype = tk.StringVar()
        self._plate_offset = tk.StringVar(value='0')
        self._beam = tk.StringVar(value='—')
        self._angle = tk.StringVar(value='—')
        self._length = tk.StringVar(value='—')
        self._overhang = tk.StringVar(value='—')
        self._brace = tk.StringVar(value='—')
        self._points = tk.StringVar(value='—')
        self._rack_number = tk.StringVar(value='—')
        self._plate_dim = tk.StringVar(value='—')
        self._plate_bolt = tk.StringVar(value='—')
        self._status = tk.StringVar()
        self._load_note = tk.StringVar(value='')
        self._l2_limit = tk.StringVar(value='≤%.0f' % kind_max_length(
            DEFAULT_KIND))
        self._variant_by_label = {}
        self._kind_by_label = {}
        self._type_by_label = {}
        self._plate_by_label = {}

        self._build()
        self.restore_state()
        self.restore_position()
        self.protocol('WM_DELETE_WINDOW', self.cancel_tool)
        self._start_poll()
        self.set_status('① 先在顶部选【架型】（D5 端焊 / D6 侧焊 / G12 锚固 / '
                        'D19 双槽钢），② 在模型中点选一条水平直线段，'
                        '③ 再输入 L1；改参数会自动重建预览。')
        try:
            self.minsize(540, 560)
        except tk.TclError:
            pass
        _log('panel built rev=%s file=%s'
             % (UI_REVISION, os.path.abspath(__file__)))

    # -- 构建 --------------------------------------------------------------

    def _build(self):
        # 副标题省略（下面第一行已说明用法），以压低面板高度。
        form = self.build_shell(UI_TITLE, '')
        form.columnconfigure(1, weight=1)

        # -- 顶部：架型选择 + 一行提示 + 使用说明弹窗 ------------------------
        top = tk.Frame(form, bg=CARD)
        top.grid(row=0, column=0, columnspan=2, sticky='ew')
        ttk.Label(top, text='架型', style='GlassMuted.TLabel').pack(side='left')
        for key, label in BRACKET_KINDS:
            self._kind_by_label[label] = key
        self._kind_combo = ttk.Combobox(
            top, textvariable=self._kind, state='readonly', width=14,
            style='Glass.TCombobox', values=[label for _k, label in
                                             BRACKET_KINDS])
        self._kind_combo.pack(side='left', padx=(6, 0))
        self._kind_combo.bind('<<ComboboxSelected>>', self.on_kind_changed)
        tk.Label(top, text='① 点选直线　② 输入 L1　③ 确定', bg=CARD, fg=MUTED,
                 font=UI_FONT_SMALL).pack(side='left', padx=(10, 0))
        help_link = tk.Label(top, text='使用说明 ▸', bg=CARD, fg=ACCENT,
                             font=UI_FONT_SMALL, cursor='hand2')
        help_link.pack(side='right')
        help_link.bind('<Button-1>', lambda event: self.show_help())

        # -- 构件规格：选择框在上，构件规格双列并排 ---------------------------
        ttk.Label(form, text='构件规格', style='Section.TLabel').grid(
            row=1, column=0, columnspan=2, sticky='w', pady=(8, 2))

        spec_top = tk.Frame(form, bg=CARD)
        spec_top.grid(row=2, column=0, columnspan=2, sticky='ew')
        spec_top.columnconfigure(1, weight=1)
        ttk.Label(spec_top, text='子项', style='GlassMuted.TLabel').grid(
            row=0, column=0, sticky='w', pady=2)
        self._variant_combo = ttk.Combobox(
            spec_top, textvariable=self._variant, state='readonly', width=34,
            style='Glass.TCombobox', values=())
        self._variant_combo.grid(row=0, column=1, sticky='ew', padx=(8, 0),
                                 pady=2)
        self._variant_combo.bind('<<ComboboxSelected>>',
                                 self.on_options_changed)
        # 子项列表随"架型"切换重建（D5 为 H 型钢+角钢 / 槽钢架型见表 2）。
        self._populate_variants()

        ttk.Label(spec_top, text='类型', style='GlassMuted.TLabel').grid(
            row=1, column=0, sticky='w', pady=2)
        type_labels = []
        for key, label in TYPE_OPTIONS:
            type_labels.append(label)
            self._type_by_label[label] = key
        self._type_combo = ttk.Combobox(
            spec_top, textvariable=self._rack_type, state='readonly', width=34,
            style='Glass.TCombobox', values=type_labels)
        self._type_combo.grid(row=1, column=1, sticky='ew', padx=(8, 0),
                              pady=2)
        self._type_combo.bind('<<ComboboxSelected>>', self.on_options_changed)

        members = tk.Frame(form, bg=CARD)
        members.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(4, 0))
        members.columnconfigure(0, weight=1, uniform='member')
        members.columnconfigure(1, weight=1, uniform='member')
        member_a = tk.Frame(members, bg=CARD)
        member_a.grid(row=0, column=0, sticky='w')
        ttk.Label(member_a, text='构件A（横担）',
                  style='GlassMuted.TLabel').pack(anchor='w')
        tk.Label(member_a, textvariable=self._beam, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(anchor='w')
        member_b = tk.Frame(members, bg=CARD)
        member_b.grid(row=0, column=1, sticky='w')
        ttk.Label(member_b, text='构件B（斜撑）',
                  style='GlassMuted.TLabel').pack(anchor='w')
        tk.Label(member_b, textvariable=self._angle, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(anchor='w')
        # 允许荷载（表 1，仅槽钢架型有；D5 时用 grid_remove 收起，不占高度）。
        self._load_label = tk.Label(
            members, textvariable=self._load_note, bg=CARD, fg=MUTED,
            font=UI_FONT_SMALL, anchor='w', justify='left', wraplength=460)
        self._load_label.grid(row=1, column=0, columnspan=2, sticky='w',
                              pady=(4, 0))
        self._load_label.grid_remove()

        ttk.Separator(form, orient='horizontal').grid(
            row=4, column=0, columnspan=2, sticky='ew', pady=4)

        # -- 尺寸参数：双列紧凑排版（不再单独占一行标题）----------------------
        dims = tk.Frame(form, bg=CARD)
        dims.grid(row=6, column=0, columnspan=2, sticky='ew')
        dims.columnconfigure(0, weight=1, uniform='dim')
        dims.columnconfigure(1, weight=1, uniform='dim')

        l1_cell = tk.Frame(dims, bg=CARD)
        l1_cell.grid(row=0, column=0, sticky='w')
        ttk.Label(l1_cell, text='L1', style='GlassMuted.TLabel').pack(
            side='left')
        self._l1_entry = self._entry(l1_cell, self._l1, 7)
        tk.Label(l1_cell, text='mm', bg=CARD, fg=MUTED,
                 font=UI_FONT_SMALL).pack(side='left', padx=(6, 0))

        l2_cell = tk.Frame(dims, bg=CARD)
        l2_cell.grid(row=0, column=1, sticky='w')
        ttk.Label(l2_cell, text='直线长 L2', style='GlassMuted.TLabel').pack(
            side='left')
        self._length_label = tk.Label(l2_cell, textvariable=self._length,
                                     bg=CARD, fg=INK, font=UI_FONT_BOLD)
        self._length_label.pack(side='left', padx=(6, 0))
        tk.Label(l2_cell, textvariable=self._l2_limit, bg=CARD, fg=MUTED,
                 font=UI_FONT_SMALL).pack(side='left', padx=(4, 0))

        e_cell = tk.Frame(dims, bg=CARD)
        e_cell.grid(row=1, column=0, sticky='w', pady=(4, 0))
        ttk.Label(e_cell, text='端部余量 E', style='GlassMuted.TLabel').pack(
            side='left')
        tk.Label(e_cell, textvariable=self._overhang, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left', padx=(6, 0))
        tk.Label(e_cell, text='≥%.0f' % MIN_END_OVERHANG, bg=CARD, fg=MUTED,
                 font=UI_FONT_SMALL).pack(side='left', padx=(4, 0))

        brace_cell = tk.Frame(dims, bg=CARD)
        brace_cell.grid(row=1, column=1, sticky='w', pady=(4, 0))
        ttk.Label(brace_cell, text='斜撑轴长',
                  style='GlassMuted.TLabel').pack(side='left')
        tk.Label(brace_cell, textvariable=self._brace, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left', padx=(6, 0))

        points_cell = tk.Frame(dims, bg=CARD)
        points_cell.grid(row=2, column=0, columnspan=2, sticky='ew',
                         pady=(4, 0))
        ttk.Label(points_cell, text='辅助点', style='GlassMuted.TLabel').pack(
            side='left')
        tk.Label(points_cell, textvariable=self._points, bg=CARD, fg=MUTED,
                 font=UI_FONT_SMALL, anchor='w', justify='left',
                 wraplength=400).pack(side='left', padx=(6, 0))

        ttk.Separator(form, orient='horizontal').grid(
            row=7, column=0, columnspan=2, sticky='ew', pady=4)

        # -- 管架编号：名称与编号同排（省一行）--------------------------------
        ident = tk.Frame(form, bg=CARD)
        ident.grid(row=15, column=0, columnspan=2, sticky='ew', pady=2)
        ident.columnconfigure(0, weight=1, uniform='ident')
        ident.columnconfigure(1, weight=1, uniform='ident')
        name_cell = tk.Frame(ident, bg=CARD)
        name_cell.grid(row=0, column=0, sticky='w')
        ttk.Label(name_cell, text='名称', style='GlassMuted.TLabel').pack(
            side='left')
        self._name_entry = self._entry(name_cell, self._rack_name, 10)
        number_cell = tk.Frame(ident, bg=CARD)
        number_cell.grid(row=0, column=1, sticky='w')
        ttk.Label(number_cell, text='编号',
                  style='GlassMuted.TLabel').pack(side='left')
        tk.Label(number_cell, textvariable=self._rack_number, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left', padx=(6, 0))

        ttk.Separator(form, orient='horizontal').grid(
            row=17, column=0, columnspan=2, sticky='ew', pady=4)

        ttk.Label(form, text='生根方式', style='Section.TLabel').grid(
            row=18, column=0, columnspan=2, sticky='w', pady=(0, 2))
        plate_head = tk.Frame(form, bg=CARD)
        plate_head.grid(row=19, column=0, columnspan=2, sticky='w')
        self._plate_check = tk.Checkbutton(
            plate_head,
            text='混凝土上生根：端面加 G2 混凝土锚板（板背面贴混凝土面、板身在外侧）',
            variable=self._add_plate, command=self.on_plate_changed,
            bg=CARD, fg=INK, activebackground=CARD, selectcolor=CARD,
            font=UI_FONT_SMALL, highlightthickness=0, bd=0)
        self._plate_check.pack(anchor='w')

        ttk.Label(form, text='G2 子项', style='GlassMuted.TLabel').grid(
            row=20, column=0, sticky='w', pady=3)
        plate_row = tk.Frame(form, bg=CARD)
        plate_row.grid(row=20, column=1, sticky='ew', padx=(10, 0), pady=3)
        plate_row.columnconfigure(0, weight=1)
        plate_labels = []
        for key in sorted(anchor.ANCHOR_TABLE):
            label = geom.plate_subtype_label(key)
            plate_labels.append(label)
            self._plate_by_label[label] = key
        self._plate_combo = ttk.Combobox(
            plate_row, textvariable=self._plate_subtype, state='disabled',
            width=30, style='Glass.TCombobox', values=plate_labels)
        self._plate_combo.grid(row=0, column=0, sticky='ew')
        self._plate_combo.bind('<<ComboboxSelected>>', self.on_plate_changed)
        offset_cell = tk.Frame(plate_row, bg=CARD)
        offset_cell.grid(row=0, column=1, sticky='e', padx=(10, 0))
        tk.Label(offset_cell, text='外移', bg=CARD, fg=MUTED,
                 font=UI_FONT_SMALL).pack(side='left')
        self._plate_offset_entry = self._entry(offset_cell, self._plate_offset, 6)
        tk.Label(offset_cell, text='mm', bg=CARD, fg=MUTED,
                 font=UI_FONT_SMALL).pack(side='left', padx=(4, 0))

        ttk.Label(form, text='端板 / 锚栓', style='GlassMuted.TLabel').grid(
            row=21, column=0, sticky='w', pady=3)
        plate_info = tk.Frame(form, bg=CARD)
        plate_info.grid(row=21, column=1, sticky='w', padx=(10, 0), pady=3)
        tk.Label(plate_info, textvariable=self._plate_dim, bg=CARD, fg=INK,
                 font=UI_FONT_BOLD).pack(side='left')
        tk.Label(plate_info, textvariable=self._plate_bolt, bg=CARD, fg=MUTED,
                 font=UI_FONT_SMALL, justify='left', anchor='w',
                 wraplength=250).pack(side='left', padx=(8, 0))

        ttk.Separator(form, orient='horizontal').grid(
            row=22, column=0, columnspan=2, sticky='ew', pady=4)

        checks = tk.Frame(form, bg=CARD)
        checks.grid(row=23, column=0, columnspan=2, sticky='w')
        tk.Checkbutton(
            checks, text='创建后保留所选辅助线（用户直线）',
            variable=self._keep_line, bg=CARD, fg=INK, activebackground=CARD,
            selectcolor=CARD, font=UI_FONT_SMALL, highlightthickness=0,
            bd=0).pack(side='left')
        # 反向：直线画反了（起点落在横担末端）时交换两端，整组翻到正确一侧。
        self._reverse_check = tk.Checkbutton(
            checks, text='反向（起点取直线另一端）',
            variable=self._reverse, command=self.on_options_changed,
            bg=CARD, fg=INK, activebackground=CARD, selectcolor=CARD,
            font=UI_FONT_SMALL, highlightthickness=0, bd=0)
        self._reverse_check.pack(side='left', padx=(12, 0))

        self.make_status_chip(form, self._status, wraplength=470).grid(
            row=25, column=0, columnspan=2, sticky='ew', pady=(6, 0))

        buttons = tk.Frame(form, bg=CARD)
        buttons.grid(row=26, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        self.confirm_button = RoundButton(
            buttons, '确定', self.confirm_tool, primary=True, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self.cancel_button = RoundButton(
            buttons, '取消', self.cancel_tool, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self.export_button = RoundButton(
            buttons, '导出 JSON 清单', self.export_bom, bg=CARD,
            font=UI_FONT, font_bold=UI_FONT_BOLD)
        self.export_button.pack(side='left')
        self.confirm_button.pack(side='right')
        self.cancel_button.pack(side='right', padx=(0, 8))

        self._l1.trace_add('write', self.on_text_changed)
        self._rack_name.trace_add('write', self.on_text_changed)
        self._plate_offset.trace_add('write', self.on_text_changed)

    def show_help(self):
        """使用说明弹窗（只读文本），避免在主面板上堆一大段文字。"""
        window = self._help_window
        if window is not None:
            try:
                if window.winfo_exists():
                    window.lift()
                    window.focus_set()
                    return
            except tk.TclError:
                pass

        window = tk.Toplevel(self)
        self._help_window = window
        window.title('%s · 使用说明' % UI_TITLE)
        window.configure(bg=CARD)
        try:
            window.transient(self)
            window.attributes('-topmost', True)
        except tk.TclError:
            pass

        body = tk.Frame(window, bg=CARD)
        body.pack(fill='both', expand=True, padx=14, pady=12)
        text = tk.Text(
            body, width=62, height=22, wrap='word', font=UI_FONT_SMALL,
            bg=CARD_SOFT, fg=INK, relief='flat', highlightthickness=1,
            highlightbackground=BORDER, padx=10, pady=8, cursor='arrow',
            takefocus=0)
        text.pack(fill='both', expand=True)
        text.insert('1.0', HELP_TEXT)
        text.configure(state='disabled')

        buttons = tk.Frame(window, bg=CARD)
        buttons.pack(fill='x', padx=14, pady=(0, 12))
        close = RoundButton(buttons, '关闭', window.destroy, primary=True,
                            bg=CARD, font=UI_FONT, font_bold=UI_FONT_BOLD)
        close.pack(side='right')

        window.update_idletasks()
        try:
            window.geometry('+%d+%d' % (self.winfo_rootx() + 40,
                                        self.winfo_rooty() + 50))
        except tk.TclError:
            pass

    # -- 架型 / 子项 --------------------------------------------------------

    def current_kind(self):
        return self._kind_by_label.get(self._kind.get(), DEFAULT_KIND)

    def _populate_variants(self, preferred=None):
        """按当前架型重建"子项"下拉内容；尽量保留原来的子项。"""
        kind = self.current_kind()
        if preferred is None:
            preferred = self._variant_by_label.get(self._variant.get())
        labels = []
        self._variant_by_label = {}
        for key in variant_keys_of(kind):
            label = variant_label_of(kind, key)
            labels.append(label)
            self._variant_by_label[label] = key
        try:
            self._variant_combo.configure(values=labels)
        except tk.TclError:
            return
        fallback = None
        selected = None
        # 只有该架型自己表里的子项（或 D5 的 VARIANTS）才保留原选择。
        valid = set(CHANNEL_VARIANTS.get(kind, ())) | set(geom.VARIANTS)
        keep = preferred if preferred in valid else None
        for label, key in self._variant_by_label.items():
            if fallback is None:
                fallback = label
            if key == default_variant_of(kind):
                fallback = label
            if keep is not None and key == keep:
                selected = label
        self._variant.set(selected or fallback)

    def _sync_default_name(self, kind):
        """名称还带着另一个架型的默认前缀时，跟着换（用户自由命名的不动）。"""
        name = (self._rack_name.get() or '').strip()
        new_default = kind_default_name(kind)
        for other in KIND_KEYS:
            if other == kind:
                continue
            old = kind_default_name(other)
            if name == old or name.startswith(old + '-'):
                name = new_default + name[len(old):]
                break
        if not name:
            name = new_default
        self._rack_name.set(name)

    def on_kind_changed(self, event=None):
        """切换架型：换子项表、名称默认值、L2 上限与允许荷载显示。

        D6 / G12 / D19 都没有"混凝土上生根（G2 端板）"，切过去时把勾选清掉
        （切回 D5 需重新勾选）。
        """
        kind = self.current_kind()
        if kind in CHANNEL_KINDS and self._add_plate.get():
            self._add_plate.set(False)
        self._sync_default_name(kind)
        self._populate_variants()
        self.refresh_spec()
        self._schedule_regeneration(REGENERATE_DELAY_MS)
        _log('kind changed: %s' % kind)

    def _entry(self, parent, variable, width):
        entry = tk.Entry(
            parent, textvariable=variable, width=width, font=UI_FONT, fg=INK,
            bg=FIELD, relief='flat', highlightthickness=1,
            highlightbackground=BORDER, highlightcolor='#9FB4CC',
            insertbackground=INK, justify='center')
        entry.pack(side='left', ipady=3)
        # 获得焦点即全选：再次输入时整体替换已有数值。
        entry.bind('<FocusIn>',
                   lambda event, widget=entry: widget.select_range(0, 'end'))
        return entry

    # -- 记忆 --------------------------------------------------------------

    def restore_state(self):
        state = self.ui_state
        kind = state.get('kind')
        if kind in KIND_KEYS:
            for label, key in self._kind_by_label.items():
                if key == kind:
                    self._kind.set(label)
                    break
        if not self._kind.get():
            self._kind.set(KIND_LABELS[KIND_KEYS[0]])
        self._populate_variants(preferred=state.get('variant'))

        selected_type = None
        fallback_type = None
        for label, key in self._type_by_label.items():
            if fallback_type is None:
                fallback_type = label
            if key == state.get('rack_type'):
                selected_type = label
        self._rack_type.set(selected_type or fallback_type)

        value = state.get('l1')
        if isinstance(value, str) and value.strip():
            self._l1.set(value)
        name = state.get('rack_name')
        if isinstance(name, str) and name.strip():
            self._rack_name.set(name)
        self._sync_default_name(self.current_kind())
        if isinstance(state.get('keep_line'), bool):
            self._keep_line.set(state.get('keep_line'))
        if isinstance(state.get('reverse'), bool):
            self._reverse.set(state.get('reverse'))
        if isinstance(state.get('add_plate'), bool):
            self._add_plate.set(state.get('add_plate'))
        offset = state.get('plate_offset')
        if isinstance(offset, str) and offset.strip():
            self._plate_offset.set(offset)
        selected_plate = None
        fallback_plate = None
        for label, key in self._plate_by_label.items():
            if fallback_plate is None:
                fallback_plate = label
            if key == DEFAULT_PLATE_SUBTYPE:
                fallback_plate = label
            if key == state.get('plate_subtype'):
                selected_plate = label
        self._plate_subtype.set(selected_plate or fallback_plate)
        self.refresh_spec()

    def persist_state(self, state):
        try:
            state['kind'] = self.current_kind()
            state['variant'] = self.current_variant()
            state['rack_type'] = self.current_rack_type()
            state['l1'] = self._l1.get()
            state['rack_name'] = self._rack_name.get()
            state['keep_line'] = bool(self._keep_line.get())
            state['reverse'] = bool(self._reverse.get())
            state['add_plate'] = bool(self._add_plate.get())
            state['plate_subtype'] = self.current_plate_subtype()
            state['plate_offset'] = self._plate_offset.get()
        except tk.TclError:
            pass

    # -- 选项 --------------------------------------------------------------

    def current_variant(self):
        kind = self.current_kind()
        return self._variant_by_label.get(self._variant.get(),
                                          default_variant_of(kind))

    def current_rack_type(self):
        return self._type_by_label.get(self._rack_type.get(), 1)

    def current_reverse(self):
        return bool(self._reverse.get())

    def current_add_plate(self):
        """是否在端面加 G2 锚板；**D6 / G12 / D19 都不提供该工况**。"""
        if self.current_kind() in CHANNEL_KINDS:
            return False
        return bool(self._add_plate.get())

    def current_plate_subtype(self):
        return self._plate_by_label.get(self._plate_subtype.get(),
                                        DEFAULT_PLATE_SUBTYPE)

    def current_plate_offset(self):
        """端板背面相对所选直线起点的外移量（mm，≥0）。"""
        try:
            return float((self._plate_offset.get() or '').strip() or 0.0)
        except (TypeError, ValueError):
            raise ValueError('端板外移必须是数字（mm）。')

    def current_l1(self):
        try:
            return float((self._l1.get() or '').strip())
        except (TypeError, ValueError):
            raise ValueError('L1 必须是数字（mm）。')

    def current_number(self, line=None):
        line = line if line is not None else self.line
        if line is None:
            return ''
        try:
            l1 = self.current_l1()
        except ValueError:
            return ''
        return build_number(self._rack_name.get(), self.current_rack_type(),
                            self.current_variant(), l1, line['length_mm'])

    # -- 显示 --------------------------------------------------------------

    def set_status(self, message, is_error=False):
        self._pending_message = message
        self._pending_is_error = bool(is_error)

    def note_hover_error(self, message):
        self._pending_message = message
        self._pending_is_error = True

    def note_hover(self, line):
        """原生悬停回调**只能**写 Python 状态，绝不碰 Tk 控件。

        在 MicroStation 的原生回调（_OnPostLocate / _OnElementModify）里改
        StringVar、刷新界面，会让 Tcl 解释器状态错乱，随后 update() 里直接
        access violation（本插件的崩溃就是这么来的）。界面刷新一律交给
        _flush_ui（Tk 定时器）。
        """
        self._hover_line = line

    def _show_line_values(self, line):
        if line is None:
            self.refresh_line_labels()
            return
        l2 = float(line['length_mm'])
        self._set_length_text(l2)
        try:
            l1 = self.current_l1()
        except ValueError:
            self._overhang.set('—')
            self._brace.set('—')
            self._points.set('—')
            self._rack_number.set('—')
            return
        self._overhang.set('%.1f' % (l2 - l1 - self._toe_offset_for_variant()))
        self._brace.set('%.1f' % (l1 * math.sqrt(2.0)))
        points = compute_points(l2, l1, self._beam_height_for_variant(),
                                self.current_rack_type() == 1)
        prefix = '已反向｜' if self.current_reverse() else ''
        self._points.set(
            prefix + 'P0(0,0,0)　P2(%.0f,0,0)　P1(%.0f,0,%.0f)　P3(0,0,%.0f)'
            % (points['P2'][0], points['P1'][0], points['P1'][2],
               points['P3'][2]))
        number = self.current_number(line)
        self._rack_number.set(number if number else '（名称留空，不附加）')

    def _set_length_text(self, l2):
        """L2 读数：超过当前架型上限时标红并注明"不生成"。"""
        limit = kind_max_length(self.current_kind())
        over = False
        if l2 is None:
            self._length.set('—')
        else:
            over = float(l2) > limit + 1.0e-9
            self._length.set('%.1f%s' % (float(l2),
                                         '　← 超出上限，不生成' if over else ''))
        try:
            self._length_label.configure(fg='#C0392B' if over else INK)
        except Exception:
            pass

    def _beam_height_for_variant(self):
        beam, _brace, _a, _b = variant_specs(self.current_kind(),
                                             self.current_variant())
        return float(beam[0]) if beam else 0.0

    def _toe_offset_for_variant(self):
        """斜撑上端水平切面自交点向外的伸出量（D5 √2×肢宽 / 槽钢 hB×√2/4）。"""
        return toe_offset_of(self.current_kind(), self.current_variant())

    def refresh_spec(self):
        kind = self.current_kind()
        variant_key = self.current_variant()
        beam, brace, spec_a, spec_b = variant_specs(kind, variant_key)
        self._l2_limit.set('≤%.0f' % kind_max_length(kind))
        self._beam.set(spec_a)
        self._angle.set('%s（45°）' % spec_b)
        if kind in CHANNEL_KINDS:
            try:
                l1 = self.current_l1()
            except ValueError:
                l1 = None
            lines = []
            if l1 is not None:
                note = describe_load(kind, variant_key, l1)
                if note:
                    lines.append(note)
            bolt_line = describe_bolt_line(kind, variant_key)
            if bolt_line:
                lines.append(bolt_line)
            connector_line = describe_connector(kind, variant_key)
            if connector_line:
                lines.append(connector_line)
            text = '\n'.join(lines)
            self._load_note.set(text)
            if text:
                self._load_label.grid()
            else:
                self._load_label.grid_remove()
        else:
            self._load_note.set('')
            self._load_label.grid_remove()
        self._sync_plate_widgets()
        self.refresh_line_labels()

    def _sync_plate_widgets(self):
        """端板勾选框 / 子项下拉 / 外移输入 / 只读数值的联动与显示。

        D6 侧焊（腹板直接侧焊在既有钢结构上）、G12 混凝土锚固（用构件C 膨胀
        锚栓锚在既有混凝土上）与 D19 双槽钢（两片端面现场焊接 + 筋板）都没有
        "混凝土上生根（G2 端板）"这种工况，勾选框与子项、外移一律禁用。
        """
        applicable = self.current_kind() not in CHANNEL_KINDS
        enabled = applicable and bool(self._add_plate.get())
        try:
            self._plate_check.configure(
                state='normal' if applicable else 'disabled',
                text=('混凝土上生根：端面加 G2 混凝土锚板'
                      '（板背面贴混凝土面、板身在外侧）' if applicable else
                      '混凝土上生根不可用：本架型不设端板'))
            self._plate_combo.configure(
                state='readonly' if enabled else 'disabled')
            self._plate_offset_entry.configure(
                state='normal' if enabled else 'disabled')
        except tk.TclError:
            pass
        if not applicable:
            kind = self.current_kind()
            self._plate_dim.set('不适用（%s 不设端板）' % kind)
            if kind == 'D6':
                note = 'D6 侧焊：腹板外表面直接侧焊在既有钢结构上'
            elif kind == 'G12':
                note = 'G12：由构件C 膨胀锚栓直接锚在既有混凝土上'
            else:
                note = ('D19：两片槽钢端面现场焊接在既有钢结构上'
                        '（配筋板，见管架编号 D1）')
            self._plate_bolt.set(note)
            return
        beam_spec, _brace, _spec_a, _spec_b = variant_specs(
            self.current_kind(), self.current_variant())
        if not enabled:
            self._plate_dim.set('不创建（端面直接焊接）')
            self._plate_bolt.set('')
            return
        subtype = self.current_plate_subtype()
        try:
            resolved = geom._resolve_plate_options(subtype, 0.0, beam_spec)
        except ValueError as error:
            self._plate_dim.set('参数有误：%s' % error)
            self._plate_bolt.set('')
            return
        try:
            offset = self.current_plate_offset()
        except ValueError as error:
            self._plate_dim.set(str(error))
            self._plate_bolt.set('')
            return
        if offset < -1.0e-9:
            self._plate_dim.set('端板外移不能为负：板会被埋进混凝土')
            self._plate_bolt.set('')
            return
        plate_t = float(resolved['plate_t'])
        self._plate_dim.set(
            'G2-%s %.0f×%.0f×%.0f（S=%.0f）%s'
            % (subtype, resolved['plate_side'], resolved['plate_side'],
               plate_t, resolved['spacing'],
               ('　外移 %.0f' % offset) if offset > 1.0e-9 else ''))
        bolt_text = 'M%.0f×%.0f 锚栓 ×4/块（埋入混凝土）' % (
            resolved['bolt_dia'], resolved['bolt_length'])
        if self.line is not None:
            bolt_text += '；横担自 x=%.0f 起' % (offset + plate_t)
        self._plate_bolt.set(bolt_text)

    def refresh_line_labels(self):
        line = self.line
        if line is None:
            self._set_length_text(None)
            self._overhang.set('—')
            self._brace.set('—')
            self._points.set('—')
            self._rack_number.set('—')
            return
        l2 = float(line['length_mm'])
        self._set_length_text(l2)
        try:
            l1 = self.current_l1()
        except ValueError:
            self._overhang.set('—')
            self._brace.set('—')
            self._points.set('—')
            self._rack_number.set('—')
            return
        self._overhang.set('%.1f' % (l2 - l1 - self._toe_offset_for_variant()))
        try:
            resolved = resolve_geometry(line, l1, self.current_variant(),
                                        self.current_rack_type(),
                                        self.current_reverse(), False,
                                        DEFAULT_PLATE_SUBTYPE, 0.0,
                                        self.current_kind())
        except (ValueError, RuntimeError):
            self._brace.set('—')
            self._points.set('—')
            self._rack_number.set('—')
            return
        points = resolved['points']
        self._brace.set('%.1f' % resolved['brace_length'])
        prefix = '已反向｜' if resolved.get('reverse') else ''
        self._points.set(
            prefix + 'P0(0,0,0)　P2(%.0f,0,0)　P1(%.0f,0,%.0f)　P3(0,0,%.0f)'
            % (points['P2'][0], points['P1'][0], points['P1'][2],
               points['P3'][2]))
        number = self.current_number(line)
        self._rack_number.set(number if number else '（名称留空，不附加）')

    def set_result(self, result):
        number = result.get('pipe_rack_number') or '—'
        plate = result.get('plate')
        if plate:
            plate_note = ('G2-%s 端板×2%s ｜ ' % (
                plate['subtype'],
                ('（外移 %.0f）' % result.get('plate_offset', 0.0))
                if result.get('plate_offset', 0.0) > 1.0e-9 else ''))
        else:
            plate_note = '不加端板 ｜ '
        load = result.get('allowable_load')
        load_note = (' ｜ 允许垂直荷载 %.1f kN' % load) if load else ''
        if result.get('anchor_count'):
            load_note += ' ｜ 构件C 膨胀锚栓 ×%d' % result['anchor_count']
        self._pending_message = (
            '预览已更新%s：%s子项 %s ｜ 类型 %d ｜ 横担 %s ｜ L2=%.0f ｜ '
            'L1=%.0f ｜ E=%.0f ｜ 横担实体 %.0f ｜ %d 个子元素 ｜ 编号 %s%s'
            % ('（已反向）' if result.get('reverse') else '', plate_note,
               result['variant'], result['rack_type'],
               result['h_beam_specification'], result['line_length'],
               result['l1'], result['end_overhang'], result['beam_length'],
               result['child_count'], number, load_note))
        self._pending_is_error = False
        if ATTACH_ON_CONFIRM and not self._preview_attached:
            self._pending_message += ' ｜ 清单在【确定】时写入公共库'

    # -- UI 刷新：只允许在这个 Tk 定时器里碰控件 ---------------------------

    def _start_poll(self):
        try:
            self._poll_job = self.after(self.POLL_MS, self._poll_ui)
        except tk.TclError:
            self._poll_job = None

    def _poll_ui(self):
        self._poll_job = None
        try:
            if self._shutdown_requested:
                self._shutdown_requested = False
                self.shutdown()
                return
            if self._cancel_requested:
                self._cancel_requested = False
                self.cancel_tool()
                return
            if (self._regen_deadline is not None
                    and time.monotonic() >= self._regen_deadline):
                self._regen_deadline = None
                try:
                    self.regenerate()
                except Exception:
                    _log_exception('regenerate from timer failed')
            try:
                self._flush_ui()
            except Exception:
                _log_exception('flush ui failed')
            # 无论上一轮发生什么，都要把定时器接回去，否则面板会失去刷新。
            self._poll_job = self.after(self.POLL_MS, self._poll_ui)
        except tk.TclError:
            self._poll_job = None

    def _flush_ui(self):
        """所有界面刷新都在这里做（由 Tk 定时器调用）。"""
        try:
            if self._pending_result is not None:
                result = self._pending_result
                self._pending_result = None
                self.refresh_spec()
                self.set_result(result)
            if self._pending_message is not None:
                message = self._pending_message
                self._pending_message = None
                self._status.set(message)
            if self.line is None and self._hover_line is not None:
                self._show_line_values(self._hover_line)
        except tk.TclError:
            pass

    def request_cancel(self):
        self._cancel_requested = True

    def request_shutdown(self):
        self._shutdown_requested = True

    # -- 事件 --------------------------------------------------------------

    def on_options_changed(self, event=None):
        self.refresh_spec()
        self._schedule_regeneration(REGENERATE_DELAY_MS)

    def on_plate_changed(self, event=None):
        self.refresh_spec()
        self._schedule_regeneration(REGENERATE_DELAY_MS)

    def on_text_changed(self, *_args):
        self.refresh_spec()
        self._schedule_regeneration(TEXT_REGENERATE_DELAY_MS)

    def _schedule_regeneration(self, delay_ms):
        self._regen_deadline = None
        if self.line is None:
            return
        self._regen_deadline = time.monotonic() + delay_ms / 1000.0

    def _cancel_pending_regeneration(self):
        self._regen_deadline = None

    # -- 预览 --------------------------------------------------------------

    def regenerate(self, line=None, handle=None):
        """按当前直线与选项重建预览；只做 Bentley 建模，UI 刷新交给定时器。"""
        self._cancel_pending_regeneration()
        if line is not None:
            self.line = line
            self.line_handle = handle
        if self.line is None:
            return None

        try:
            l1 = self.current_l1()
            kind = self.current_kind()
            variant_key = self.current_variant()
            rack_type = self.current_rack_type()
            reverse = self.current_reverse()
            add_plate = self.current_add_plate()
            plate_subtype = self.current_plate_subtype()
            plate_offset = self.current_plate_offset()
            resolve_geometry(self.line, l1, variant_key, rack_type, reverse,
                             add_plate, plate_subtype, plate_offset, kind)
        except (ValueError, RuntimeError) as error:
            # 参数超限 / 不合法：**不生成**，并清掉上一版预览以免留在模型里误导，
            # 同时在面板和 MicroStation 提示区醒目提醒。
            message = '未生成预览：%s' % error
            self._discard_stale_preview()
            self._pending_message = message
            self._pending_is_error = True
            try:
                NotificationManager.OutputPrompt('%s：%s'
                                                 % (UI_TITLE, message))
            except Exception:
                _log_exception('OutputPrompt failed')
            _log('regenerate skipped: %s' % message)
            return None

        # 参数与所选直线都没变时直接跳过（连续输入 / 悬停都会走到这里），
        # 避免反复做扫掠 + 布尔剪切——这是稳定性的关键。
        start = self.line.get('start_mm') or (0.0, 0.0, 0.0)
        key = (kind, variant_key, rack_type, bool(reverse), round(l1, 3),
               bool(add_plate),
               (plate_subtype if add_plate else ''),
               (round(plate_offset, 3) if add_plate else 0.0),
               round(float(self.line['length_mm']), 3),
               round(float(self.line['heading_deg']), 6),
               tuple(round(float(c), 6) for c in start))
        if key == self._built_key and self.preview_handle is not None:
            return self.preview_result

        rack_number = self.current_number()
        # 预览阶段默认**不写清单库**（写库推迟到【确定】，见 ATTACH_ON_CONFIRM）；
        # 只有把开关关掉时才在预览里写，此时要记住"这一版已经写过了"，
        # 免得点【确定】时重复写一遍。
        attach_now = (not ATTACH_ON_CONFIRM) and ITEM_TYPE_ATTACH
        _log('regenerate: kind=%s variant=%s type=%s L1=%.1f reverse=%s '
             'plate=%s offset=%.1f rack=%s attach=%s'
             % (kind, variant_key, rack_type, l1, reverse,
                (plate_subtype if add_plate else '-'),
                (plate_offset if add_plate else 0.0), rack_number or '-',
                attach_now))
        try:
            new_handle, result, deleted = replace_end_welded_bracket(
                self.line, l1, self.preview_handle, variant_key, rack_type,
                rack_number, reverse, add_plate, plate_subtype, plate_offset,
                kind, attach_now)
        except Exception as error:
            message = '%s 生成失败：%s' % (UI_TITLE, error)
            _log_exception('preview failed')
            self._pending_message = message
            self._pending_is_error = True
            try:
                NotificationManager.OutputPrompt(message)
            except Exception:
                _log_exception('OutputPrompt failed')
            print(message)
            return None

        self.preview_handle = new_handle
        self.preview_result = result
        self._preview_attached = bool(attach_now)
        self._built_key = key
        self._pending_result = result
        try:
            NotificationManager.OutputPrompt(
                '%s 预览已更新：L1=%.0f，L2=%.0f。%s'
                % (UI_TITLE, result['l1'], result['line_length'],
                   ('允许垂直荷载 %.1f kN。' % result['allowable_load'])
                   if result.get('allowable_load') else ''))
        except Exception:
            pass
        _log('regenerate: done')
        return result

    def queue_pick(self, line, handle):
        """原生拾取回调只调用这里：记下所选直线，重建交给 _poll_ui。

        重型建模（扫掠 / 布尔剪切 / 写库）不要在原生回调里连续做，
        否则多次改参数后容易把 MicroStation 崩掉。
        """
        self.line = line
        self.line_handle = handle
        self._pending_message = None
        self._regen_deadline = time.monotonic() + REGENERATE_DELAY_MS / 1000.0

    def _discard_stale_preview(self):
        """参数超限 / 不合法时删掉上一版预览，避免旧模型留在模型里被误判为已生成。"""
        if self.preview_handle is None:
            self._built_key = None
            return False
        return self.discard_preview()

    def discard_preview(self):
        handle = self.preview_handle
        self.preview_handle = None
        self.preview_result = None
        self._preview_attached = False
        self._built_key = None
        return _delete_preview(handle)

    def delete_source_line(self):
        handle = self.line_handle
        if handle is None:
            return False
        try:
            if handle.IsValid():
                handle.DeleteFromModel()
                return True
        except Exception:
            _log_exception('delete source line failed')
        self.set_status('所选直线删除失败，请手动删除。', True)
        return False

    def export_bom(self):
        output_path = export_bom_json()
        if output_path is not None:
            self.set_status('清单已导出：%s' % output_path)

    # -- 收尾 --------------------------------------------------------------

    def confirm_tool(self):
        self._cancel_pending_regeneration()
        self.confirmed = True
        # 清单写库在【确定】这一刻做（预览阶段完全不碰 ItemType）：
        # 原生 EC 写入次数降一到两个数量级，也不会为取消掉的预览留下垃圾 ItemType。
        self.attach_result()
        if self.preview_handle is not None and not self._keep_line.get():
            self.delete_source_line()
        self.finish_tool()

    def attach_result(self):
        """把当前预览写进共享支吊架库（整组 + 各构件）；失败只记日志，不影响落图。

        这一步走的是 MicroStation 原生 EC 调用（``ApplyCustomItem``），是本插件
        已知的偶发卡死点，所以：先记一条含 ItemType 名字的日志（崩了也能从日志
        看出崩在哪一项），再逐项写；写失败不抛给调用方。
        """
        handle = self.preview_handle
        result = self.preview_result
        if handle is None or result is None:
            return 0
        if self._preview_attached:
            _log('attach skipped: preview already written')
            return 0
        if not ITEM_TYPE_ATTACH:
            _log('attach skipped (ITEM_TYPE_ATTACH=False): %s'
                 % (result.get('pipe_rack_number') or '-'))
            return 0
        try:
            if not handle.IsValid():
                _log('attach skipped: preview handle invalid')
                return 0
        except Exception:
            _log_exception('attach handle check failed')
            return 0
        config = kind_config(result.get('kind'))
        _log('attach on confirm: type=%s code=%s tag=%s beam=%s items=%s'
             % (config['support_type'], config['support_code'],
                result.get('pipe_rack_number') or '-',
                result.get('h_beam_specification') or '-',
                [str(item.get('code')) for item in
                 result.get('bom_items', ())]))
        try:
            count = _attach_result_items(handle, result)
        except Exception as error:
            _log_exception('attach on confirm failed')
            self._pending_message = ('清单写入失败（模型已生成，不受影响）：%s'
                                     % error)
            self._pending_is_error = True
            try:
                NotificationManager.OutputPrompt('%s：清单写入失败：%s'
                                                 % (UI_TITLE, error))
            except Exception:
                _log_exception('OutputPrompt failed')
            return 0
        self._preview_attached = True
        _log('attach on confirm: %s item(s) written' % (count or 0))
        try:
            NotificationManager.OutputPrompt(
                '%s：清单已写入公共库（%d 项）' % (UI_TITLE, count or 0))
        except Exception:
            _log_exception('OutputPrompt failed')
        return count

    def cancel_tool(self):
        self._cancel_pending_regeneration()
        self.confirmed = False
        self.discard_preview()
        self.finish_tool()

    def finish_tool(self):
        try:
            PyCommandState.StartDefaultCommand()
        except Exception:
            _log_exception('StartDefaultCommand failed')
        self.shutdown()

    def shutdown(self):
        if self._poll_job is not None:
            try:
                self.after_cancel(self._poll_job)
            except Exception:
                pass
            self._poll_job = None
        window = self._help_window
        self._help_window = None
        if window is not None:
            try:
                if window.winfo_exists():
                    window.destroy()
            except Exception:
                pass
        _disable_fault_logging()
        _purge_paths()
        try:
            if self.winfo_exists():
                self.destroy()
        except tk.TclError:
            pass


# ---------------------------------------------------------------------------
# 交互工具：点选水平直线
# ---------------------------------------------------------------------------


class BracketByLineTool(DgnElementSetTool):
    """点选一条水平直线段并放置端焊三角架的交互工具。"""

    def __init__(self, tool_id=0):
        DgnElementSetTool.__init__(self, tool_id)
        self.m_self = self
        self.tool_settings = None

    def _GetToolName(self, name):
        return WString('D5D6G12D19TriangleBracketByLineTool')

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
        NotificationManager.OutputPrompt(
            '请点选一条水平直线段：起点 P0＝焊接端面，终点 P2＝横担末端，'
            '直线标高＝管道底标高。右键放弃。')

    def _OnPostLocate(self, path, cant_accept_reason):
        if not DgnElementSetTool._OnPostLocate(self, path, cant_accept_reason):
            return False
        try:
            handle = ElementHandle(path.GetHeadElem(), path.GetRoot())
            line = geom.extract_horizontal_line(handle)
            if self.tool_settings is not None:
                # 只做悬停预览；不要在这里改 L1 / 触发建模——
                # 鼠标划过直线也会走到这里，反复触发重建。
                self.tool_settings.note_hover(line)
            return True
        except Exception as error:
            if self.tool_settings is not None:
                try:
                    self.tool_settings.note_hover_error(str(error))
                except Exception:
                    pass
            return False

    def _OnResetButton(self, event):
        settings = self.tool_settings
        if settings is not None:
            settings.request_cancel()
        return True

    def _OnElementModify(self, eeh):
        if self.tool_settings is None:
            return BentleyStatus.eERROR
        try:
            line = geom.extract_horizontal_line(eeh)
        except Exception as error:
            message = '直线提取失败：%s' % error
            _log_exception('element modify failed')
            try:
                self.tool_settings.note_hover_error(message)
                NotificationManager.OutputPrompt(message)
            except Exception:
                pass
            print(message)
            return BentleyStatus.eERROR
        # 原生回调里只记下所选直线；扫掠 / 布尔剪切 / 写库全部推迟到
        # Tk 定时器里做（queue_pick + _poll_ui），避免在原生回调里连续
        # 重型建模导致 MicroStation 崩溃。
        self.tool_settings.queue_pick(line, eeh)
        return BentleyStatus.eSUCCESS

    def _OnRestartTool(self):
        settings = self.tool_settings
        self.tool_settings = None
        BracketByLineTool.InstallNewInstance(self.GetToolId(), settings, False)

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
        settings.request_shutdown()

    @staticmethod
    def InstallNewInstance(tool_id=0, tool_settings=None, start_ui_loop=True):
        owner = tool_settings is None
        if owner:
            active = getattr(BracketByLineTool, '_active_settings', None)
            if active is not None:
                try:
                    if active.winfo_exists():
                        active.lift()
                        return None
                except tk.TclError:
                    pass
        settings = (tool_settings if tool_settings is not None
                    else _BracketDialog())
        if owner:
            BracketByLineTool._active_settings = settings
        tool = BracketByLineTool(tool_id)
        tool.tool_settings = settings
        tool.InstallTool()
        try:
            if start_ui_loop:
                settings.run_bentley_loop()
        finally:
            if owner:
                BracketByLineTool._active_settings = None
        return tool


def show_bracket_dialog():
    return BracketByLineTool.InstallNewInstance(0)


def PyMain():
    """供 MicroStation Python 管理器调用的入口。"""
    _enable_fault_logging()
    _log('PyMain: entry rev=%s' % UI_REVISION)
    _reload_runtime_modules()
    try:
        show_bracket_dialog()
    except Exception as error:
        detail = traceback.format_exc()
        _log('tool start failed: %s\n%s' % (error, detail))
        print('三角架插件启动失败：%s\n%s' % (error, detail))
        try:
            MessageCenter.ShowErrorMessage(
                '三角架插件启动失败：%s\n详见日志：%s' % (error, DEBUG_LOG),
                '', False)
        except Exception:
            pass
        return None
    return None


if __name__ == '__main__':
    PyMain()
