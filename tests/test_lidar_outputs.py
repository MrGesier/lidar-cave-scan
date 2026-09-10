import unittest

from lidar_cave_scan.lidar import priority_class


class LidarOutputTests(unittest.TestCase):
    def test_priority_classes(self):
        self.assertEqual(priority_class(80), "A - priorite terrain")
        self.assertEqual(priority_class(60), "B - interessant")
        self.assertEqual(priority_class(40), "C - controle rapide")
        self.assertEqual(priority_class(10), "D - faible signal")


if __name__ == "__main__":
    unittest.main()
