# -*- coding: utf-8 -*-
"""离线验证配方和导出错误处理。模拟 CEL 接口不代表宿主验证。"""
import importlib
import json
import math
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from huahai_geometry import SPECS, build_recipe, box_frame, distance, point_and_vector, normalize_capacity


class DimensionsTest(unittest.TestCase):
    def test_all_variant_dimensions(self):
        expected = {'2':(110,360),'4':(130,485),'5':(140,535),'6':(150,575),'8':(160,605)}
        for key, (diameter, height) in expected.items():
            with self.subTest(capacity=key):
                recipe = build_recipe(key)
                bottle = next(p for p in recipe['parts'] if p['kind']=='rounded_bottle')
                self.assertEqual(bottle['radius']*2, diameter)
                lever = next(p for p in recipe['parts'] if p['name']=='upper_squeeze_lever')
                base, top, x, y = box_frame(lever)
                vertices = [tuple(origin[i]+dx*x[i]+dy*y[i] for i in range(3))
                            for origin in (base,top)
                            for dx in (0,lever['size'][0]) for dy in (0,lever['size'][1])]
                self.assertAlmostEqual(max(v[2] for v in vertices),height,places=8)
                foot = next(p for p in recipe['parts'] if p['name']=='black_base_foot')
                self.assertEqual(foot['start'][2],0)

    def test_discharge_and_hose(self):
        for key in SPECS:
            recipe = build_recipe(key)
            hoses = [p for p in recipe['parts'] if p['kind']=='hose']
            if key=='2':
                self.assertFalse(hoses)
                self.assertTrue(any(p['name']=='direct_discharge_nozzle_2kg' for p in recipe['parts']))
            else:
                self.assertEqual(len(hoses),1)
                self.assertAlmostEqual(recipe['hose_length'],400,places=7)
                self.assertEqual(hoses[0]['radius'],9)
                self.assertTrue(all(distance(a,b)>1e-6 for a,b in zip(hoses[0]['points'],hoses[0]['points'][1:])))
                # 管口与最低软管点都高于地面。
                nozzle = next(p for p in recipe['parts'] if p['name']=='flared_discharge_nozzle')
                self.assertGreater(nozzle['start'][2],0)
                self.assertLess(max(p[2] for p in hoses[0]['points'])+9,recipe['spec']['total_height'])

    def test_units_rotation_and_translation(self):
        for uor_per_mm in (1,1000,10000):
            point, vector = point_and_vector((50,60,70),90,uor_per_mm)
            result = point((130,0,485))
            self.assertAlmostEqual(result[0],50)
            self.assertAlmostEqual(result[1],60+130*uor_per_mm)
            self.assertAlmostEqual(result[2],70+485*uor_per_mm)
            self.assertAlmostEqual(vector((130,0,0))[1],130*uor_per_mm)
        for invalid in (float('nan'),float('inf')):
            with self.assertRaises(ValueError):
                point_and_vector((0,0,0),invalid,1)
        with self.assertRaises(ValueError):
            point_and_vector((0,0,0),0,0)

    def test_selection(self):
        self.assertEqual(normalize_capacity('4公斤'),'4')
        self.assertEqual(normalize_capacity(' 8 KG '),'8')
        for value in ('3',None,'4.5',''):
            with self.assertRaises(ValueError):
                normalize_capacity(value)


class ExportFailureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 只模拟库状态和异常路径，不模拟实体建模。
        cls.saved = {name:sys.modules.get(name) for name in
                     ('MSPyBentley','MSPyBentleyGeom','MSPyDgnPlatform','MSPyDgnView','MSPyMstnPlatform')}
        for name in cls.saved:
            sys.modules[name] = types.ModuleType(name)
        sys.modules['MSPyDgnView'].DgnPrimitiveTool = type('DgnPrimitiveTool',(),{})
        cls.backend = importlib.import_module('huahai_bentley')

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop('huahai_bentley',None)
        for name,value in cls.saved.items():
            if value is None:
                sys.modules.pop(name,None)
            else:
                sys.modules[name] = value

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.seed = self.directory/'seed3d.dgn'
        self.seed.write_bytes(b'FAKE-SEED-FOR-OFFLINE-TEST-ONLY')
        self.target = self.directory/'result.cel'
        self.attached = 'prior.cel'
        self.names = set()
        self.add_status = 0
        self.save_status = 0
        owner = self

        class FileName:
            def __init__(self,value=''):
                self.value = value
            def __str__(self):
                return self.value

        class CellApi:
            @staticmethod
            def GetLibraryName(out):
                out.value = owner.attached
            @staticmethod
            def AttachLibrary(out,path,default,flag):
                owner.attached = str(path) if path is not None else ''
                return 0
            @staticmethod
            def AddLibDescr(descriptor,kind,nested):
                owner.names.add(descriptor)
                return owner.add_status
            @staticmethod
            def ExistsInLibrary(name):
                return name in owner.names
            @staticmethod
            def GetLibraryObject(path,unused):
                return 0,types.SimpleNamespace(ProcessChanges=lambda reason:owner.save_status)

        replacements = dict(active_model=lambda:object(),BeFileName=FileName,Cell=CellApi,
            BentleyStatus=types.SimpleNamespace(eSUCCESS=0),
            DgnSaveReason=types.SimpleNamespace(eUserInitiated=1),
            CellAddType=types.SimpleNamespace(NormalCell=0),DPoint3d=lambda *args:args,
            build_cell=lambda key,*args:types.SimpleNamespace(GetElementDescr=lambda:'HUAHAI_MF_ABCE'+key))
        self.patcher = patch.multiple(self.backend,create=True,**replacements)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    def test_success_restores_library(self):
        output = self.backend.export_cell_library(self.target,seed_path=self.seed)
        self.assertEqual(output,str(self.target.resolve()))
        self.assertEqual(self.attached,'prior.cel')
        self.assertEqual(self.names,{'HUAHAI_MF_ABCE'+k for k in SPECS})
        self.assertTrue(self.target.exists())
        self.assertFalse(list(self.directory.glob('*.partial.cel')))

    def test_add_failure_keeps_final_file_absent(self):
        self.add_status = 8
        with self.assertRaises(RuntimeError):
            self.backend.export_cell_library(self.target,seed_path=self.seed)
        self.assertEqual(self.attached,'prior.cel')
        self.assertFalse(self.target.exists())
        self.assertEqual(len(list(self.directory.glob('*.partial.cel'))),1)

    def test_save_failure_restores_no_previous_library(self):
        self.attached = ''
        self.save_status = 7
        with self.assertRaises(RuntimeError):
            self.backend.export_cell_library(self.target,seed_path=self.seed)
        self.assertEqual(self.attached,'')
        self.assertFalse(self.target.exists())

    def test_existing_file_remains_untouched(self):
        self.target.write_bytes(b'existing-library')
        with self.assertRaises(FileExistsError):
            self.backend.export_cell_library(self.target,seed_path=self.seed)
        self.assertEqual(self.target.read_bytes(),b'existing-library')
        self.assertEqual(self.attached,'prior.cel')

    def test_bad_extension_and_seed(self):
        with self.assertRaises(ValueError):
            self.backend.export_cell_library(self.directory/'wrong.step',seed_path=self.seed)
        with self.assertRaises(FileNotFoundError):
            self.backend.export_cell_library(self.target,seed_path=self.directory/'missing.dgn')
        self.assertFalse(self.target.exists())
        self.assertEqual(self.attached,'prior.cel')


if __name__=='__main__':
    unittest.main(verbosity=2)
