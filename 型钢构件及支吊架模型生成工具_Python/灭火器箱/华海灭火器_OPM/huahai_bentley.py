# -*- coding: utf-8 -*-
"""Bentley PowerPlatform 原生实体、命名单元及 CEL 导出。仅在 OPM 中导入。"""
import math
import os
import shutil
from pathlib import Path

from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *

from huahai_geometry import build_recipe, normalize_capacity, point_and_vector, box_frame, cell_name


def check(status, operation, allow_void=False):
    if status is None and allow_void:
        return
    if status != BentleyStatus.eSUCCESS:
        raise RuntimeError('%s失败，Bentley 状态：%r' % (operation, status))


def active_model():
    model = ISessionMgr.GetActiveDgnModel()
    if model is None or not model.Is3d():
        raise RuntimeError('请先打开可编辑的三维 DGN 模型。')
    return model


def build_cell(capacity=4, origin=None, angle=0):
    """只创建内存单元，成功后调用 AddToModel 才写入活动模型。origin 为 UOR。"""
    model = active_model()
    origin = origin or DPoint3d(0,0,0)
    scale = model.GetModelInfo().GetUorPerMeter()/1000.0
    point_tuple, vector_tuple = point_and_vector((origin.x,origin.y,origin.z), angle, scale)
    recipe = build_recipe(capacity)

    def p(v):
        return DPoint3d(*point_tuple(v))

    def v(vec):
        return DVec3d(*vector_tuple(vec))

    def direction(vec):
        return DVec3d(*(a/scale for a in vector_tuple(vec)))

    cell = EditElementHandle()
    # 用命名单元接口指定底部中心为原点，避免匿名单元自动取范围中心。
    check(NormalCellHeaderHandler.CreateCellElement(
        cell, recipe['name'], origin, RotMatrix.FromAxisAndRotationAngle(2, math.radians(angle)),
        True, model), '创建命名单元', allow_void=True)
    if not cell.IsValid():
        raise RuntimeError('Bentley 未创建有效的命名单元句柄。')
    check(NormalCellHeaderHandler.SetDescription(cell,
        'Huahai %s kg / %s / diameter %s mm / height %s mm' %
        (recipe['capacity'],recipe['spec']['model'],recipe['spec']['body_diameter'],
         recipe['spec']['total_height'])), '设置单元说明')
    colors = {}

    def lathe(part):
        # 圆柱上下边缘保留原脚本的 9*scale mm 真圆弧圆角。
        r, f = part['radius'], part['fillet']
        lo, hi = part['bottom'], part['top']
        curve = CurveVector(CurveVector.eBOUNDARY_TYPE_Outer)

        def line(a, b):
            curve.Add(ICurvePrimitive.CreateLine(DSegment3d(p(a), p(b))))

        line((0,0,lo), (r-f,0,lo))
        curve.Add(ICurvePrimitive.CreateArc(DEllipse3d.FromVectors(
            p((r-f,0,lo+f)), v((f,0,0)), v((0,0,f)), -math.pi/2, math.pi/2)))
        line((r,0,lo+f), (r,0,hi-f))
        curve.Add(ICurvePrimitive.CreateArc(DEllipse3d.FromVectors(
            p((r-f,0,hi-f)), v((f,0,0)), v((0,0,f)), 0, math.pi/2)))
        line((r-f,0,hi), (0,0,hi))
        line((0,0,hi), (0,0,lo))
        return ISolidPrimitive.CreateDgnRotationalSweep(DgnRotationalSweepDetail(
            curve, p((0,0,0)), direction((0,0,1)), 2*math.pi, True))

    def hose(part):
        # 沿平滑中心线以圆截面生成一个封闭放样实体。截面一致朝向避免扭转。
        points = part['points']
        sections = CurveVectorPtrArray()
        radius = part['radius']
        for i, center in enumerate(points):
            before, after = points[max(0,i-1)], points[min(len(points)-1,i+1)]
            dx, dz = after[0]-before[0], after[2]-before[2]
            length = math.hypot(dx, dz)
            if length <= 1e-9:
                raise RuntimeError('软管中心线有重复点。')
            section = CurveVector(CurveVector.eBOUNDARY_TYPE_Outer)
            section.Add(ICurvePrimitive.CreateArc(DEllipse3d.FromVectors(
                p(center), v((0,radius,0)), v((-dz/length*radius,0,dx/length*radius)),
                0, 2*math.pi)))
            sections.append(section)
        return ISolidPrimitive.CreateDgnRuledSweep(DgnRuledSweepDetail(sections, True))

    for part in recipe['parts']:
        kind = part['kind']
        if kind == 'cone':
            primitive = ISolidPrimitive.CreateDgnCone(DgnConeDetail(
                p(part['start']), p(part['end']), part['r0']*scale, part['r1']*scale, True))
        elif kind == 'box':
            base, top, x, y = box_frame(part)
            dx, dy, dz = part['size']
            primitive = ISolidPrimitive.CreateDgnBox(DgnBoxDetail(
                p(base), p(top), direction(x), direction(y),
                dx*scale, dy*scale, dx*scale, dy*scale, True))
        elif kind == 'torus':
            primitive = ISolidPrimitive.CreateDgnTorusPipe(DgnTorusPipeDetail(
                p(part['center']), direction((1,0,0)), direction((0,0,1)),
                part['major']*scale, part['minor']*scale, 2*math.pi, True))
        elif kind == 'rounded_bottle':
            primitive = lathe(part)
        elif kind == 'hose':
            primitive = hose(part)
        else:
            raise RuntimeError('未知几何：%s' % kind)
        if primitive is None:
            raise RuntimeError('生成实体失败：%s' % part['name'])
        element = EditElementHandle()
        check(DraftingElementSchema.ToElement(element, primitive, None, model), part['name'])
        if not element.IsValid():
            raise RuntimeError('实体句柄无效：%s' % part['name'])
        rgb = tuple(part['color'])
        if rgb not in colors:
            colors[rgb] = DgnColorMap.CreateElementColor(
                IntColorDef(*rgb), None, None, ISessionMgr.GetActiveDgnFile())
        props = ElementPropertiesSetter()
        props.SetColor(colors[rgb])
        props.SetWeight(1)
        props.Apply(element)
        check(NormalCellHeaderHandler.AddChildElement(cell, element), '加入 '+part['name'])
    check(NormalCellHeaderHandler.AddChildComplete(cell), '完成灭火器单元')
    return cell


def place_extinguisher(capacity=4, origin=None, angle=0):
    cell = build_cell(capacity, origin, angle)
    check(cell.AddToModel(), '写入活动模型')
    return cell


def default_seed():
    candidates = (
        Path(__file__).with_name('seed3d.dgn'),
        Path('D:/Program Files/Bentley/OpenPlant 2024/OpenPlantModeler/Default/Seed/seed3d.dgn'),
        Path('C:/Program Files/Bentley/OpenPlant 2024/OpenPlantModeler/Default/Seed/seed3d.dgn'),
        Path('C:/Program Files/Bentley/OpenPlant 2024/IsometricsManager/Default/Seed/seed3d.dgn'),
    )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return ''


def export_cell_library(output_path, capacities=(2,4,5,6,8), seed_path=None):
    """创建真实 V8 CEL，通过 Bentley AddLibDescr 写入，不把 STEP 改后缀。

    导出从内存生成的零原点单元，不在当前工程中添加临时几何。
    已有目标文件拒绝覆盖；如中途失败，保留 .partial.cel 供排查。
    """
    active_model()
    keys = tuple(dict.fromkeys(normalize_capacity(c) for c in capacities))
    if not keys:
        raise ValueError('至少选择一个规格。')
    target = Path(output_path).expanduser().resolve()
    if target.suffix.lower() != '.cel':
        raise ValueError('单元库文件必须使用 .cel 扩展名。')
    if target.exists():
        raise FileExistsError('文件已存在，请另选名称：%s' % target)
    seed = Path(seed_path or default_seed())
    if not seed.is_file():
        raise FileNotFoundError('请选择 Bentley 提供的空白三维 seed3d.dgn 种子文件。')
    target.parent.mkdir(parents=True, exist_ok=True)
    # 唯一临时路径，不覆盖既有导出或工程。
    import uuid
    staging = target.with_name(target.stem+'.'+uuid.uuid4().hex[:8]+'.partial.cel')
    shutil.copyfile(str(seed), str(staging))
    previous = BeFileName()
    Cell.GetLibraryName(previous)
    previous_name = str(previous)
    attached = False
    library = None
    try:
        check(Cell.AttachLibrary(BeFileName(), BeFileName(str(staging)), None, True), '附加临时单元库')
        attached = True
        for key in keys:
            cell = build_cell(key, DPoint3d(0,0,0), 0)
            check(Cell.AddLibDescr(cell.GetElementDescr(), CellAddType.NormalCell, False),
                  '保存 '+cell_name(key))
        status, library = Cell.GetLibraryObject(str(staging), False)
        check(status, '获取单元库对象')
        if library is None:
            raise RuntimeError('单元库对象为空。')
        check(library.ProcessChanges(DgnSaveReason.eUserInitiated), '保存单元库到磁盘')
        # 确认每个命名单元已入库。
        for key in keys:
            if not Cell.ExistsInLibrary(cell_name(key)):
                raise RuntimeError('库中找不到 '+cell_name(key))
    finally:
        library = None
        if attached:
            # AttachLibrary 的 null 输入表示解除附加；同一路径原库则恢复原库。
            check(Cell.AttachLibrary(BeFileName(), BeFileName(previous_name) if previous_name else None,
                                     None, True), '恢复原单元库')
    # 所有接口成功才发布文件。Windows rename 在目标存在时失败，防止竞态覆盖。
    os.rename(str(staging), str(target))
    return str(target)


ACTIVE_TOOL = None


class ExtinguisherPlacementTool(DgnPrimitiveTool):
    def __init__(self, capacity, angle):
        DgnPrimitiveTool.__init__(self, 0, 0)
        self.capacity = normalize_capacity(capacity)
        self.angle = angle
        self.m_self = self

    def _GetToolName(self, name):
        return WString('HuahaiExtinguisherPlacement')

    def _OnPostInstall(self):
        DgnPrimitiveTool._OnPostInstall(self)
        AccuSnap.GetInstance().EnableSnap(True)
        NotificationManager.OutputPrompt('点取灭火器底部中心；可连续放置，右键结束。')

    def _OnDataButton(self, event):
        try:
            place_extinguisher(self.capacity, event.GetPoint(), self.angle)
            MessageCenter.ShowInfoMessage('已放置华海 %s kg 灭火器单元。' % self.capacity, '', False)
        except Exception:
            import traceback
            error = traceback.format_exc()
            try:
                Path(__file__).with_name('huahai_debug.log').write_text(error, encoding='utf-8')
            except OSError:
                pass
            MessageCenter.ShowErrorMessage('灭火器生成失败。', error, False)
        return True

    def _OnResetButton(self, event):
        PyCommandState.StartDefaultCommand()
        return True

    def _OnRestartTool(self):
        install_placement(self.capacity, self.angle)


def install_placement(capacity=4, angle=0):
    global ACTIVE_TOOL
    active_model()
    ACTIVE_TOOL = ExtinguisherPlacementTool(capacity, angle)
    ACTIVE_TOOL.InstallTool()
