import unittest
from unittest.mock import patch
import numpy as np
import solution

class GeometryTests(unittest.TestCase):
    def test_iou_is_one_for_identical_boxes(self):
        box = (10, 10, 30, 40)
        self.assertAlmostEqual(solution._iou(box, box), 1.0)

    def test_crossing_detected(self):
        line = ((5, 0), (5, 10))
        self.assertTrue(solution._crosses((0, 5), (10, 5), line))
        self.assertFalse(solution._crosses((0, 1), (3, 1), line))

    def test_official_class_ids_are_unique(self):
        self.assertEqual(len(solution.CLASSES), 14)
        self.assertEqual(len(solution.CLASSES), len(set(solution.CLASSES)))

class CausalInterfaceTests(unittest.TestCase):
    @patch("solution._detect", return_value=[])
    def test_risk_estimator_returns_bounded_scores(self, _detect):
        estimator = solution.RiskEstimator()
        estimator.reset({"fps":25,"width":64,"height":48,"n_frames":3,"video_id":"test.mp4"})
        frame = np.zeros((48, 64, 3), dtype=np.uint8)
        scores = [estimator.step(frame, i / 25) for i in range(3)]
        self.assertEqual(len(scores), 3)
        self.assertTrue(all(0 <= score <= 1 for score in scores))

    @patch("solution._detect", return_value=[])
    def test_empty_scene_has_no_events(self, _detect):
        analyzer = solution.Analyzer(64, 48)
        analyzer.process(np.zeros((48,64,3), dtype=np.uint8), 0, [])
        self.assertEqual(analyzer.finish(1), [])

if __name__ == "__main__":
    unittest.main()
