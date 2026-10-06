# -*- coding: utf-8 -*-
"""Bentley Power Platform Python 入口：盘梯建模。"""
import os
import sys
import traceback
import tkinter as tk
import win32gui
import win32process
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spiral_geometry import Parameters, build_layout, build_guides, build_z_tread_parts, build_platform_parts
from generation_log import GenerationLog
from upright_beams import build_u_profiles
from MSPyBentley import *
from MSPyBentleyGeom import *
from MSPyDgnPlatform import *
from MSPyDgnView import *
from MSPyMstnPlatform import *


def _succeeded(status):
    # bool True 在Python中等于1，不能按BentleyStatus的0成功约定判断。
    if isinstance(status,bool):
        return status
    return status == 0 or status == BentleyStatus.eSUCCESS


def hide_system_python_console(log):
    """只隐藏当前Bentley进程中明确命名的Python控制台窗口。"""
    titles={'python console','python控制台','python 控制台','python output','python输出','python 输出'}
    try:
        def hide(handle,unused):
            title=win32gui.GetWindowText(handle).strip().lower()
            if title not in titles:
                return
            thread_id,process_id=win32process.GetWindowThreadProcessId(handle)
            if process_id==os.getpid() and win32gui.IsWindowVisible(handle):
                win32gui.ShowWindow(handle,0)
                log.write('INFO','已隐藏系统Python控制台，日志仅显示在插件窗口。')
        win32gui.EnumWindows(hide,None)
    except Exception as error:
        log.write('WARN','隐藏系统Python控制台失败：'+str(error))


def generate(center, parameters, log=None, with_beams=False):
    if log is None:
        log=GenerationLog()
        try:
            return generate(center,parameters,log,with_beams=with_beams)
        finally:
            log.close()
    with log.stage('计算盘梯放样辅助线'):
        log.write('INFO',repr(parameters))
        layout=build_layout(parameters, auxiliary_only=True)
        guides=build_guides(layout)
        log.write('INFO','辅助线模式：%d梯段，%d休息平台，%d条线；不创建实体。' %
                  (len(layout['flights']),len(layout['landing_levels']),len(guides)))
    ref=ISessionMgr.ActiveDgnModelRef
    model=ref.GetDgnModel()
    if not model.Is3d():
        raise ValueError('请激活三维模型。')
    scale=model.GetModelInfo().GetUorPerMeter()/1000.0
    xyz=(center.x,center.y,center.z) if hasattr(center,'x') else tuple(center)
    if len(xyz)!=3:
        raise ValueError('放置中心必须包含三个坐标。')
    with log.stage('初始化辅助线单元'):
        cell=EditElementHandle()
        status=NormalCellHeaderHandler.CreateOrphanCellElement(cell,'SPIRAL_STAIR_GUIDES',True,model)
        valid=cell.IsValid()
        log.write('INFO','CreateOrphanCellElement返回%s（%s）；单元句柄有效=%s' %
                  (repr(status),type(status).__name__,valid))
        # 该API在不同MSPy绑定中可能返回bool或None，直接检查输出句柄。
        if not valid:
            raise RuntimeError('辅助线单元初始化失败：句柄无效，返回%s。' % repr(status))
    paths=[]
    for index,guide in enumerate(guides):
        with log.stage('辅助线 %d/%d：%s' % (index+1,len(guides),guide['name'])):
            points=DPoint3dArray()
            for point in guide['points']:
                points.append(DPoint3d.From(*(xyz[i]+point[i]*scale for i in range(3))))
            line=EditElementHandle()
            status=LineStringHandler.CreateLineStringElement(line,None,points,True,ref)
            if not _succeeded(status):
                raise RuntimeError('辅助线创建失败：%s，状态%r（%s）' % (guide['name'],status,type(status).__name__))
            if guide.get('standalone'):
                paths.append(line)
            else:
                status=NormalCellHeaderHandler.AddChildElement(cell,line)
                if not _succeeded(status):
                    raise RuntimeError('辅助线加入单元失败：%s，状态%r（%s）' % (guide['name'],status,type(status).__name__))
    beams=[]
    if with_beams:
        log.write('INFO','内梁腹板下缘路径半径=罐外半径+100mm+间隙=%.3fmm。' % layout['inner_radius'])
        if parameters.wall_gap == 0:
            log.write('WARN','螺旋基准已让出100mm腿宽；平台直线弦仍可能向罐壁内偏，需复核平台连接。')
        beams=build_beam_elements(guides[:2],xyz,scale,model,ref,log)
        beams.append(build_tread_element(layout,xyz,scale,model,ref,log))
    with log.stage('写入辅助线与梯梁'):
        if not _succeeded(NormalCellHeaderHandler.AddChildComplete(cell)):
            raise RuntimeError('辅助线单元组装失败。')
        committed=[]
        try:
            # 梯梁路径作为独立元素，可直接选取；其他轮廓仍归入辅助线单元。
            for index,element in enumerate(paths+[cell]+beams):
                status=element.AddToModel()
                if not _succeeded(status):
                    raise RuntimeError('辅助线元素%d写入失败：%r。' % (index+1,status))
                committed.append(element)
            log.write('INFO','内外梯梁路径及梁顶开口外缘栏杆路径均独立写入；栏杆基准上移200mm，内侧向内、外侧向外偏移100mm，顶部折回按横梁开口方向连接。')
        except Exception:
            for element in reversed(committed):
                try:
                    status=element.DeleteFromModel()
                    if status is not None and not _succeeded(status):
                        log.write('ERROR','回退已写入辅助线失败：%r' % status)
                except Exception as error:
                    log.write('ERROR','回退已写入辅助线异常：'+str(error))
            raise
    return layout,dict(guide_count=len(guides),mode='beams' if with_beams else 'guides',beam_count=len(beams))


def build_beam_elements(guides,xyz,scale,model,ref,log):
    """每个位置明确布置竖直截面，逐段放样避免路径法向导致截面侧倾。"""
    cells=[]
    for side,guide in zip(('inner','outer'),guides):
        with log.stage('%s侧U形梯梁：200×100×6，腹板底部外角基准，向上200mm' % side):
            profiles=build_u_profiles(guide['points'],side,return_start=guide.get('return_start'))
            cell=EditElementHandle()
            NormalCellHeaderHandler.CreateOrphanCellElement(cell,'SPIRAL_U_'+side.upper(),True,model)
            if not cell.IsValid():
                raise RuntimeError('梯梁单元句柄无效。')
            curves=[]
            for index,profile in enumerate(profiles):
                points=DPoint3dArray()
                for p in profile+[profile[0]]:
                    points.append(DPoint3d.From(*(xyz[i]+p[i]*scale for i in range(3))))
                handle=EditElementHandle()
                status=ShapeHandler.CreateShapeElement(handle,None,points,True,ref)
                if not _succeeded(status):
                    raise RuntimeError('梯梁截面%d创建失败：%r' % (index+1,status))
                curve=ICurvePathQuery.ElementToCurveVector(handle)
                if curve is None:
                    raise RuntimeError('梯梁截面%d转换失败。' % (index+1))
                curves.append(curve)
            for index in range(len(curves)-1):
                log.write('INFO','竖直U形梯梁放样 %d/%d' % (index+1,len(curves)-1))
                pair=CurveVectorPtrArray()
                pair.append(curves[index])
                pair.append(curves[index+1])
                primitive=ISolidPrimitive.CreateDgnRuledSweep(DgnRuledSweepDetail(pair,True))
                if primitive is None:
                    raise RuntimeError('第%d段放样实体创建失败。' % (index+1))
                element=EditElementHandle()
                status=DraftingElementSchema.ToElement(element,primitive,None,model)
                if not _succeeded(status):
                    raise RuntimeError('第%d段放样实体转换失败：%r' % (index+1,status))
                status=NormalCellHeaderHandler.AddChildElement(cell,element)
                if not _succeeded(status):
                    raise RuntimeError('第%d段梯梁加入单元失败：%r' % (index+1,status))
            if not _succeeded(NormalCellHeaderHandler.AddChildComplete(cell)):
                raise RuntimeError('梯梁单元组装失败。')
            cells.append(cell)
    return cells


def build_tread_element(layout,xyz,scale,model,ref,log):
    with log.stage('Z形踏板简化实体'):
        cell=EditElementHandle()
        NormalCellHeaderHandler.CreateOrphanCellElement(cell,'SPIRAL_Z_TREADS',True,model)
        if not cell.IsValid():
            raise RuntimeError('踏板单元初始化失败。')
        plates=[('踏板%d' % (index+1),build_z_tread_parts(layout,tread)) for index,tread in enumerate(layout['treads'])]
        plates.extend(('顶部平台' if index==len(layout['platforms'])-1 else '休息平台%d' % (index+1),
                       build_platform_parts(layout,index)) for index in range(len(layout['platforms'])))
        for name,parts in plates:
            for part in parts:
                with log.stage('%s：%s' % (name,part['name'])):
                    points=DPoint3dArray()
                    for p in part['corners']+[part['corners'][0]]:
                        points.append(DPoint3d.From(*(xyz[i]+p[i]*scale for i in range(3))))
                    profile=EditElementHandle()
                    status=ShapeHandler.CreateShapeElement(profile,None,points,True,ref)
                    if not _succeeded(status):
                        raise RuntimeError('踏板轮廓创建失败：%r' % status)
                    status,body=SolidUtil.Convert.ElementToBody(profile,True,True,False)
                    if not _succeeded(status):
                        raise RuntimeError('踏板轮廓转实体失败：%r' % status)
                    status=SolidUtil.Modify.ThickenSheet(body,part['thickness']*scale,0.0)
                    if not _succeeded(status):
                        raise RuntimeError('踏板拉伸失败：%r' % status)
                    element=EditElementHandle()
                    status=SolidUtil.Convert.BodyToElement(element,body,profile,model)
                    if not _succeeded(status):
                        raise RuntimeError('踏板实体转换失败：%r' % status)
                    if not _succeeded(NormalCellHeaderHandler.AddChildElement(cell,element)):
                        raise RuntimeError('踏板实体加入单元失败。')
        if not _succeeded(NormalCellHeaderHandler.AddChildComplete(cell)):
            raise RuntimeError('踏板单元组装失败。')
        return cell


class PlacementTool(DgnPrimitiveTool):
    def __init__(self, parameters, log=None, finished=None, with_beams=False):
        DgnPrimitiveTool.__init__(self,0,0)
        self.parameters=parameters
        self.log=log or GenerationLog()
        self.finished=finished
        self.completed=False
        self.with_beams=with_beams
        self.m_self=self
    def _OnPostInstall(self):
        AccuSnap.GetInstance().EnableSnap(True)
        DgnPrimitiveTool._OnPostInstall(self)
        self.log.write('INFO','放置工具已激活；请在模型视图左键点取中心，右键取消。')
        NotificationManager.OutputPrompt('点取罐中心基准点（输入标高相对此点）；右键取消。')
    def _OnDataButton(self,event):
        if self.completed:
            return True
        try:
            point=event.GetPoint()
            self.log.write('INFO','已收到模型点取事件；中心UOR=(%.6f, %.6f, %.6f)' % (point.x,point.y,point.z))
            layout, result=generate(point,self.parameters,self.log,with_beams=self.with_beams)
            message='盘梯辅助线已写入：%d条，%d梯段。' % (result['guide_count'],len(layout['flights']))
            message += '内外U形梯梁和Z形踏板已写入，需检查实际实体。' if self.with_beams else '未生成实体。'
            NotificationManager.OutputPrompt(message)
            self.log.write('INFO',message)
        except Exception as error:
            NotificationManager.OutputPrompt('盘梯生成失败：'+str(error))
            self.log.write('ERROR', '失败阶段：%s；%s；完整日志：%s' % (self.log.failed_stage or self.log.current_stage,error,self.log.path))
            if self.log.failed_stage is None:
                self.log.write('ERROR',traceback.format_exc())
        self._finish()
        self._ExitTool()
        return True
    def _OnResetButton(self,event):
        if not self.completed:
            self.log.write('INFO','用户取消放置。')
        self._finish()
        self._ExitTool()
        return True
    def _OnRestartTool(self):
        if not self.completed:
            self.log.write('INFO','放置工具请求重启，结束本次放置；可重新点击生成。')
        self._finish()
        self._ExitTool()

    def _finish(self):
        if self.completed:
            return
        self.completed=True
        self.log.close()
        if self.finished:
            self.finished()

    def _OnCleanup(self):
        if not self.completed:
            self.log.write('INFO','放置工具被退出或替换。')
        self._finish()


class _MicroStationTk(tk.Tk):
    """与现有爬梯插件一致：交替处理Tk及Bentley输入队列。"""
    def __init__(self):
        tk.Tk.__init__(self)
        self._attached_to_mstn=False
        self.placement_tool=None

    def microstation_mainloop(self):
        while True:
            try:
                self.update()
                if not win32gui.IsWindow(self.winfo_id()):
                    break
                if not self._attached_to_mstn:
                    frame_handle=win32gui.GetParent(self.winfo_id())
                    if frame_handle:
                        PyCadInputQueue.AttachTkinterToolSetting(frame_handle)
                        self._attached_to_mstn=True
            except tk.TclError:
                break
            PyCadInputQueue.PythonMainLoop()


def PyMain():
    root=_MicroStationTk()
    root.title('盘梯放样辅助线 · 参数单位 mm')
    labels=[('tank_diameter','罐体外径'),('start_z','起点标高'),('end_z','终点标高'),
            ('landing_interval','休息平台高度间隔'),('riser','踏步高度'),('tread_depth','内缘踏面深度'),
            ('clear_width','净宽'),('wall_gap','罐壁间隙'),('landing_length','休息平台内缘长度'),
            ('top_length','顶部平台内缘长度'),('start_angle','起始角 rad'),('direction','方向 +1/-1')]
    defaults=Parameters()
    fields={}
    for row,(name,label) in enumerate(labels):
        tk.Label(root,text=label).grid(row=row,column=0,padx=12,pady=3,sticky='w')
        value=tk.StringVar(value=str(getattr(defaults,name)))
        fields[name]=value
        tk.Entry(root,textvariable=value).grid(row=row,column=1,padx=12,pady=3)
    tk.Label(root,text='200×100×6背靠背U形梯梁；内路径半径=罐半径+100+间隙\n基准：腹板底部外角；截面从辅助线向上200mm。').grid(row=len(labels),columnspan=2,padx=12,pady=8)
    def accept(with_beams=False):
        try:
            values={k:float(v.get()) for k,v in fields.items()}
            p=Parameters(**values)
            build_layout(p, auxiliary_only=True)
        except Exception as error:
            messagebox.showerror('参数错误',str(error),parent=root)
            return
        panel=tk.Toplevel(root)
        panel.title('盘梯建模 · 进度与错误日志')
        output=ScrolledText(panel,width=100,height=28,state='disabled')
        output.pack(fill='both',expand=True)
        def display(text):
            output.configure(state='normal')
            output.insert('end',text+'\n')
            output.see('end')
            output.configure(state='disabled')
            panel.update_idletasks()
        log=GenerationLog(sink=display)
        hide_system_python_console(log)
        actions=tk.Frame(panel)
        actions.pack(fill='x')
        def copy_log():
            panel.clipboard_clear()
            panel.clipboard_append('\n'.join(log.lines))
        tk.Button(actions,text='复制完整日志',command=copy_log).pack(side='left',padx=8,pady=6)
        tk.Button(actions,text='打开日志文件',command=lambda:os.startfile(log.path)).pack(side='left',padx=8,pady=6)
        log.write('INFO','等待点取罐中心基准点。')
        generate_button.configure(state='disabled')
        beam_button.configure(state='disabled')
        def finished():
            root.placement_tool=None
            try:
                generate_button.configure(state='normal')
                beam_button.configure(state='normal')
            except tk.TclError:
                pass
        try:
            # 保持工具强引用直到其退出，避免Python虚拟回调对象提前回收。
            root.placement_tool=PlacementTool(p,log,finished,with_beams=with_beams)
            log.write('INFO','正在安装Bentley放置工具。')
            root.placement_tool.InstallTool()
        except Exception:
            log.write('ERROR','安装放置工具失败：'+traceback.format_exc())
            log.close()
            finished()
    generate_button=tk.Button(root,text='绘制辅助线并点取罐中心',command=accept)
    generate_button.grid(row=len(labels)+1,columnspan=2,pady=12)
    beam_button=tk.Button(root,text='生成U形梯梁与Z形踏板并点取罐中心',command=lambda:accept(True))
    beam_button.grid(row=len(labels)+2,columnspan=2,pady=8)
    def close_window():
        tool=root.placement_tool
        if tool is not None and not tool.completed:
            tool.log.write('INFO','关闭参数窗口，退出放置工具。')
            tool._finish()
            tool._ExitTool()
        root.destroy()
    root.protocol('WM_DELETE_WINDOW',close_window)
    root.microstation_mainloop()

if __name__=='__main__':
    PyMain()
