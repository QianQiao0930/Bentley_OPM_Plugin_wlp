import os
import sys
import unittest

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_LOGIC_DIR = os.path.join(os.path.dirname(_TEST_DIR), '竖直弯头的竖直耳轴')
if _LOGIC_DIR not in sys.path:
    sys.path.insert(0, _LOGIC_DIR)

from elbow_selection_logic import (
    f4_alignment_offset, f4_end_plate_thickness,
    f5_axis_points, f5_azimuth_deg, f5_number, f5_placement_direction,
    horizontal_elbow_frame_from_matrix,
)


class F5LogicTests(unittest.TestCase):
    def test_horizontal_90_degree_elbow_and_both_alignments(self):
        # Run 端朝西，Outlet 端朝北；耳轴向东延伸。
        matrix = (1, 0, 0, 0,
                  0, 0, 1, 0,
                  0, -1, 0, 0)
        frame = horizontal_elbow_frame_from_matrix(matrix, 1000, 300, 300)
        self.assertEqual((1.0, 0.0, 0.0), frame['axis_x'])
        self.assertEqual(90.0, f5_azimuth_deg(frame['axis_x']))
        self.assertEqual((300.0, 300.0, 0.0), frame['outlet_port_mm'])
        centered = f5_axis_points(frame, 700, 6)
        bottom_offset = f4_alignment_offset(406.4, 219.1, 'BOTTOM')
        bottom = f5_axis_points(frame, 700, 6, bottom_offset)
        # 拉伸轴落在 Run 轴上，起点进入弯头，不能落在 Outlet 端面。
        self.assertEqual((300.0, 0.0, 0.0), centered['origin_mm'])
        self.assertEqual((1.0, 0.0, 0.0), centered['tube_start_mm'])
        self.assertEqual((1000.0, 0.0, 0.0), centered['outer_end_mm'])
        self.assertNotEqual(frame['outlet_port_mm'], centered['origin_mm'])
        opposite = f5_axis_points(frame, 700, 6, 0, 'OUTLET')
        self.assertEqual((0.0, -1.0, 0.0),
                         f5_placement_direction(frame, 'OUTLET'))
        self.assertEqual((300.0, 299.0, 0.0), opposite['tube_start_mm'])
        self.assertEqual((300.0, -700.0, 0.0), opposite['outer_end_mm'])
        self.assertEqual((300.0, 0.0, 0.0), opposite['origin_mm'])
        self.assertEqual(180.0,
                         f5_azimuth_deg(f5_placement_direction(frame, 'OUTLET')))
        self.assertAlmostEqual(-93.65, bottom['origin_mm'][2])
        self.assertAlmostEqual(-93.65, bottom['tube_start_mm'][2])
        self.assertAlmostEqual(-93.65, bottom['outer_end_mm'][2])
        opposite_bottom = f5_axis_points(frame, 700, 6, bottom_offset,
                                         'OUTLET')
        self.assertAlmostEqual(-93.65, opposite_bottom['tube_start_mm'][2])
        self.assertEqual(6.0, f4_end_plate_thickness(200, 'A'))
        self.assertEqual(12.0, f4_end_plate_thickness(200, 'B'))
        self.assertEqual(0.0, f4_end_plate_thickness(200, 'C'))

    def test_azimuth_and_number(self):
        for direction, expected in (((0, 1, 0), 0), ((1, 0, 0), 90),
                                    ((0, -1, 0), 180), ((-1, 0, 0), 270)):
            self.assertEqual(expected, f5_azimuth_deg(direction))
        self.assertEqual('F5-DN400-DN200-C1-700-A-90',
                         f5_number(400, 200, 8.18, 8.18, 'C1', 700,
                                   'A', 90))
        self.assertEqual('F5-DN400-DN200(10)-C1-700-B-90-FB',
                         f5_number(400, 200, 10, 8.18, 'C1', 700,
                                   'B', 90, True))
        self.assertEqual('F5-DN400-DN200-C1-700-C-0',
                         f5_number(400, 200, 8.18, 8.18, 'C1', 700,
                                   'C', 359.9))

    def test_vertical_elbow_is_rejected(self):
        matrix = (1, 0, 0, 0,
                  0, 1, 0, 0,
                  0, 0, 1, 0)
        with self.assertRaisesRegex(ValueError, '不是水平弯头'):
            horizontal_elbow_frame_from_matrix(matrix, 1000, 300, 300)


if __name__ == '__main__':
    unittest.main()
