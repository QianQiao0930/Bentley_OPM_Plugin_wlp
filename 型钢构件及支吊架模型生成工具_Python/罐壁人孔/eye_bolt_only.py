# -*- coding: utf-8 -*-
"""图示 M20 吊环螺栓，Bentley OpenPlant / MicroStation MSPy 独立脚本。

在 Python Editor 执行本文件，第一次点取圆孔中心生成预览，第二次点击
确认；右键取消并删除本次预览。也可调用 draw_eye_bolt(DPoint3d, options)。
不导入同目录其它脚本，不改写任何已有文件。

建模说明（mm）：
  原点为圆孔中心及构件厚度中面交点；局部 XZ 为图纸平面，Y 为孔轴，
  Z 竖直向上。heading_deg 绕 Z 旋转图纸平面。
  200 是孔中心到杆顶的距离；底部 30 暂按孔直径解释。
  M20 按直径 20 表示，上端 100 MIN 默认取 100，螺纹为光滑公称外径
  包络，分段端面标识螺纹起点，不生成真实螺旋牙型。
  R30 暂按颈部中心线弯曲半径解释；圆环截面暂取与杆同径的圆钢。
  圆环中心线半径 = 孔半径 + 圆钢半径 = 25，外径 = 70。
  颈部采用与圆环外切的反向圆弧，保持杆轴通过圆孔中心。
  图中 DIN 444 是替代方案说明，本脚本复现图示弯环外形，未套用其规格。
  这些解释可通过下列参数调整；本文件不是吊装承载校核结果。

输出为普通单元中的实体圆环、颈弯、光杆、螺纹包络；连接处有实体重合，
未做布尔融合。只在 Bentley 中生成 DGN 图元，不导出 STEP。
普通 Python 可执行：python -B eye_bolt_only.py --self-test
"""

import math
import sys

DEFAULT_OPTIONS = {
    "bar_dia": 20.0,
    "hole_dia": 30.0,
    "top_height": 200.0,
    "thread_length": 100.0,
    "bend_radius": 30.0,
    "heading_deg": 0.0,
}
CELL_NAME = "M20_EYE_BOLT"
COLOR = 2


def _layout(options=None):
    """纯数学布局；长度为 mm，角度为 rad。"""
    p = dict(DEFAULT_OPTIONS)
    if options:
        unknown = set(options) - set(p)
        if unknown:
            raise ValueError("未知参数：%s" % ", ".join(sorted(unknown)))
        p.update(options)
    for key in p:
        p[key] = float(p[key])
        if not math.isfinite(p[key]):
            raise ValueError("参数必须是有限数值：%s" % key)
        if key != "heading_deg" and p[key] <= 0:
            raise ValueError("尺寸必须大于零：%s" % key)
    a = p["bar_dia"] / 2.0
    r = p["hole_dia"] / 2.0 + a
    b = p["bend_radius"]
    if b <= a:
        raise ValueError("颈弯中心线半径必须大于圆钢半径。")
    # 颈弯中心 C=(-b,h)，圆环中心 O=(0,0)，|OC|=b+r。
    h = math.sqrt((b + r) ** 2 - b ** 2)
    thread_start = p["top_height"] - p["thread_length"]
    if p["thread_length"] < 100:
        raise ValueError("图纸要求螺纹长度至少为 100 mm。")
    if thread_start <= h:
        raise ValueError("螺纹起点必须高于颈弯与直杆的切点。")
    p.update(bar_radius=a, eye_radius=r, neck_height=h,
             neck_angle=math.atan2(h, b), thread_start=thread_start,
             tangent_x=-b * r / (b + r),
             tangent_z=h * r / (b + r))
    return p


def _self_test():
    p = _layout()
    r, b, h = p["eye_radius"], p["bend_radius"], p["neck_height"]
    x, z = p["tangent_x"], p["tangent_z"]
    assert math.isclose(math.hypot(x, z), r)
    assert math.isclose(math.hypot(x + b, z - h), b)
    # 切点处两圆半径共线，故相切；杆端处颈弯切线竖直。
    assert abs(x * (z - h) - z * (x + b)) < 1e-9
    assert math.isclose(2 * (r - p["bar_radius"]), 30)
    assert math.isclose(p["top_height"], 200)
    assert math.isclose(p["top_height"] - p["thread_start"], 100)
    assert math.isclose(-b + b * math.cos(p["neck_angle"]), x)
    assert math.isclose(h - b * math.sin(p["neck_angle"]), z)
    for bad in ({"hole_dia": 0}, {"bar_dia": float("nan")},
                {"thread_length": 99}, {"top_height": 120},
                {"bend_radius": 5}, {"heading_deg": float("inf")}):
        try:
            _layout(bad)
        except ValueError:
            continue
        raise AssertionError("应拒绝参数：%r" % bad)
    print("PASS: dimensions, tangent continuity and invalid parameters")
    print("Origin: hole centre; hole 30; top Z 200; thread Z 100..200 mm")
    print("Envelope: X -35..35, Y -10..10, Z -35..200 mm (heading 0)")
    print("Bentley solid creation and viewport appearance require OPM validation.")


if "--self-test" not in sys.argv:
    from MSPyBentley import *
    from MSPyBentleyGeom import *
    from MSPyDgnPlatform import *
    from MSPyDgnView import *
    from MSPyMstnPlatform import *


    def _check(status, message, allow_none=False):
        """仅对已知无返回值的接口允许 None；其它接口仍严格检查。"""
        if status is None and allow_none:
            return
        try:
            succeeded = int(status) == 0
        except (TypeError, ValueError):
            raise RuntimeError("%s 返回了无效状态：%r" % (message, status))
        if not succeeded:
            raise RuntimeError("%s 状态码：%r" % (message, status))


    def _build_eye_bolt(placement_point, options=None):
        p = _layout(options)
        model_ref = ISessionMgr.ActiveDgnModelRef
        if model_ref is None:
            raise RuntimeError("请先打开三维 DGN 模型。")
        model = model_ref.GetDgnModel()
        if not model.Is3d():
            raise RuntimeError("请在三维 DGN 模型中运行。")
        scale = model.GetModelInfo().GetUorPerMeter() / 1000.0
        if not math.isfinite(scale) or scale <= 0:
            raise RuntimeError("模型单位换算无效。")
        angle = math.radians(p["heading_deg"])
        c, s = math.cos(angle), math.sin(angle)

        def point(x, y, z):
            return DPoint3d.From(placement_point.x + scale * (c*x - s*y),
                                placement_point.y + scale * (s*x + c*y),
                                placement_point.z + scale * z)

        cell = EditElementHandle()
        # MSPy 的此接口可返回 None，通过生成的句柄验证是否创建成功。
        _check(NormalCellHeaderHandler.CreateOrphanCellElement(
            cell, CELL_NAME, True, model), "创建吊环单元失败。", allow_none=True)
        if not cell.IsValid():
            raise RuntimeError("创建吊环单元失败：单元句柄无效。")

        def add(primitive):
            element = EditElementHandle()
            _check(DraftingElementSchema.ToElement(element, primitive, None, model),
                   "创建吊环实体失败。")
            props = ElementPropertiesSetter()
            props.SetColor(COLOR)
            props.Apply(element)
            _check(NormalCellHeaderHandler.AddChildElement(cell, element),
                   "添加吊环实体失败。")

        a = p["bar_radius"] * scale
        # 圆钢圆环：孔中心严格为局部 (0,0,0)，孔轴为局部 Y。
        add(ISolidPrimitive.CreateDgnTorusPipe(DgnTorusPipeDetail(
            point(0, 0, 0), DVec3d.From(c, s, 0), DVec3d.From(0, 0, 1),
            p["eye_radius"] * scale, a, 2 * math.pi, True)))
        # 从直杆切点向左下方弯曲，终点与圆环相切。
        add(ISolidPrimitive.CreateDgnTorusPipe(DgnTorusPipeDetail(
            point(-p["bend_radius"], 0, p["neck_height"]),
            DVec3d.From(c, s, 0), DVec3d.From(0, 0, -1),
            p["bend_radius"] * scale, a, p["neck_angle"], True)))
        for bottom, top in ((p["neck_height"], p["thread_start"]),
                            (p["thread_start"], p["top_height"])):
            add(ISolidPrimitive.CreateDgnCone(DgnConeDetail(
                point(0, 0, bottom), point(0, 0, top), a, a, True)))
        _check(NormalCellHeaderHandler.AddChildComplete(cell), "完成单元失败。")
        return cell


    def draw_eye_bolt(placement_point, options=None):
        """直接放置；placement_point 为模型 UOR 坐标，尺寸参数为 mm。"""
        cell = _build_eye_bolt(placement_point, options)
        _check(cell.AddToModel(), "写入活动模型失败。")
        return cell


    class EyeBoltPlacementTool(DgnPrimitiveTool):
        def __init__(self):
            DgnPrimitiveTool.__init__(self, 0, 0)
            self.m_self = self
            self.preview = None

        def _GetToolName(self, name):
            return WString("EyeBoltPlacementTool")

        def _OnPostInstall(self):
            DgnPrimitiveTool._OnPostInstall(self)
            AccuSnap.GetInstance().EnableSnap(True)
            NotificationManager.OutputPrompt("点取吊环圆孔中心；再次左键确认，右键取消。")

        def _OnDataButton(self, event):
            if self.preview is not None:
                self.preview = None
                PyCommandState.StartDefaultCommand()
                return True
            try:
                self.preview = draw_eye_bolt(event.GetPoint())
                NotificationManager.OutputPrompt("吊环预览已生成：再次左键确认，右键取消。")
            except Exception as error:
                print("吊环建模失败：%s" % error)
                NotificationManager.OutputPrompt("吊环建模失败：%s" % error)
            return True

        def _discard(self):
            if self.preview is not None:
                # 与目录内其它放置工具一致，兼容无状态返回的删除接口。
                _check(self.preview.DeleteFromModel(), "无法删除本次吊环预览。",
                       allow_none=True)
                self.preview = None

        def _OnResetButton(self, event):
            try:
                self._discard()
            except Exception as error:
                NotificationManager.OutputPrompt(str(error))
                return True
            PyCommandState.StartDefaultCommand()
            return True

        def _OnCleanup(self):
            try:
                self._discard()
            except Exception as error:
                print("清理吊环预览失败：%s" % error)


    _ACTIVE_TOOL = None


    def PyMain():
        global _ACTIVE_TOOL
        _ACTIVE_TOOL = EyeBoltPlacementTool()
        _ACTIVE_TOOL.InstallTool()


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    else:
        PyMain()
