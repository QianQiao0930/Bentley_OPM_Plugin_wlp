"""不启动 Bentley：调用真实栏杆入口，替代原生实体API验证坐标回归。"""
import ast
import math
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from generation_log import GenerationLog
from spiral_geometry import Parameters, build_layout
from spiral_geometry import build_guides
from contextlib import nullcontext

class IntegrationContractTests(unittest.TestCase):
    def test_auxiliary_entry_only_creates_lines_and_commits_once(self):
        source=Path(__file__).with_name('spiral_stair.py')
        tree=ast.parse(source.read_text(encoding='utf-8-sig'))
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('generate','_succeeded')]
        lines,commits=[],[]
        class Handle:
            def AddToModel(self): commits.append(self); return 0
            def IsValid(self): return True
        def create_line(handle,template,points,is3d,ref):
            lines.append(points)
            return 0
        model=SimpleNamespace(Is3d=lambda:True,GetModelInfo=lambda:SimpleNamespace(GetUorPerMeter=lambda:2000))
        env=dict(build_layout=build_layout,build_guides=build_guides,
                 ISessionMgr=SimpleNamespace(ActiveDgnModelRef=SimpleNamespace(GetDgnModel=lambda:model)),
                 EditElementHandle=Handle,DPoint3dArray=list,DPoint3d=SimpleNamespace(From=lambda *xyz:xyz),
                 BentleyStatus=SimpleNamespace(eSUCCESS=0),
                 NormalCellHeaderHandler=SimpleNamespace(CreateOrphanCellElement=lambda *args:True,
                     AddChildElement=lambda *args:0,AddChildComplete=lambda *args:0),
                 LineStringHandler=SimpleNamespace(CreateLineStringElement=create_line))
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),env)
        log=SimpleNamespace(stage=lambda name:nullcontext(),write=lambda *args:None)
        layout,result=env['generate']((100,200,300),Parameters(),log)
        self.assertEqual(result['mode'],'guides')
        self.assertEqual(len(lines),107)
        self.assertEqual(len(commits),5)
        self.assertEqual(lines[-1],[(100,200,300),(100,200,40300)])
        self.assertTrue(env['_succeeded'](True))
        self.assertFalse(env['_succeeded'](False))
        self.assertFalse(env['_succeeded'](1))
        self.assertTrue(env['_succeeded'](0))
        # 无返回值但有效的输出句柄也不应被当作初始化失败。
        env['NormalCellHeaderHandler'].CreateOrphanCellElement=lambda *args:None
        env['generate']((0,0,0),Parameters(),log)
        # 环境不含栏杆或实体API，入口如调用它们测试即失败。
        commits.clear()
        env['LineStringHandler'].CreateLineStringElement=lambda *args:1
        with self.assertRaisesRegex(RuntimeError,'辅助线创建失败'):
            env['generate']((0,0,0),Parameters(),log)
        self.assertEqual(commits,[])

    def test_spatial_kickplate_uses_segment_lofts(self):
        source=Path(__file__).resolve().parents[1]/'普通钢结构围栏'/'steel_handrail.py'
        tree=ast.parse(source.read_text(encoding='utf-8-sig'))
        names={'_horizontal_unit','_horizontal_normal','_offset_spatial_polyline_pieces',
               '_spatial_kickplate_profiles','_add_spatial_kickplate','_add_kickplate'}
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
        env=dict(hypot=math.hypot,PATH_TOLERANCE_MM=.01,STANCHION_OD=48.3,
                 KICKPLATE_CLEARANCE=10.,KICKPLATE_THICKNESS=6.,
                 KICKPLATE_BOTTOM_Z=10.,KICKPLATE_HEIGHT=130.,
                 ISessionMgr=SimpleNamespace(ActiveDgnModelRef=SimpleNamespace(Is3d=lambda:True)),
                 DPoint3dArray=list,CurveVectorPtrArray=list,EditElementHandle=SimpleNamespace,
                 _point_uor=lambda origin,p,scale:p,_succeeded=lambda status:status==0,
                 ShapeHandler=SimpleNamespace(CreateShapeElement=lambda *args:0),
                 ICurvePathQuery=SimpleNamespace(ElementToCurveVector=lambda handle:handle),
                 DgnRuledSweepDetail=lambda pair,capped:pair,
                 ISolidPrimitive=SimpleNamespace(CreateDgnRuledSweep=lambda detail:detail),
                 _primitive_to_element=lambda model,primitive,color:primitive)
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),env)
        for interval,direction in ((10000,1),(5000,-1)):
            points=build_layout(Parameters(wall_gap=150,landing_interval=interval,direction=direction))['rail']
            pieces=[]
            for start,end in zip(points,points[1:]):
                length=sum((end[i]-start[i])**2 for i in range(3))**.5
                pieces.append(dict(type='line',start=start,end=end,tangent=tuple((end[i]-start[i])/length for i in range(3))))
            profiles=env['_spatial_kickplate_profiles'](pieces,direction)
            self.assertEqual(len(profiles),len(points))
            for point,profile in zip(points,profiles):
                self.assertAlmostEqual(profile[0][2],point[2]+10)
                self.assertAlmostEqual(profile[2][2]-profile[0][2],130)
            elements=[]
            builder=SimpleNamespace(dgn_model=1,add=elements.append)
            env['_add_kickplate'](builder,None,1,pieces,direction,None,spatial_polyline=True)
            self.assertEqual(len(elements),len(pieces))
            # 后段放样必须复用上一段末端截面。
            for a,b in zip(elements,elements[1:]): self.assertIs(a[1],b[0])
        env['_primitive_to_element']=lambda *args:None
        with self.assertRaisesRegex(RuntimeError,'第1/'):
            env['_add_kickplate'](builder,None,1,pieces,direction,None,spatial_polyline=True)

    def test_bentley_tk_input_queue_pump(self):
        source=Path(__file__).with_name('spiral_stair.py')
        tree=ast.parse(source.read_text(encoding='utf-8-sig'))
        node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='_MicroStationTk')
        calls=[]
        class FakeTk:
            def __init__(self): self.updates=0
            def update(self): self.updates+=1; calls.append('tk')
            def winfo_id(self): return self.updates
        queue=SimpleNamespace(AttachTkinterToolSetting=lambda handle:calls.append('attach'),
                              PythonMainLoop=lambda:calls.append('bentley'))
        env=dict(tk=SimpleNamespace(Tk=FakeTk,TclError=RuntimeError),
                 win32gui=SimpleNamespace(IsWindow=lambda handle:handle<3,GetParent=lambda handle:100),
                 PyCadInputQueue=queue)
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),env)
        window=env['_MicroStationTk']()
        window.microstation_mainloop()
        self.assertEqual(calls,['tk','attach','bentley','tk','bentley','tk'])

    def test_placement_event_and_cleanup_only_once(self):
        source=Path(__file__).with_name('spiral_stair.py')
        tree=ast.parse(source.read_text(encoding='utf-8-sig'))
        node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='PlacementTool')
        calls=[]
        class Base:
            def __init__(self,*args): pass
            def _OnPostInstall(self): calls.append('post_install')
            def _ExitTool(self): calls.append('exit')
        log=SimpleNamespace(write=lambda level,text:calls.append(text),close=lambda:calls.append('close'))
        def generate(point,parameters,logger,**kwargs):
            calls.append('generate')
            return dict(flights=[1,2]),dict(guide_count=107)
        env=dict(DgnPrimitiveTool=Base,AccuSnap=SimpleNamespace(GetInstance=lambda:SimpleNamespace(EnableSnap=lambda value:None)),
                 NotificationManager=SimpleNamespace(OutputPrompt=lambda msg:None),generate=generate)
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),env)
        tool=env['PlacementTool'](Parameters(),log,lambda:calls.append('finished'))
        tool._OnPostInstall()
        tool._OnDataButton(SimpleNamespace(GetPoint=lambda:SimpleNamespace(x=1,y=2,z=3)))
        tool._OnCleanup()
        self.assertIn('generate',calls)
        self.assertTrue(any('已收到模型点取事件' in c for c in calls))
        self.assertEqual(calls.count('close'),1)
        self.assertEqual(calls.count('finished'),1)

    def test_reported_kickplate_gap_and_shared_vertex_fix(self):
        source=Path(__file__).resolve().parents[1]/'普通钢结构围栏'/'steel_handrail.py'
        tree=ast.parse(source.read_text(encoding='utf-8-sig'))
        names={'_horizontal_unit','_horizontal_normal','_offset_spatial_polyline_pieces','_offset_kickplate_pieces'}
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
        env=dict(hypot=math.hypot,cos=math.cos,sin=math.sin,
                 PATH_TOLERANCE_MM=.01,KICKPLATE_THICKNESS=6.,CORNER_RADIUS=140.)
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),env)
        for interval in (10000,5000):
            for direction in (1,-1):
                points=build_layout(Parameters(wall_gap=150,landing_interval=interval,direction=direction))['rail']
                pieces=[]
                for start,end in zip(points,points[1:]):
                    length=sum((end[i]-start[i])**2 for i in range(3))**.5
                    pieces.append(dict(type='line',start=start,end=end,tangent=tuple((end[i]-start[i])/length for i in range(3))))
                # 原实现能重现用户的约0.704mm路径接缝。
                with self.assertRaisesRegex(RuntimeError,'不连续'):
                    env['_offset_kickplate_pieces'](pieces,direction,37.15)
                fixed=env['_offset_kickplate_pieces'](pieces,direction,37.15,spatial_polyline=True)
                for a,b in zip(fixed,fixed[1:]):
                    self.assertEqual(a['end'],b['start'])
                for original,new in zip(pieces,fixed):
                    self.assertEqual(original['start'][2],new['start'][2])
                    self.assertEqual(original['end'][2],new['end'][2])
                    # 共享顶点仍位于相应水平偏移直线上。
                    normal=env['_horizontal_normal'](original['tangent'],direction)
                    for key in ('start','end'):
                        distance=sum((new[key][i]-original[key][i])*normal[i] for i in (0,1))
                        self.assertAlmostEqual(distance,37.15,places=7)

    def test_real_rail_entry_accepts_local_tuples(self):
        source=Path(__file__).resolve().parents[1]/'普通钢结构围栏'/'steel_handrail.py'
        tree=ast.parse(source.read_text(encoding='utf-8-sig'))
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='build_continuous_handrail')
        model=SimpleNamespace(GetModelInfo=lambda:SimpleNamespace(GetUorPerMeter=lambda:1000))
        calls=[]
        class Builder:
            def __init__(self,model): self.cell='uncommitted'
            def build(self): calls.append('build')
        env=dict(ISessionMgr=SimpleNamespace(ActiveDgnModelRef=SimpleNamespace(GetDgnModel=lambda:model)),
                 _to_local_path=lambda vertices,scale:(vertices[0],[(0.,0.,0.),(100.,10.,80.),(200.,30.,160.)]),
                 _clean_and_validate_points=lambda points:points,
                 hypot=math.hypot, KNEE_RAIL_Z=560.,BALL_DIAMETER=76.,TOP_RAIL_Z=1017.,
                 PATH_TOLERANCE_MM=.01,TYPE2_STRUCTURE_OFFSET_DEFAULT=120.,
                 _build_post_stations=lambda station,corners:[0,station],
                 _merge_stations=lambda stations,total:sorted(set(stations)),
                 _HandrailCellBuilder=Builder,_element_color=lambda:None,
                 _add_rails=lambda *args:calls.append('rails'),
                 _add_posts_balls_and_brackets=lambda *args:calls.append('posts'),
                 _add_kickplate=lambda *args,**kwargs:calls.append('kickplate'))
        # 旧距离函数若再次被调用，应直接使测试失败。
        env['_distance3']=lambda a,b: self.fail('误用了DPoint3d距离函数')
        exec(compile(ast.Module(body=[function],type_ignores=[]),str(source),'exec'),env)
        progress=[]
        cell,result=env['build_continuous_handrail']([1,2,3],progress=progress.append)
        self.assertEqual(calls,['rails','posts','kickplate','build'])
        self.assertGreater(result['length_mm'],200)
        self.assertEqual(env['TOP_RAIL_Z'],1017.)
        self.assertTrue(any('踢脚板' in text for text in progress))
        def failure(*args): raise RuntimeError('模拟栏杆原生API失败')
        env['_add_rails']=failure
        with self.assertRaises(RuntimeError): env['build_continuous_handrail']([1,2,3])
        self.assertEqual(env['TOP_RAIL_Z'],1017.)

    def test_log_captures_exact_stage_and_traceback(self):
        with tempfile.TemporaryDirectory() as folder:
            log=GenerationLog(directory=folder)
            with self.assertRaises(ValueError):
                with log.stage('总体建模'):
                    with log.stage('梯段3 外侧板放样'):
                        raise ValueError('模拟截面错误')
            self.assertEqual(log.failed_stage,'梯段3 外侧板放样')
            log.close()
            self.assertTrue(Path(log.path).read_bytes().startswith(b'\xef\xbb\xbf'))
            text=Path(log.path).read_text(encoding='utf-8')
            self.assertIn('Traceback',text)
            self.assertIn('模拟截面错误',text)
            self.assertEqual(text.count('Traceback'),1)

if __name__=='__main__': unittest.main()
