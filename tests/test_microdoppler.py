import unittest

import numpy as np

from lidar_cave_scan.microdoppler import analyze, make_synthetic_demo


class MicroDopplerTests(unittest.TestCase):
    def test_synthetic_demo_recovers_frequency_and_rms(self):
        times, samples, reference, wavelength, _ = make_synthetic_demo()
        metrics, _, _, _, _ = analyze(samples, times, wavelength, reference)
        self.assertAlmostEqual(metrics["frequency_hz"], 1.25, delta=0.051)
        self.assertAlmostEqual(metrics["los_displacement_rms_mm"], 2 / np.sqrt(2), delta=0.05)
        self.assertEqual(metrics["status"], "experimental_unvalidated")

    def test_bad_timing_is_rejected(self):
        times, samples, reference, wavelength, _ = make_synthetic_demo()
        times[3] = times[2]
        with self.assertRaises(ValueError):
            analyze(samples, times, wavelength, reference)

    def test_short_series_is_rejected(self):
        with self.assertRaises(ValueError):
            analyze(np.ones(4, dtype=complex), np.arange(4), 0.03)


if __name__ == "__main__":
    unittest.main()
