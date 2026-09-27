#!/usr/bin/env python3
"""Generate lightweight sample-video metadata and object-motion heatmaps."""
import argparse
import json
from pathlib import Path
import sys

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from solution import Tracker, _detect


def inspect_video(path: Path, out_dir: Path, stride_seconds: float = 1.0):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError("Cannot open " + str(path))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 25)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    nframes = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    stride = max(1, round(fps * stride_seconds))
    heat = np.zeros((height, width), dtype=np.float32)
    counts, brightness, counts_over_time = {}, [], []
    tracker = Tracker()
    trajectories = {}
    frame_index = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_index % stride == 0:
            brightness.append(float(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean()))
            detections = _detect(frame)
            t = frame_index / fps
            frame_counts = {}
            for d in detections:
                frame_counts[d.name] = frame_counts.get(d.name, 0) + 1
                counts[d.name] = counts.get(d.name, 0) + 1
                x, y = map(int, d.center)
                if 0 <= x < width and 0 <= y < height:
                    heat[y, x] += 1
            counts_over_time.append({"t_sec": round(t, 3), "by_class": frame_counts, "total": len(detections)})
            for tr in tracker.update(detections, t):
                trajectories.setdefault(str(tr.id), []).append([round(t, 2), round(tr.foot[0], 1), round(tr.foot[1], 1)])
        frame_index += 1
    cap.release()
    if not brightness:
        raise ValueError("No readable frames in " + str(path))
    heat = cv2.GaussianBlur(heat, (0, 0), sigmaX=max(5, width / 80))
    norm = cv2.normalize(heat, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    color = cv2.applyColorMap(norm, cv2.COLORMAP_TURBO)
    heatmap_path = path.stem + "_motion_heatmap.jpg"
    cv2.imwrite(str(out_dir / heatmap_path), color)
    return {
        "filename": path.name,
        "width": width,
        "height": height,
        "fps": fps,
        "duration_sec": round((nframes or frame_index) / fps, 2),
        "sampled_frame_count": len(brightness),
        "mean_brightness_0_255": round(float(np.mean(brightness)), 1),
        "detected_objects_by_class": counts,
        "counts_over_time": counts_over_time,
        "tracked_trajectories": trajectories,
        "motion_heatmap": heatmap_path,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--videos", required=True, type=Path)
    parser.add_argument("--out", default=Path("artifacts/eda"), type=Path)
    parser.add_argument("--sample-seconds", default=1.0, type=float)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    video_paths = sorted(p for p in args.videos.iterdir() if p.is_file() and p.suffix.lower() == ".mp4")
    if not video_paths:
        parser.error("No MP4 videos found; refusing to report empty EDA as completed.")
    summaries = []
    for video_path in video_paths:
        print("Inspecting", video_path.name, flush=True)
        summaries.append(inspect_video(video_path, args.out, args.sample_seconds))
    (args.out / "eda_summary.json").write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    print("Wrote", args.out / "eda_summary.json")
