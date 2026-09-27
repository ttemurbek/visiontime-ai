# RoadSight — technical report

**Team:** DaemonEye · Tursunov Temurbek, Nosirjonov Muxammadshaxzod, Shukrullo. Roles and profile links have not been supplied.

## Approach

RoadSight is a fixed-camera baseline built from a local COCO-pretrained Ultralytics YOLO11n detector, centroid tracking and temporal geometry rules. It uses no additional training dataset. The detector supplies common vehicle/person/object boxes; camera rules interpret tracks using road areas, crosswalks, lane directions, stop lines and signal regions. Same-class overlapping intervals are merged before return from `detect_events(video_path)`.

The causal `RiskEstimator` receives frames from the organizer harness, maintains its own tracking state and derives bounded accident-risk scores from approaching objects and motion cues. It does not reopen a video or reuse a complete Part A analysis. Time-to-collision is an image-plane cue; scores are uncalibrated, and accident/near-miss outputs are heuristic candidates. Inference samples at most 8 frames/second by default, with a minimum frame stride of 3, and uses image size 640. Part B still returns a score for every frame passed by the official harness.

## Reproduction and interface

The repository includes the organizer's **unchanged** `run_submission.py`, `evaluate.py` and illustrative example JSONs. Python 3.10–3.12 and pinned dependencies are specified. Model weights must be downloaded before offline evaluation. CUDA is used when available, otherwise the CPU. The official run is:

```bash
python run_submission.py --videos /data/test --out predictions.json --team DaemonEye
```

The joint Part A + Part B budget is three times video duration; this budget has not been benchmarked on the official footage. The Flask demo offers upload, playable video, an event timeline and risk visualization. A public deployment has not been confirmed.

## Validation and current evidence

| Check | Observed result |
|---|---|
| Unit/regression suite | 14 tests passed: interface, geometry, boundaries, causal prefix and reset behavior |
| Local checkpoint | YOLO11n, 5,613,764 bytes; checksum in `weights/SHA256SUMS` |
| Real-detector software smoke | Synthetic 4.0-second clip, 640×360, 25 FPS; 0 events and 100 risk samples |
| Official harness timing | 5.5 seconds on CPU, below this clip's 12-second budget |
| Official JSON validation | VALID; 0 errors, 0 warnings |

The smoke clip is synthetic and contains no labeled traffic events. It verifies real inference and integration only; it is not an organizer-sample accuracy result or GPU benchmark.

All four official videos (**C3896.MP4, C3897.MP4, C3902.MP4, C3905.MP4**) returned Google Drive download-quota errors; URLs/status are in `sample_sources.json`. No usable sample file was obtained. Camera geometry is uncalibrated, no manually annotated development set exists, `predictions_samples.json` is an empty placeholder, and no sample EDA or measured Score_A/Score_B is reported. Organizer example predictions are not this system's outputs.

## Limitations and next steps

Geometry-dependent classes cannot operate reliably until camera regions are marked. COCO does not contain fire/smoke labels; the default checkpoint cannot support those classes. Perspective, occlusion, identity changes and projected box overlap can cause false incidents. Next steps are to download and inspect the supplied footage, mark scene geometry, annotate event boundaries, run the unchanged harness, inspect class-wise errors and timing, then publish the verified repository and website. No competitive accuracy claim is made.
