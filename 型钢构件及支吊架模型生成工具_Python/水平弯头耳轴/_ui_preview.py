# -*- coding: utf-8 -*-
"""本地 UI 预览工具（无需 OPM 环境）。

用法：
    python _ui_preview.py            # 交互式打开对话框
    python _ui_preview.py --shot     # 渲染成 preview.png
"""

import os
import sys
import types

STUB_MODULES = ("MSPyBentley", "MSPyBentleyGeom", "MSPyDgnPlatform",
                "MSPyDgnView", "MSPyMstnPlatform")


def _install_stubs():
    for name in STUB_MODULES:
        module = types.ModuleType(name)
        if name == "MSPyMstnPlatform":
            class _DgnPrimitiveTool(object):
                def __init__(self, *args, **kwargs):
                    pass
            module.DgnPrimitiveTool = _DgnPrimitiveTool
        sys.modules[name] = module


def _load_plugin():
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "水平弯头耳轴.py")
    spec = importlib.util.spec_from_file_location("trunnion_plugin", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    _install_stubs()
    plugin = _load_plugin()

    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    dialog = plugin.TrunnionDialog()

    if "--shot" in sys.argv:
        dialog.show()
        for _ in range(10):
            app.processEvents()
        image = dialog.grab()
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "preview.png")
        image.save(out)
        print("saved: %s" % out)
        return

    dialog.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
