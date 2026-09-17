# -*- coding: utf-8 -*-
"""导出当前 DGN 中**全部**管道支吊架的统一清单。

本脚本只读公共库 ``PipeSupportComponents``：凡是按共享契约写入该库的支吊架
（端焊三角架、L 型管架，以及今后接入的其它支吊架）都会被一次汇总，输出按
类型统计的套数与按类型 / 构件 / 规格的材料明细。运行环境：OpenPlant /
MicroStation MSPython。
"""

from __future__ import division

import importlib
import os
import sys

from MSPyBentley import *  # noqa: F401,F403
from MSPyDgnView import *  # noqa: F401,F403


HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import 支吊架公共库  # noqa: E402


def PyMain():
    try:
        importlib.reload(支吊架公共库)
    except Exception:
        pass
    return 支吊架公共库.export_combined_bom()


if __name__ == '__main__':
    PyMain()
