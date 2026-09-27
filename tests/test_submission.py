"""Submission contracts; model inference is mocked, accuracy is not assessed."""
from __future__ import annotations

import contextlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import cv2
import numpy as np

import evaluate
import run_submission
import solution


class SubmissionContractTests(unittest.TestCase):
    def test_only_official_class_ids_are_advertised(self):
        self.assertTrue(solution.CLASSES)
        self.assertEqual(len(solution.CLASSES), len(set(solution.CLASSES)))
        self.assertTrue(set(solution.CLASSES).issubset(evaluate.OFFICIAL_CLASSES))

    def test_official_harness_decodes_all_frames_and_writes_valid_output(self):
        """Exercise both entry points through the unmodified official harness."""
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "contract_fixture.mp4"
            output = Path(tmp) / "predictions.json"
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (64, 48))
            if not writer.isOpened():
                self.skipTest("OpenCV build has no MP4 writer")
            try:
                for i in range(20):
                    writer.write(np.full((48, 64, 3), i, dtype=np.uint8))
            finally:
                writer.release()
            args = ["run_submission.py", "--videos", str(video), "--out", str(output), "--team", "contract-test"]
            with patch.object(solution, "_detect", return_value=[]), \
                    patch.object(run_submission, "load_solution", return_value=solution), \
                    patch("sys.argv", args), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(run_submission.main(), 0)
            prediction = json.loads(output.read_text())
            errors, _ = evaluate.validate(prediction)
            self.assertEqual(errors, [])
            self.assertEqual(prediction["team"], "contract-test")
            self.assertEqual(prediction["log"][video.name]["errors"], [])
            entry = prediction["videos"][video.name]
            self.assertEqual(entry["events"], [])
            self.assertEqual(len(entry["risk"]), 20)
            self.assertEqual(entry["risk"][0][0], 0.0)
            self.assertEqual(entry["risk"][-1][0], 1.9)


class CausalRiskTests(unittest.TestCase):
    @staticmethod
    def _detections(frame):
        # Two vehicles move toward one another as the current pixel value rises.
        # No future frames, file names or total clip length are consulted.
        offset = float(frame[0, 0, 0])
        return [
            solution.Detection((5 + offset, 15, 15 + offset, 25), 2, "car", .9),
            solution.Detection((95 - offset, 15, 105 - offset, 25), 2, "car", .9),
        ]

    def _prefix_scores(self, video_id, total_frames):
        estimator = solution.RiskEstimator()
        meta = {"video_id": video_id, "fps": 10.0, "width": 120, "height": 60, "n_frames": total_frames}
        with patch.object(solution, "_detect", side_effect=self._detections), \
                patch.object(solution, "detect_events", side_effect=AssertionError("Part B may not call Part A")), \
                patch.object(cv2, "VideoCapture", side_effect=AssertionError("Part B may not reopen a video")):
            estimator.reset(meta)
            scores = [estimator.step(np.full((60, 120, 3), i, dtype=np.uint8), i / 10) for i in range(30)]
        self.assertTrue(all(isinstance(score, (int, float)) and math.isfinite(score) and 0 <= score <= 1 for score in scores))
        return scores

    def test_same_prefix_is_independent_of_name_and_future_length(self):
        self.assertEqual(self._prefix_scores("short.mp4", 30), self._prefix_scores("long.mp4", 3000))

    def test_reset_removes_previous_clip_state(self):
        estimator = solution.RiskEstimator()
        meta = {"video_id": "clip.mp4", "fps": 10.0, "width": 120, "height": 60, "n_frames": 30}
        frames = [np.full((60, 120, 3), i, dtype=np.uint8) for i in range(30)]
        with patch.object(solution, "_detect", side_effect=self._detections):
            estimator.reset(meta)
            first = [estimator.step(frame, i / 10) for i, frame in enumerate(frames)]
            estimator.reset(meta)
            second = [estimator.step(frame, i / 10) for i, frame in enumerate(frames)]
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
