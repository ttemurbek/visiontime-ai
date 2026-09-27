#!/usr/bin/env python3
"""Local runner matching the published predictions.json shape.

The official run_submission.py from the organizers must be used for final
submission; this helper is for local smoke tests before that file is available.
"""
import argparse
import json
from pathlib import Path
import sys

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from solution import RiskEstimator, detect_events


def run(videos_dir: Path, output: Path, team: str) -> None:
    videos = {}
    paths = sorted(p for p in videos_dir.iterdir() if p.suffix.lower() == ".mp4")
    for path in paths:
        print(f"Analyzing {path.name} ...", flush=True)
        events = detect_events(str(path))
        cap = cv2.VideoCapture(str(path))
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 25)
        meta = {
            "video_id": path.name,
            "fps": fps,
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "n_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        }
        estimator = RiskEstimator()
        estimator.reset(meta)
        risk = []
        index = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            t = index / fps
            risk.append([round(t, 4), estimator.step(frame, t)])
            index += 1
        cap.release()
        videos[path.name] = {"events": events, "risk": risk}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"team": team, "videos": videos}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--videos", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--team", default="DaemonEye")
    args = parser.parse_args()
    run(args.videos, args.out, args.team)
