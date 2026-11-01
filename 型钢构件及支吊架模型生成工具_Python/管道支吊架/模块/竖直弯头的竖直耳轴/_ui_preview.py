# -*- coding: utf-8 -*-
"""本地 UI 预览工具（无需 OPM 环境）。

用法：
    python _ui_preview.py            # 交互式打开对话框，可查看悬停/聚焦效果
    python _ui_preview.py --shot     # 渲染成 preview.png 供快速查看

原理：在导入主脚本前用空模块顶替 MSPy* 依赖，只测 UI，不触建模逻辑。
"""

import os
import sys
import types

STUB_MODULES = ("MSPyBentley", "MSPyBentleyGeom", "MSPyECObjects", "MSPyDgnPlatform",
                "MSPyDgnView", "MSPyMstnPlatform")


def _install_stubs():
    for name in STUB_MODULES:
        module = types.ModuleType(name)
        if name == "MSPyMstnPlatform":
            class _DgnElementSetTool(object):
                eUSES_SS_None = 0

                def __init__(self, *args, **kwargs):
                    pass

            module.DgnElementSetTool = _DgnElementSetTool
            module.DgnPrimitiveTool = _DgnElementSetTool
        sys.modules[name] = module


def _load_plugin():
    import importlib.util
    here = os.path.dirname(os.path.abspath(__file__))
    if os.path.basename(os.path.dirname(here)) == '模块':
        plugin_root = os.path.dirname(os.path.dirname(here))
    else:
        plugin_root = os.path.join(os.path.dirname(here), '管道支吊架')
    path = os.path.join(plugin_root, 'F2-[竖直弯头的竖直耳轴].py')
    spec = importlib.util.spec_from_file_location("trunnion_plugin", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    _install_stubs()
    plugin = _load_plugin()

    panel = plugin.TrunnionPanel()
    panel._selection.set(
        "元素 32456｜LONG_RADIUS_90_DEGREE_PIPE_ELBOW\n"
        "DN250 · 外径 273.0 mm → 耳轴 DN150（Ø168.3）\n"
        "水平端 (13737.5, -7593.3, 0.0)｜竖直端 (13356.5, -7593.3, 381.0) mm"
    )
    panel._append_log(
        "已生成｜元素 32456｜DN250｜H 1000.0 mm｜A 方形底板｜新图元 41001, 41002"
    )
    panel._apply_status("生成完成；可继续点选另一个竖直弯头。")

    if "--shot" in sys.argv:
        from PIL import ImageGrab

        panel.update_idletasks()
        panel.update()
        x = panel.winfo_rootx()
        y = panel.winfo_rooty()
        width = panel.winfo_width()
        height = panel.winfo_height()
        image = ImageGrab.grab(bbox=(x, y, x + width, y + height))
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "preview.png")
        image.save(out)
        panel.destroy()
        print("saved: %s" % out)
        return

    panel.mainloop()


if __name__ == "__main__":
    main()
