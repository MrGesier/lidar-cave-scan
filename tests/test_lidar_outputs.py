import unittest

from lidar_cave_scan.lidar import priority_class, singularity_class


class LidarOutputTests(unittest.TestCase):
    def test_priority_classes(self):
        self.assertEqual(priority_class(80), "A - priorite terrain")
        self.assertEqual(priority_class(60), "B - interessant")
        self.assertEqual(priority_class(40), "C - controle rapide")
        self.assertEqual(priority_class(10), "D - faible signal")

    def test_singularity_classes(self):
        self.assertEqual(singularity_class(85), "S1 - anomalie forte")
        self.assertEqual(singularity_class(65), "S2 - anomalie nette")
        self.assertEqual(singularity_class(45), "S3 - signal discret")
        self.assertEqual(singularity_class(20), "S4 - bruit probable")


if __name__ == "__main__":
    unittest.main()
