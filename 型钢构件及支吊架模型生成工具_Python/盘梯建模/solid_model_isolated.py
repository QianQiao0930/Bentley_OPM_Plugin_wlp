"""暂时隔离的实体建模实现；当前辅助线入口不调用。平台三角支撑已删除。"""
# -*- coding: utf-8 -*-
"""Bentley Power Platform Python 入口：盘梯建模。"""
import os
import sys
import importlib.util
import traceback
import tkinter as tk
import win32gui
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spiral_geometry import Parameters, build_layout
from generation_log import GenerationLog
from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *


def load_handrail():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '普通钢结构围栏', 'steel_handrail.py')
    spec = importlib.util.spec_from_file_location('spiral_shared_handrail', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def generate(center, parameters, log=None):
    if log is None:
        log = GenerationLog()
        try:
            return generate(center, parameters, log)
        finally:
            log.close()
    with log.stage('参数计算与检查'):
        log.write('INFO', repr(parameters))
        layout = build_layout(parameters)
        log.write('INFO', '梯段%d；休息平台%d；平台标高%s；踏步%d' %
                  (len(layout['flights']), len(layout['landing_levels']), layout['landing_levels'], len(layout['treads'])))
        if not layout['checks']['structural_width_pass']:
            log.write('WARN', '保守结构净宽%.0fmm小于650mm。' % layout['checks']['minimum_structural_width'])
    with log.stage('Bentley模型与栏杆依赖初始化'):
        return _generate_geometry(center, parameters, layout, log)


def _generate_geometry(center, parameters, layout, log):
    ref = ISessionMgr.ActiveDgnModelRef
    model = ref.GetDgnModel()
    if not model.Is3d():
        raise ValueError('请激活三维模型。')
    scale = model.GetModelInfo().GetUorPerMeter()/1000.0
    rail = load_handrail()
    center_xyz = (center.x,center.y,center.z) if hasattr(center,'x') else tuple(center)
    if len(center_xyz) != 3:
        raise ValueError('罐中心必须包含三个坐标。')
    def world(p):
        return DPoint3d.From(*(center_xyz[i]+p[i]*scale for i in range(3)))
    def profile(points):
        array = DPoint3dArray()
        for p in points+[points[0]]:
            array.append(world(p))
        handle = EditElementHandle()
        if not rail._succeeded(ShapeHandler.CreateShapeElement(handle,None,array,True,ref)):
            raise RuntimeError('截面创建失败。')
        return handle
    builder = rail._HandrailCellBuilder(model)
    color = rail._element_color()
    for index,corners in enumerate([t['corners'] for t in layout['treads']]+layout['platforms']):
        # 扇形边界弦高误差由采样容差控制；顶面固定标高。
        name = '踏步 %d/%d' % (index+1,len(layout['treads'])) if index < len(layout['treads']) else '平台 %d/%d' % (index-len(layout['treads'])+1,len(layout['platforms']))
        with log.stage(name):
            element = rail._create_prism_from_corners(model,[world(p) for p in corners],parameters.plate_thickness*scale,color)
            builder.add(element)
    for index,sections in enumerate(layout['channels']):
        with log.stage('梯段%d %s侧板放样' % (index//2+1,'内' if index%2==0 else '外')):
            curves = CurveVectorPtrArray()
            for section_index,section in enumerate(sections):
                curve = ICurvePathQuery.ElementToCurveVector(profile(section))
                if curve is None:
                    raise RuntimeError('第%d个截面曲线转换失败' % (section_index+1))
                curves.append(curve)
            primitive = ISolidPrimitive.CreateDgnRuledSweep(DgnRuledSweepDetail(curves,True))
            element = rail._primitive_to_element(model,primitive,color)
            builder.add(element)
    with log.stage('调用栏杆插件：连续空间路径'):
        handrail, result = rail.build_continuous_handrail([world(p) for p in layout['rail']],
            height=parameters.rail_height,side='left' if parameters.direction==1 else 'right',
            end_posts=True,corner_posts=True,connect_adjacent=True, progress=lambda msg: log.write('INFO',msg))
        builder.add(handrail)
    with log.stage('组装普通单元并写入模型'):
        builder.build()
        builder.commit()
    # 所有几何成功后一次写入；中途失败不会留下半成品。
    return layout, result


