import unittest
from collections import namedtuple
from ..reconstruction.Snap_To_Boundary import Snap_To_Boundary

class TestReconstructionSnapToBoundary(unittest.TestCase):
    def setUp(self):
        origin = [0, 2]
        width = 4
        height = 4
        self.snapper = Snap_To_Boundary(origin, width, height)

    def test_is_outside(self):
        # Start point inside the network should be rejected.
        self.assertEqual(self.snapper.execute([1, 3], [5, 3]), None)

        # End point inside the network should be rejected.
        self.assertEqual(self.snapper.execute([-1, 5], [3, 3]), None)

        # Both start and end point inside the network should be rejected.
        self.assertEqual(self.snapper.execute([1, 3], [3, 3]), None)

        # Both start and end point outside the network should be fine.
        self.assertNotEqual(self.snapper.execute([-1, 5], [5, 3]), None)

    def test_is_intersecting(self):
        # Lines that do not intersect any boundary should be rejected.
        self.assertEqual(self.snapper.execute([2, 0], [5, 2]), None)

        # Lines that intersect at least one boundary should be fine.
        self.assertNotEqual(self.snapper.execute([2, 1], [5, 3]), None)

    def test_execute(self):
        Point = namedtuple('Point', 'x y')

        # Left and right boundary, decreasing line (negative delta y).
        expected = [Point(0, 14/3.0), Point(4, 10/3.0)]
        self.assertEqual(self.snapper.execute([-1, 5], [5, 3]), expected)

        # Left and right boundary, increasing line (positive delta y).
        expected = [Point(0, 31/6.0), Point(4, 35/6.0)]
        self.assertEqual(self.snapper.execute([-1, 5], [5, 6]), expected)

        # Top and bottom boundary, decreasing line (negative delta y).
        expected = [Point(1/3.0, 2), Point(5/3.0, 6)]
        self.assertEqual(self.snapper.execute([0, 1], [2, 7]), expected)

        # Top and bottom boundary, increasing line (positive delta y).
        expected = [Point(17/6.0, 2), Point(13/6.0, 6)]
        self.assertEqual(self.snapper.execute([3, 1], [2, 7]), expected)
