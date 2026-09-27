# RoadSight — DaemonEye

A local YOLO11n + tracking + geometry baseline for the **WIUT / Toyota traffic-event challenge**. It implements event intervals (Part A), a causal accident-risk curve (Part B), and a Flask video-upload demo.

**Current status:** the official runner, evaluator and example JSON files are included unchanged. The camera has not been calibrated on the organizer's footage. Actual sample-video predictions, sample EDA and measured accuracy are not available. `predictions_samples.json` is an empty placeholder, not a completed submission. The [public submission branch](https://github.com/ttemurbek/visiontime-ai/tree/daemon-eye-toyota) is `daemon-eye-toyota`; website deployment is pending.

## Team

| Member | Role / profile |
|---|---|
| Tursunov Temurbek | Not supplied |
| Nosirjonov Muxammadshaxzod | Not supplied |
| Shukrullo | Surname, role and profile not supplied |

Team name: **DaemonEye**. Do not infer contributions from this table. See `TEAM_INFO_TEMPLATE.md` for missing details.

## Setup

Use **Python 3.10–3.12**. Python 3.11 is used by the Dockerfile. Clone the challenge branch (or open the extracted ZIP):

```bash
git clone --branch daemon-eye-toyota https://github.com/ttemurbek/visiontime-ai.git
cd visiontime-ai
```

From the directory containing `solution.py`:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
bash weights/download.sh
```

On Windows use `.venv\Scripts\activate` and run the download script in Git Bash. On a minimal Debian/Ubuntu system OpenCV also needs `libgl1` and `libglib2.0-0`; these are installed by the Dockerfile.

The default requirements install PyTorch 2.5.1 and torchvision 0.20.1. Inference selects CUDA device 0 when available and otherwise uses the CPU. GPU execution needs an NVIDIA GPU and a driver compatible with the installed PyTorch CUDA runtime. No training is required. Runtime and GPU memory use on the organizer's long videos remain unmeasured.

For a smaller **CPU-only demo installation**, run this before installing `requirements.txt`:

```bash
python -m pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.txt
```

The downloaded `weights/yolo11n.pt` is **5,613,764 bytes**; its SHA256 is recorded in `weights/SHA256SUMS`. Git checkouts use the included download script to obtain it once with internet access. The model is loaded only from a local path during analysis; missing weights cause an explicit error. Install dependencies and prepare weights before offline judging. `TRAFFIC_WEIGHTS` and `TRAFFIC_CONFIG` may override the default checkpoint and camera JSON paths.

## Official run

Put the supplied MP4 files in `samples/`, then run both parts with the unchanged organizer harness:

```bash
python run_submission.py --videos samples --out predictions_samples.json --team DaemonEye
python evaluate.py --pred predictions_samples.json --validate-only
```

The exact hidden-test command is:

```bash
python run_submission.py --videos /data/test --out predictions.json --team DaemonEye
```

To measure accuracy, first manually label the sample videos using the organizer's conventions and the shape in `examples/ground_truth.json`:

```bash
python evaluate.py --pred predictions_samples.json --gt my_labels.json --per-video --json evaluation_report.json
```

A format pass is **not** an accuracy result. The JSONs in `examples/` are the organizer's illustrative examples, not measurements of this model. The default time limit is **3 × each video's duration for Part A and Part B combined**; inspect every video's `log.errors`. An over-budget video is scored as empty. Do not change the official scripts or relax their defaults for a reported judging run.

## Model and limitations

- COCO-pretrained **YOLO11n** detects generic objects. Confidence threshold is 0.25, inference image size 640, with up to 150 detections per sampled frame.
- A deterministic centroid tracker associates detections. Geometric and motion rules create intervals, then merge overlapping same-class intervals.
- Sampling uses the larger of `frame_stride` (default 3) and the stride needed to stay at or below `max_analyzed_fps` (default 8). At 25 FPS this means one analysis every four frames. Large frames are resized before tracking.
- `RiskEstimator.reset(meta)` / `step(frame, t_sec)` maintain an independent causal state. The estimator processes supplied frames only and returns one bounded score per call. Time-to-collision is an image-plane cue; risk is an uncalibrated heuristic score. Accident and near-miss intervals are heuristic candidates, not verified collisions.
- Part A exposes the 14 official IDs through `CLASSES`. This does **not** mean all 14 classes are reliably detected. Camera-dependent rules remain inactive without the required geometry. COCO has no fire/smoke classes, so the default detector cannot support `fire_smoke`.
- Perspective, occlusion, tracker identity changes and overlapping boxes can produce misses or false alarms. No sample-ground-truth F1, AP or time-to-accident result has been measured.

## Camera calibration and sample EDA

The supplied `Videos.pdf` links four large Google Drive videos (approximately 18.8 GB in total): **C3896.MP4, C3897.MP4, C3902.MP4 and C3905.MP4**. All four download attempts returned a Google Drive download-quota error. No usable sample MP4 was obtained; source URLs and status are recorded in `sample_sources.json`. Sample predictions, EDA and calibration remain blocked on obtaining those actual files.

Inspect the actual camera footage and fill `config/camera.json` with **normalized** coordinates `(x / width, y / height)`: road/intersection polygons, lanes/crosswalks, stop and solid lines, signal ROI, traffic direction and queue areas. Keep unobserved geometry empty. Thresholds use the processed image scale and need camera-specific validation.

Once actual sample MP4s and the weights are available:

```bash
python tools/eda_samples.py --videos samples --out artifacts/eda
python tools/render_samples.py --videos samples --pred predictions_samples.json --out artifacts/samples
```

The EDA helper produces metadata, brightness, sampled object counts over time, approximate tracks and occupancy heatmaps. The renderer creates annotated playback, event/risk timelines and an index from actual videos plus previously generated predictions; source timestamps remain in seconds. Sampled boxes are explicitly labeled. These counts are detections across frames, not unique vehicles. No real sample EDA is claimed until the tool has run on those files.

## Demo and checks

```bash
python app.py
python -m unittest discover -s tests -v
```

Open `http://127.0.0.1:5000`. The local UI uploads MP4s and displays event intervals and the risk curve. Upload/runtime limits are enforced by `app.py`. This local address is not a publicly hosted judging URL.

**Verified:** all 14 unit/regression tests passed. They cover geometry, the official interface, event boundaries, causal prefix independence and state reset. Separately, the unchanged official harness processed a synthetic 4.0-second, 640×360, 25-FPS clip using the real YOLO checkpoint: 0 events, 100 risk samples, 5.5 seconds on CPU against a 12-second budget. The official evaluator reported VALID with no errors or warnings. A repeat produced identical events/risk values (runtime 4.7 seconds). This is a software smoke test, not organizer-sample accuracy or a GPU benchmark.

```bash
docker build -t roadsight .
docker run --rm -p 5000:5000 roadsight
# Offline harness, with weights already included when building the image:
docker run --rm -v /absolute/videos:/data/test:ro -v /absolute/output:/output roadsight python run_submission.py --videos /data/test --out /output/predictions.json --team DaemonEye
```

The demo image installs CPU PyTorch, uses one Gunicorn worker to avoid loading multiple model copies, and honors `PORT` (default 5000). It includes the supplied weights or downloads them at build time if missing. This Docker image is intended for the CPU demo; use the local GPU installation for GPU judging. Hosting still requires a public destination and a successful upload test.

See [QUICKSTART_UZ.md](QUICKSTART_UZ.md), [REPORT.md](REPORT.md), [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). The package uses no additional training dataset and no hosted inference API.
