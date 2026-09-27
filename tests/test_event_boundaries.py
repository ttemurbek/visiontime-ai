"""Regression checks for event timing and image-plane motion rules."""
import unittest

import numpy as np

import solution


class EventBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.frame = np.zeros((100, 200, 3), dtype=np.uint8)

    def analyzer(self):
        analyzer = solution.Analyzer(200, 100)
        analyzer.scene.cfg = {"road_polygon": [[.5, 0], [1, 0], [1, 1], [.5, 1]]}
        return analyzer

    @staticmethod
    def detection(x, name="person", class_id=0):
        return solution.Detection((x - 10, 20, x + 10, 60), class_id, name, .9)

    def test_line_extension_is_not_a_marking_crossing(self):
        self.assertFalse(solution._crosses((0, 20), (10, 20), ((5, 0), (5, 10))))
        self.assertTrue(solution._crosses((0, 5), (10, 5), ((5, 0), (5, 10))))

    def test_jaywalking_starts_at_road_entry_not_track_birth(self):
        analyzer = self.analyzer()
        for index in range(16):
            analyzer.process(self.frame, index * .2, [self.detection(40 + 6 * index)])
        events = analyzer.finish(3.2)
        walking = [event for event in events if event[2] == "jaywalking"]
        self.assertEqual(len(walking), 1)
        self.assertAlmostEqual(walking[0][0], 2.0)

    def test_debounce_gap_does_not_extend_event_end(self):
        analyzer = self.analyzer()
        analyzer.sample_interval = .2
        for timestamp in (4.0, 4.2, 4.4):
            analyzer._update_events(timestamp, [("jaywalking", "p:1", timestamp)])
        analyzer._update_events(5.1, [])
        events = analyzer.finish(20)
        self.assertEqual(len(events), 1)
        self.assertAlmostEqual(events[0][0], 4.0)
        self.assertAlmostEqual(events[0][1], 4.6)

    def test_obstacle_does_not_start_before_it_stops_on_road(self):
        analyzer = self.analyzer()
        analyzer.scene.cfg["obstacle_class_names"] = ["chair"]
        for index in range(61):
            timestamp = index * .2
            x = 40 if timestamp <= 4 else min(120, 40 + (timestamp - 4) * 40)
            analyzer.process(self.frame, timestamp, [self.detection(x, "chair", 56)])
        events = analyzer.finish(12.2)
        obstacles = [event for event in events if event[2] == "road_obstacle"]
        self.assertEqual(len(obstacles), 1)
        self.assertGreaterEqual(obstacles[0][0], 6.0)
        self.assertLess(obstacles[0][0], 7.0)

    def test_ttc_requires_approach_and_observation_history(self):
        analyzer = self.analyzer()
        scores = []
        for index in range(12):
            detections = [self.detection(30 + 2 * index, "car", 2),
                          self.detection(170 - 2 * index, "car", 2)]
            scores.append(analyzer.process(self.frame, index * .2, detections))
        self.assertEqual(scores[0], .01)
        self.assertGreater(scores[-1], .1)
        away = self.analyzer()
        for index in range(10):
            score = away.process(self.frame, index * .2,
                                 [self.detection(60 - 2 * index, "car", 2),
                                  self.detection(140 + 2 * index, "car", 2)])
        self.assertEqual(score, .01)


if __name__ == "__main__":
    unittest.main()
