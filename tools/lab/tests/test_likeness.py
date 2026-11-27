"""Track H's comparison (likeness.py): the score of a picture against itself is 0, against a tinted copy the tint's
own difference, pictures of other sizes are refused and masked cells left out; the camera's place and field of view,
and the game's steps."""
from pathlib import Path
import math
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import likeness  # noqa: E402

from PIL import Image  # noqa: E402
import numpy as np  # noqa: E402


def flat(colour, size=(320, 180)):
    return Image.new('RGB', size, colour)


class Score(unittest.TestCase):
    def test_same_picture_scores_zero(self):
        rng = np.random.default_rng(7)
        picture = Image.fromarray(rng.integers(0, 255, (180, 320, 3), dtype=np.uint8))
        self.assertEqual(likeness.score_pair(picture, picture), {'dE': 0.0, 'L': 0.0, 'hue': 0.0})

    def test_tint_scores_its_own_difference(self):
        a, b = (120, 100, 80), (140, 100, 60)
        lab_a, keep = likeness.lab_cells(flat(a))
        lab_b, _ = likeness.lab_cells(flat(b))
        expected = float(np.linalg.norm(lab_a[0, 0] - lab_b[0, 0]))
        result = likeness.score_pair(flat(a), flat(b))
        self.assertAlmostEqual(result['dE'], expected, places=1)
        self.assertAlmostEqual(result['L'], abs(lab_a[0, 0, 0] - lab_b[0, 0, 0]), places=1)
        self.assertGreater(result['hue'], 10)

    def test_known_lab_value(self):
        lab, _ = likeness.lab_cells(flat((255, 255, 255)))
        self.assertAlmostEqual(lab[0, 0, 0], 100.0, places=1)
        self.assertAlmostEqual(abs(lab[0, 0, 1]) + abs(lab[0, 0, 2]), 0.0, places=1)

    def test_other_sizes_refused(self):
        with self.assertRaises(ValueError):
            likeness.score_pair(flat((1, 2, 3)), flat((1, 2, 3), (321, 180)))

    def test_masked_cells_left_out(self):
        a = flat((100, 100, 100))
        b = a.copy()
        b.paste((250, 20, 20), (0, 0, 80, 45))                 # the top left quarter of each side
        self.assertGreater(likeness.score_pair(a, b)['dE'], 1)
        self.assertEqual(likeness.score_pair(a, b, mask=[[0, 0, 0.32, 0.32]])['dE'], 0.0)   # the blur spreads it a little


class Camera(unittest.TestCase):
    def test_place_behind_the_target(self):
        shot = {'target': [100, 200, 0], 'yaw': 0, 'pitch': -45, 'distance': 1000}
        x, y, z = likeness.camera_place(shot)
        self.assertAlmostEqual(x, 100 - 1000 * math.cos(math.radians(45)), places=6)
        self.assertAlmostEqual(y, 200, places=6)
        self.assertAlmostEqual(z, 1000 * math.sin(math.radians(45)), places=6)
        x2, y2, _ = likeness.camera_place(shot, {'yawOffset': 90})
        self.assertAlmostEqual(x2, 100, places=6)
        self.assertLess(y2, 200)

    def test_field_of_view_across_the_width(self):
        self.assertAlmostEqual(likeness.vertical_fov(90, (1600, 900)), math.degrees(2 * math.atan(900 / 1600)))
        self.assertEqual(likeness.vertical_fov(50, (1600, 900), {'fovAcross': 'height'}), 50)

    def test_game_steps(self):
        steps = likeness.game_steps([{'id': 'x-1', 'target': [1, 2, 3], 'yaw': 45, 'pitch': -45, 'distance': 1800,
                                      'fov': 70}])
        self.assertEqual(steps[:2], ['console UIToggleVisibility', 'console ToggleFOW'])
        self.assertIn('console SetOverheadCameraParameters 70 1800 -45 | SetCameraYaw 45', steps)
        self.assertIn('console ViewLocation 1 2 3', steps)
        self.assertIn('shot x-1', steps)

    def test_shot_list_reads(self):
        plan = likeness.shot_list()
        self.assertEqual(len(likeness.cameras(plan)), 12)
        self.assertEqual(len({s['id'] for _, s in likeness.cameras(plan)}), 12)


if __name__ == '__main__':
    unittest.main()
