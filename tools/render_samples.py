#!/usr/bin/env python3
"""Render real MP4s with local detections and previously computed predictions.

Example (from the repository root)::

    python run_submission.py --videos samples --out predictions_samples.json --team DaemonEye
    python tools/render_samples.py --videos samples --pred predictions_samples.json --out artifacts/samples

This is an offline visualization pass, not another Part A or Part B submission.
It never calls detect_events or RiskEstimator. Event intervals and the risk curve
come only from --pred; object boxes come from the existing local YOLO detector.
Past-only risk lookup uses the most recent supplied timestamp <= the displayed
source timestamp, without interpolation from a future sample.

Output video is silent, downscaled, and regularly frame-sampled. Its playback
rate is source_fps / render_stride, preserving elapsed time (the final duration
can differ by less than one output frame). All JSON event/risk/detection times
remain seconds from frame 0 of the exact input file; trimming an original resets
that origin and therefore requires predictions for the trimmed file itself.
Source timestamps use frame_index / source_fps, as in the official harness.
The same constant-FPS interpretation applies to variable-frame-rate inputs.
Box detections are sampled separately and held only until the next inference;
the on-screen detection age makes this visible. This pass does not measure model
accuracy or validate that an externally supplied risk curve was computed causally.
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def number(value, name):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def read_predictions(path, video_paths):
    from solution import CLASSES

    data = json.loads(path.read_text(encoding="utf-8"))
    videos = data.get("videos")
    if not isinstance(videos, dict):
        raise ValueError("--pred must be official-format JSON with a videos object")
    entries = {}
    for video in video_paths:
        entry = videos.get(video.name)
        if not isinstance(entry, dict):
            raise ValueError(f"No exact prediction entry for {video.name}; run the harness on this input first")
        if not isinstance(entry.get("events"), list) or not isinstance(entry.get("risk"), list):
            raise ValueError(f"{video.name}: predictions require events and risk arrays")
        events, risk = [], []
        for event in entry["events"]:
            if not isinstance(event, list) or len(event) != 3:
                raise ValueError(f"{video.name}: invalid event {event!r}")
            start, end = number(event[0], "event start"), number(event[1], "event end")
            if not 0 <= start < end or event[2] not in CLASSES:
                raise ValueError(f"{video.name}: invalid event {event!r}")
            events.append([start, end, event[2]])
        previous = -1.0
        for point in entry["risk"]:
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError(f"{video.name}: invalid risk point {point!r}")
            t, score = number(point[0], "risk time"), number(point[1], "risk score")
            if t < 0 or t < previous or not 0 <= score <= 1:
                raise ValueError(f"{video.name}: risk needs chronological nonnegative times and scores in [0, 1]")
            risk.append([t, score])
            previous = t
        entries[video.name] = {"events": events, "risk": risk}
    return data, entries


def text(cv2, image, message, x, y, color=(235, 240, 245), scale=.5):
    cv2.putText(image, message, (x, y), cv2.FONT_HERSHEY_SIMPLEX,
                scale, color, 1, cv2.LINE_AA)


def render_one(path, entry, out, args, prediction_log):
    import cv2
    import numpy as np
    from solution import _detect, _prepare_frame

    cap = cv2.VideoCapture(str(path))
    writer = None
    if not cap.isOpened():
        cap.release()
        raise ValueError(f"Cannot open video: {path}")
    raw_video = out / (path.name + ".rendering.mp4")
    final_video = out / (path.name + ".annotated.mp4")
    timeline_path = out / (path.name + ".timeline.json")
    try:
        fps = number(cap.get(cv2.CAP_PROP_FPS), "source FPS")
        if fps <= 0:
            raise ValueError(f"{path.name}: cannot preserve source timestamps without a positive FPS")
        source_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        source_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        declared_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        declared_duration = max(0, declared_frames) / fps
        render_stride = max(1, math.ceil(fps / args.render_fps))
        output_fps = fps / render_stride
        detection_stride = render_stride * max(1, math.ceil(output_fps / args.detect_fps))
        events, curve = entry["events"], entry["risk"]
        risk_times = [point[0] for point in curve]
        rows = sorted({event[2] for event in events})
        detection_samples = []
        detections, detection_time = [], None
        source_index = rendered_frames = 0
        panel_height = 240
        width = height = None
        while True:
            ok, source_frame = cap.read()
            if not ok:
                break
            if source_index % render_stride:
                source_index += 1
                continue
            t = source_index / fps
            frame = _prepare_frame(source_frame, args.max_dimension)
            if writer is None:
                height, width = frame.shape[:2]
                # Even dimensions are necessary for the optional H.264 encode.
                width, height = width - width % 2, height - height % 2
                if min(width, height) < 2:
                    raise ValueError(f"{path.name}: unusable frame dimensions")
                frame = frame[:height, :width]
                canvas_width = max(640, width)
                writer = cv2.VideoWriter(str(raw_video), cv2.VideoWriter_fourcc(*"mp4v"),
                                         output_fps, (canvas_width, height + panel_height))
                if not writer.isOpened():
                    raise RuntimeError("OpenCV could not create an MP4 video writer")
            frame = frame[:height, :width]
            if source_index % detection_stride == 0:
                detections = _detect(frame)
                detection_time = t
                detection_samples.append({
                    "t_sec": round(t, 6),
                    "source_frame_index": source_index,
                    "objects": [{"label": d.name, "confidence": round(d.confidence, 5),
                                 "box_xyxy": [round(v, 2) for v in d.box]} for d in detections],
                })
            for detection in detections:
                x1, y1, x2, y2 = map(lambda value: int(round(value)), detection.box)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (80, 225, 120), 2)
                text(cv2, frame, f"{detection.name} {detection.confidence:.2f}",
                     max(0, x1), max(15, y1 - 5), (80, 225, 120), .42)
            canvas = np.full((height + panel_height, canvas_width, 3), (25, 23, 20), dtype=np.uint8)
            canvas[:height, :width] = frame
            risk_index = bisect_right(risk_times, t + 1e-9) - 1
            score = curve[risk_index][1] if risk_index >= 0 else None
            active = [label for start, end, label in events if start <= t < end]
            text(cv2, canvas, f"{path.name} | source time {t:.2f}s | frame {source_index}", 12, height + 23)
            age = t - detection_time if detection_time is not None else 0
            risk_message = f"{score:.3f}" if score is not None else "not available"
            text(cv2, canvas, f"Risk from supplied predictions: {risk_message} | box age: {age:.2f}s", 12, height + 46)
            active_message = ", ".join(active) or "none"
            text(cv2, canvas, "Active Part A events: " + active_message[:100], 12, height + 69)

            # A past-only risk graph. No future risk point enters this display.
            left, right = 38, canvas_width - 15
            top, bottom = height + 88, height + 157
            cv2.rectangle(canvas, (left, top), (right, bottom), (85, 85, 85), 1)
            text(cv2, canvas, "1", 17, top + 5, scale=.35)
            text(cv2, canvas, "0", 17, bottom, scale=.35)
            window_start = max(0, t - args.risk_window)
            curve_start = max(0, bisect_right(risk_times, window_start) - 1)
            points = curve[curve_start:risk_index + 1] if risk_index >= 0 else []
            if points:
                # Bounded drawing cost even when the prediction curve is dense.
                step = max(1, len(points) // max(1, right - left))
                visible = points[::step]
                if visible[-1] != points[-1]:
                    visible.append(points[-1])
                coordinates = [(int(left + (max(window_start, pt) - window_start) /
                                    args.risk_window * (right - left)),
                                int(bottom - risk * (bottom - top))) for pt, risk in visible]
                if len(coordinates) >= 2:
                    cv2.polylines(canvas, [np.asarray(coordinates, dtype=np.int32)], False, (60, 200, 245), 2)
                else:
                    cv2.circle(canvas, coordinates[0], 2, (60, 200, 245), -1)
            text(cv2, canvas, f"Past risk: {window_start:.1f}s to {t:.1f}s (window {args.risk_window:g}s)",
                 12, height + 176, scale=.4)

            # Whole-file Part A timeline is retrospective and never used as risk input.
            duration_for_axis = max(declared_duration, t + 1 / fps)
            y = height + 197
            cv2.line(canvas, (left, y), (right, y), (80, 80, 80), 8)
            for start, end, _label in events:
                x1 = int(left + min(1, start / duration_for_axis) * (right - left))
                x2 = int(left + min(1, end / duration_for_axis) * (right - left))
                cv2.line(canvas, (x1, y), (x2, y), (95, 175, 240), 8)
            x = int(left + min(1, t / duration_for_axis) * (right - left))
            cv2.line(canvas, (x, y - 9), (x, y + 9), (245, 245, 245), 2)
            text(cv2, canvas, "Retrospective event timeline | local detector | heuristic risk, not crash probability",
                 12, height + 228, scale=.36)
            writer.write(canvas)
            rendered_frames += 1
            source_index += 1
        if not rendered_frames:
            raise ValueError(f"{path.name}: no decodable frames; no sample result generated")
        writer.release()
        writer = None
        duration = source_index / fps
        if any(end > duration + 1 / fps for _, end, _ in events):
            raise ValueError(f"{path.name}: supplied events exceed input duration; predictions may refer to another cut")
        if curve and curve[-1][0] > duration + 1 / fps:
            raise ValueError(f"{path.name}: supplied risk exceeds input duration; predictions may refer to another cut")

        codec = "mp4v"
        # H.264 + faststart is playable in more browsers than OpenCV's mp4v.
        if shutil.which("ffmpeg"):
            encoded = out / (path.name + ".encoding.mp4")
            process = subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw_video),
                "-an", "-c:v", "libx264", "-threads", "2", "-preset", "veryfast",
                "-crf", "25", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(encoded),
            ], capture_output=True, text=True)
            if process.returncode == 0 and encoded.is_file() and encoded.stat().st_size:
                encoded.replace(final_video)
                raw_video.unlink()
                codec = "h264"
            else:
                encoded.unlink(missing_ok=True)
                print(f"Warning: {path.name}: H.264 unavailable; retained playable-by-VLC mp4v output", file=sys.stderr)
                raw_video.replace(final_video)
        else:
            raw_video.replace(final_video)
        result = {
            "source_video": path.name,
            "source_size_bytes": path.stat().st_size,
            "prediction_file": str(args.pred),
            "annotated_video": final_video.name,
            "video_codec": codec,
            "source": {"width": source_width, "height": source_height, "fps": fps,
                       "decoded_frames": source_index, "duration_sec": duration},
            "render": {"width": canvas_width, "height": height + panel_height,
                       "image_width": width, "image_height": height, "fps": output_fps,
                       "frame_stride": render_stride, "frames": rendered_frames,
                       "duration_sec": rendered_frames / output_fps, "audio": "omitted"},
            "detection": {"method": "solution._detect local YOLO; no hosted inference",
                          "source_frame_stride": detection_stride,
                          "effective_fps": fps / detection_stride,
                          "box_coordinates": "pixels in the rendered image region, excluding bottom panel",
                          "samples": detection_samples},
            "time_note": "All times are frame_index/source_fps seconds from this exact input's frame 0. "
                         "Display frame sampling preserves playback speed; no trimming or speed change.",
            "risk_note": "Supplied prediction curve, not recomputed. Display uses latest point at or before "
                         "source time. No future interpolation. Heuristic score, not calibrated probability.",
            "event_note": "Retrospective Part A events supplied by --pred; never used to compute risk here.",
            "events": events, "event_classes": rows, "risk": curve,
            "prediction_log": prediction_log,
            "timeline_json": timeline_path.name,
        }
        timeline_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return {key: result[key] for key in ("source_video", "annotated_video", "timeline_json", "source", "render")}
    finally:
        cap.release()
        if writer is not None:
            writer.release()
        raw_video.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--videos", type=Path, required=True, help="MP4 folder or one MP4; uppercase extensions supported")
    parser.add_argument("--pred", type=Path, required=True, help="Official-format predictions for these exact source files")
    parser.add_argument("--out", type=Path, required=True, help="Output directory for annotated MP4s and timeline JSON")
    parser.add_argument("--max-dimension", type=int, default=1280, help="Maximum image dimension (320–1920), excluding panel")
    parser.add_argument("--render-fps", type=float, default=8, help="Maximum playback frame rate (1–30), preserving elapsed time")
    parser.add_argument("--detect-fps", type=float, default=4, help="Maximum local box-inference rate (0.1–30 Hz)")
    parser.add_argument("--risk-window", type=float, default=20, help="Past-only risk graph window in seconds")
    args = parser.parse_args()
    if not 320 <= args.max_dimension <= 1920:
        parser.error("--max-dimension must be between 320 and 1920")
    if not 1 <= args.render_fps <= 30 or not .1 <= args.detect_fps <= 30:
        parser.error("--render-fps must be 1–30 and --detect-fps must be 0.1–30")
    if not math.isfinite(args.risk_window) or args.risk_window <= 0:
        parser.error("--risk-window must be finite and positive")
    if args.videos.is_file():
        video_paths = [args.videos] if args.videos.suffix.lower() == ".mp4" else []
    elif args.videos.is_dir():
        video_paths = sorted(p for p in args.videos.iterdir() if p.is_file() and p.suffix.lower() == ".mp4")
    else:
        parser.error(f"Video path does not exist: {args.videos}")
    if not video_paths:
        parser.error("No MP4 videos found; refusing to generate empty sample artifacts")
    try:
        predictions, entries = read_predictions(args.pred, video_paths)
        args.out.mkdir(parents=True, exist_ok=True)
        summaries = []
        for path in video_paths:
            print(f"Rendering {path.name} with real local detections", flush=True)
            summaries.append(render_one(path, entries[path.name], args.out, args,
                                        predictions.get("log", {}).get(path.name, {})))
        manifest = {"team": predictions.get("team"), "status": "rendered_from_actual_input_videos",
                    "videos": summaries}
        (args.out / "index.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"Wrote {len(summaries)} annotated videos and timeline JSON files to {args.out}")
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f"Sample rendering failed: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
