import unittest
from math import degrees
from spiral_geometry import Parameters, build_layout, build_guides, build_z_tread_parts, build_platform_parts
from upright_beams import build_u_profiles

class GeometryTests(unittest.TestCase):
    def test_default(self):
        g=build_layout()
        self.assertEqual(g['counts'],[50,50])
        self.assertAlmostEqual(g['step_angle'],250/10100)
        self.assertEqual(g['inner_radius'],10100)
        self.assertEqual(g['outer_radius'],10800)
        self.assertAlmostEqual(g['flight_angle'],100*250/10100)
        self.assertAlmostEqual(g['slope'],38.659808254)
        self.assertEqual(len(g['treads']),100)
        self.assertEqual(g['treads'][49]['z'],10000)
        self.assertEqual(g['treads'][-1]['z'],20000)
        self.assertEqual(len(g['channels']),4)
        self.assertFalse(g['checks']['structural_width_pass'])
        for t in g['treads']:
            self.assertTrue(all(abs(p[2]-(t['z']-4))<1e-8 for p in t['corners']))
        self.assertEqual(g['rail'][0][2],0)
        self.assertEqual(g['rail'][-1][2],20000)
    def test_reverse_and_translation(self):
        g=build_layout(Parameters(direction=-1,start_z=1000,landing_z=11000,end_z=21000))
        self.assertEqual(g['treads'][0]['z'],1200)
        for t in g['treads']:
            xy=t['corners']
            area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(xy,xy[1:]+xy[:1]))
            self.assertGreater(area,0)
    def test_invalid(self):
        for params in (Parameters(riser=210),Parameters(landing_z=0),Parameters(clear_width=640),Parameters(tread_depth=100),Parameters(tank_diameter=float('nan'))):
            with self.assertRaises(ValueError): build_layout(params)

    def test_five_meter_landings(self):
        g=build_layout(Parameters(landing_interval=5000))
        self.assertEqual(g['landing_levels'],[5000,10000,15000])
        self.assertEqual(g['counts'],[25]*4)
        self.assertEqual(len(g['platforms']),4)
        self.assertEqual(len(g['channels']),8)
        self.assertNotIn('supports',g)
        self.assertAlmostEqual(g['flight_angle'],100*250/10100)
        for a,b in zip(g['rail'],g['rail'][1:]):
            self.assertGreater(sum((a[i]-b[i])**2 for i in range(3)),0)
        for index in range(3):
            self.assertEqual(g['flights'][index][3],g['flights'][index+1][2])
            self.assertAlmostEqual(g['flights'][index+1][0]-g['flights'][index][1],1000/10100)

    def test_partial_last_flight_and_no_landing(self):
        g=build_layout(Parameters(start_z=1000,end_z=18000,landing_interval=5000))
        self.assertEqual(g['landing_levels'],[6000,11000,16000])
        self.assertEqual(g['counts'],[25,25,25,10])
        g=build_layout(Parameters(landing_interval=30000))
        self.assertEqual(g['counts'],[100])
        self.assertEqual(g['landing_levels'],[])
        self.assertEqual(len(g['platforms']),1)

    def test_invalid_interval(self):
        for interval in (0,-1,5100):
            with self.assertRaises(ValueError): build_layout(Parameters(landing_interval=interval))

    def test_auxiliary_only_layout(self):
        for interval,count in ((10000,107),(5000,109)):
            g=build_layout(Parameters(landing_interval=interval),auxiliary_only=True)
            self.assertEqual(g['channels'],[])
            self.assertNotIn('supports',g)
            guides=build_guides(g)
            self.assertEqual(len(guides),count)
            for line in guides:
                if '轮廓' in line['name'] or '边界' in line['name']:
                    self.assertEqual(line['points'][0],line['points'][-1])
                    self.assertEqual(len(set(p[2] for p in line['points'])),1)
            self.assertEqual(guides[-1]['points'],[(0,0,0),(0,0,20000)])
            for side,original,raised in zip(('inner','outer'),guides[:2],guides[2:4]):
                self.assertTrue(raised['standalone'])
                profiles=build_u_profiles(original['points'],side,return_start=original.get('return_start'))
                self.assertEqual(raised['points'],[profile[1] for profile in profiles])
                self.assertAlmostEqual(sum(v*v for v in raised['points'][0][:2])**.5,
                                       g['inner_radius']-100 if side=='inner' else g['outer_radius']+100)
                self.assertTrue(all(b[2]==a[2]+200 for a,b in zip(original['points'],raised['points'])))
            for path in guides[:2]:
                self.assertTrue(path['standalone'])
                self.assertEqual(len(path['platform_segments']),len(g['platform_specs']))
                for a,b in path['platform_segments']:
                    self.assertEqual(b,a+1)
                    self.assertEqual(path['points'][a][2],path['points'][b][2])
                self.assertEqual(path['points'][0][2],0)
                self.assertEqual(path['points'][-1][2],20000)

    def test_z_tread_extents(self):
        for direction in (1,-1):
            layout=build_layout(Parameters(direction=direction),auxiliary_only=True)
            for tread in (layout['treads'][0],layout['treads'][-1]):
                parts=build_z_tread_parts(layout,tread)
                z=tread['z']
                self.assertEqual([p['thickness'] for p in parts],[4,40,44])
                self.assertEqual([p['corners'][0][2] for p in parts],[z-4,z-40,z-4])
                self.assertEqual([p['corners'][0][2]+p['thickness'] for p in parts],[z,z,z+40])
                self.assertIn('前长边',parts[1]['name'])
                self.assertIn('后长边',parts[2]['name'])
                for part in parts:
                    points=part['corners']
                    self.assertGreater(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1])),0)

    def test_platform_fold_and_top_return(self):
        for direction in (1,-1):
            layout=build_layout(Parameters(landing_interval=5000,direction=direction),auxiliary_only=True)
            for index,spec in enumerate(layout['platform_specs']):
                parts=build_platform_parts(layout,index)
                self.assertEqual(len(parts),1)
                self.assertEqual(parts[0]['thickness'],4)
                self.assertEqual(parts[0]['corners'][0][2],spec[2]+196)
                self.assertEqual(parts[0]['corners'][0][2]+parts[0]['thickness'],spec[2]+200)
            guides=build_guides(layout)
            self.assertEqual(guides[1]['points'][-1],guides[0]['points'][-1])
            # 横梁开口朝平台出口，栏杆末端随横梁腿尖偏移，不再强制与内梁腿尖重合。
            end=guides[3]['points'][-1]
            base=guides[1]['points'][-1]
            self.assertAlmostEqual(sum((end[i]-base[i])**2 for i in range(2))**.5,100)
            incoming=tuple(guides[1]['points'][-2][i]-guides[1]['points'][-3][i] for i in range(2))
            self.assertGreater(sum((end[i]-base[i])*incoming[i] for i in range(2)),0)
            outer=guides[1]['points']
            self.assertEqual(outer[-1][2],outer[-2][2])
            distance=sum((outer[-1][i]-outer[-2][i])**2 for i in range(3))**.5
            self.assertAlmostEqual(distance,700)
            self.assertEqual(guides[1]['return_start'],len(outer)-2)
            platform_guides=[g for g in guides if '平台' in g['name']]
            for guide,spec in zip(platform_guides,layout['platform_specs']):
                self.assertTrue(all(p[2]==spec[2]+200 for p in guide['points']))

if __name__=='__main__': unittest.main()
