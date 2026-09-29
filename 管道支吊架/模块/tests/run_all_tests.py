# -*- coding: utf-8 -*-
"""本目录全部单测的入口（ASCII 文件名，规避命令行里中文路径的编码问题）。

用法::

    <python> -B 管道支吊架/模块/tests/run_all_tests.py

等价于 ``python -m unittest discover -s 管道支吊架/模块/tests``，但把发现与
``sys.path`` 的处理都放在文件内部，因此在 Windows 控制台代码页不是 UTF-8 时
也能直接运行。
"""

from __future__ import division

import os
import sys
import unittest


_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


def main():
    suite = unittest.defaultTestLoader.discover(_HERE, pattern='test_*.py')
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
