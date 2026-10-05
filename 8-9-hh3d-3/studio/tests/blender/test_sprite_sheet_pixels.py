"""Reject the observed quad overlap and wrong atlas order without an engine."""
import unittest
from tests.blender.sprite_sheet_pixels import inspect_pixels


def pixels():
    result = [0.0] * (128 * 128 * 4)
    for color, (x0, y0) in zip(((0.9, 0.1, 0.1, 1), (0.1, 0.9, 0.1, 1),
                              (0.1, 0.2, 0.9, 1), (0.9, 0.8, 0.1, 1)),
                             ((0, 64), (64, 64), (0, 0), (64, 0))):
        for y in range(y0 + 3, y0 + 61):
            for x in range(x0 + 3, x0 + 61):
                result[(y * 128 + x) * 4:(y * 128 + x) * 4 + 4] = color
    return result


class SpriteSheetPixelsTests(unittest.TestCase):
    def test_color_cells_and_transparent_gutters(self):
        result = inspect_pixels(128, 128, pixels())
        self.assertTrue(result['passed'])
        self.assertEqual(result['cell_inner_pixels'], [2304] * 4)

    def test_original_quad_overlap_rejected(self):
        image = pixels()
        for y in range(32, 96):
            for x in range(32, 96):
                image[(y * 128 + x) * 4:(y * 128 + x) * 4 + 4] = (0.5, 0.5, 0.5, 1)
        result = inspect_pixels(128, 128, image)
        self.assertFalse(result['passed'])
        self.assertEqual(result['failures'], ['cell:0', 'cell:1', 'cell:2', 'cell:3', 'cell_gutters'])

    def test_missing_swapped_and_nonfinite_pixels_rejected(self):
        for replacement in ((0, 0, 0, 0), (0.1, 0.9, 0.1, 1), (float('nan'), 0, 0, 1)):
            with self.subTest(replacement=replacement):
                image = pixels()
                offset = (96 * 128 + 32) * 4
                image[offset:offset + 4] = replacement
                self.assertFalse(inspect_pixels(128, 128, image)['passed'])


if __name__ == '__main__':
    unittest.main()
