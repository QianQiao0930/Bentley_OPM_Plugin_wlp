import unittest
from math import hypot
from upright_beams import build_u_profiles
from spiral_geometry import Parameters,build_layout,build_guides

class UprightBeamTests(unittest.TestCase):
    def test_vertical_center_and_back_to_back(self):
        for direction in (1,-1):
            guides=build_guides(build_layout(Parameters(landing_interval=5000,direction=direction),auxiliary_only=True))
            for side,guide in zip(('inner','outer'),guides[:2]):
                profiles=build_u_profiles(guide['points'],side,return_start=guide.get('return_start'))
                self.assertEqual(len(profiles),len(guide['points']))
                for index,(path,profile) in enumerate(zip(guide['points'],profiles)):
                    x,y,z=path
                    # 腹板底部外角严格落在路径上。
                    for axis in range(3): self.assertAlmostEqual(profile[7][axis],path[axis])
                    self.assertAlmostEqual(max(p[2] for p in profile)-min(p[2] for p in profile),200)
                    self.assertAlmostEqual(profile[0][2],z+200)
                    self.assertAlmostEqual(profile[7][2],z)
                    # 两翼尖之间方向纯竖直，不能随坡度侧倾。
                    self.assertEqual(profile[1][:2],profile[6][:2])
                    if guide.get('return_start') is not None and index>=guide['return_start']:
                        self.assertGreater(hypot(profile[1][0]-x,profile[1][1]-y),0)
                        continue
                    self.assertAlmostEqual(hypot(profile[1][0]-x,profile[1][1]-y),100)
                    self.assertAlmostEqual(hypot(profile[3][0]-x,profile[3][1]-y),6)
                    self.assertAlmostEqual(profile[1][2]-profile[2][2],6)
                    radial_dot=((profile[1][0]-x)*x+(profile[1][1]-y)*y)/hypot(x,y)
                    self.assertAlmostEqual(radial_dot,-100 if side=='inner' else 100)
                    # 整个截面位于径向-Z平面。
                    for px,py,pz in profile: self.assertAlmostEqual((px-x)*y-(py-y)*x,0,places=6)

    def test_invalid(self):
        for kwargs in (dict(side='bad'),dict(side='inner',thickness=0),dict(side='outer',height=10)):
            with self.assertRaises(ValueError): build_u_profiles([(100,0,0)],**kwargs)
        with self.assertRaises(ValueError): build_u_profiles([(0,0,0)],'inner')

    def test_top_cross_beam_opens_away_from_platform(self):
        for direction in (1,-1):
            layout=build_layout(Parameters(direction=direction),auxiliary_only=True)
            guide=build_guides(layout)[1]
            points=guide['points']
            profiles=build_u_profiles(points,'outer',return_start=guide['return_start'])
            incoming=[points[-2][i]-points[-3][i] for i in (0,1)]
            tip=profiles[-1][1]
            base=profiles[-1][0]
            opening=[tip[i]-base[i] for i in (0,1)]
            self.assertGreater(sum(opening[i]*incoming[i] for i in (0,1)),0)
            return_tangent=[points[-1][i]-points[-2][i] for i in (0,1)]
            self.assertAlmostEqual(sum(opening[i]*return_tangent[i] for i in (0,1)),0,places=6)

if __name__=='__main__': unittest.main()
