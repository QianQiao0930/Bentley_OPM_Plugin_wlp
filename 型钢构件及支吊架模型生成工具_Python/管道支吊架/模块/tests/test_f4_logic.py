import os
import sys
import unittest

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_LOGIC_DIR = os.path.join(os.path.dirname(_TEST_DIR), '竖直弯头的竖直耳轴')
if _LOGIC_DIR not in sys.path:
    sys.path.insert(0, _LOGIC_DIR)

from elbow_selection_logic import (
    elbow_frame_from_matrix, f4_alignment_offset, f4_axis_points,
    f4_end_plate_thickness, f4_pipe_axis_origin,
    f4_number,
)


class F4LogicTests(unittest.TestCase):
    def test_fb1_and_fb2_share_horizontal_ear_axis(self):
        up = (1, 0, 0, 0,
              0, 1, 0, 0,
              0, 0, 1, 0)
        down = (1, 0, 0, 0,
                0, -1, 0, 0,
                0, 0, -1, 0)
        for matrix, code in ((up, 'FB1'), (down, 'FB2')):
            frame = elbow_frame_from_matrix(matrix, 1000, 300, 300,
                                            allow_downward=True)
            self.assertEqual(code, frame['flat_bend_code'])
            self.assertEqual((1.0, 0.0, 0.0), frame['horizontal_direction'])
            points = f4_axis_points(frame, 500, 12)
            self.assertEqual(0.0, points['origin_mm'][2])
            self.assertAlmostEqual(1.0,
                                   (points['tube_start_mm'][0]
                                    - frame['horizontal_port_mm'][0]))
            self.assertAlmostEqual(488.0,
                                   points['tube_end_mm'][0]
                                   - points['origin_mm'][0])
            self.assertAlmostEqual(500.0,
                                   points['outer_end_mm'][0]
                                   - points['origin_mm'][0])
        with self.assertRaisesRegex(ValueError, '竖直端朝下'):
            elbow_frame_from_matrix(down, 1000, 300, 300)

    def test_end_plate_types_and_number(self):
        self.assertEqual(6, f4_end_plate_thickness(200, 'A'))
        self.assertEqual(12, f4_end_plate_thickness(200, 'B'))
        self.assertEqual(25, f4_end_plate_thickness(500, 'B'))
        self.assertEqual(30, f4_end_plate_thickness(650, 'B'))
        self.assertEqual(0, f4_end_plate_thickness(200, 'C'))
        self.assertEqual('F4-16"-8"-C1-500-A-FB1',
                         f4_number(400, 200, 8.18, 8.18, 'C1', 500,
                                   'A', 'FB1'))
        self.assertEqual('F4-16"-8"(10)-C1-500-B-FB2',
                         f4_number(400, 200, 10, 8.18, 'C1', 500,
                                   'B', 'FB2'))
        self.assertEqual('F4-16"-8"-C1-500-A',
                         f4_number(400, 200, 8.18, 8.18, 'C1', 500, 'A'))

    def test_bottom_alignment_offset_matches_pipe_radii(self):
        frame = {'vertical_port_mm': (100.0, 200.0, 300.0),
                 'horizontal_port_mm': (0.0, 200.0, 50.0),
                 'horizontal_direction': (1.0, 0.0, 0.0)}
        self.assertEqual(0.0, f4_alignment_offset(406.4, 219.1, 'CENTER'))
        offset = f4_alignment_offset(406.4, 219.1, 'BOTTOM')
        self.assertAlmostEqual(93.65, offset)
        centered = f4_axis_points(frame, 500.0, 6.0)
        bottom = f4_axis_points(frame, 500.0, 6.0, offset)
        self.assertEqual((100.0, 200.0, 50.0), f4_pipe_axis_origin(frame))
        self.assertEqual(50.0, centered['origin_mm'][2])
        self.assertAlmostEqual(-43.65, bottom['origin_mm'][2])
        self.assertAlmostEqual(1.0, bottom['tube_start_mm'][0])
        self.assertAlmostEqual(-43.65, bottom['tube_start_mm'][2])
        self.assertAlmostEqual(593.0, bottom['tube_length_mm'])
        self.assertAlmostEqual(bottom['origin_mm'][2], bottom['tube_end_mm'][2])
        self.assertEqual(600.0, bottom['outer_end_mm'][0])

    def test_upward_elbow_uses_horizontal_pipe_elevation(self):
        matrix = (1, 0, 0, 25701337.283,
                  0, 1, 0, 15559196.881,
                  0, 0, 1, 0)
        frame = elbow_frame_from_matrix(matrix, 1000, 1067, 1067,
                                        allow_downward=True)
        self.assertAlmostEqual(1067.0, frame['vertical_port_mm'][2])
        self.assertAlmostEqual(0.0, f4_pipe_axis_origin(frame)[2])
        centered = f4_axis_points(frame, 1331, 6)
        bottom = f4_axis_points(frame, 1331, 6,
                                f4_alignment_offset(711, 355.6, 'BOTTOM'))
        self.assertAlmostEqual(0.0, centered['origin_mm'][2])
        self.assertAlmostEqual(-177.7, bottom['origin_mm'][2])
        self.assertAlmostEqual(frame['horizontal_port_mm'][0] + 1.0,
                               centered['tube_start_mm'][0])
        self.assertAlmostEqual(frame['vertical_port_mm'][0] + 1331.0 - 6.0,
                               centered['tube_end_mm'][0])


if __name__ == '__main__':
    unittest.main()
