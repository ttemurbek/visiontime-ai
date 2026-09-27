# RoadSight — DaemonEye

A YOLO11n + tracking + geometry baseline for the **WIUT / Toyota traffic-event challenge**. It implements event intervals (Part A), a causal accident-risk curve (Part B), and a deployed Flask video-upload demo. The same solution can also run locally and through the official evaluation scripts.

**Live demo:** [http://167.99.245.20:8088](http://167.99.245.20:8088). The public page is deployed and accessible. Use the HTTP address shown here; HTTPS is not yet verified.

**Repository:** [ttemurbek/visiontime-ai](https://github.com/ttemurbek/visiontime-ai/tree/daemon-eye-toyota). The default branch is **`daemon-eye-toyota`**; the old `main` branch has been removed. The file-selection bug was fixed in commit [`5a4053e`](https://github.com/ttemurbek/visiontime-ai/commit/5a4053e). If a previously opened page still leaves the upload button disabled after choosing a valid video, refresh with **Ctrl+Shift+R**.

**Evaluation status:** the official runner, evaluator and example JSON files are included unchanged. Synthetic-video software checks passed, but the camera has not been calibrated on the organizer's footage. Actual sample-video predictions, sample EDA and measured accuracy are unavailable because all four supplied Drive downloads returned quota errors. **`predictions_samples.json` is an empty placeholder, not an evaluated submission.**

## O‘rtog‘ingiz qanday ishlatadi? / Uzbek demo guide

1. Brauzerda **[demo saytini oching](http://167.99.245.20:8088/#analysis)**. Login yoki GitHub akkaunti kerak emas.
2. **“Videoni shu yerga tashlang”** joyini bosib, MP4 faylni tanlang yoki faylni shu joyga tashlang. Limit: **2 daqiqa, 250 MB, 4K gacha**.
3. Fayl nomi va video oynasi paydo bo‘lgach, **“Tahlilni boshlash”** tugmasini bosing. Sahifadagi holat tahlilning qaysi bosqichdaligini ko‘rsatadi; CPUda bir necha daqiqa olishi mumkin.
4. Natijadagi hodisa belgisi yoki xavf grafigini bosing — video o‘sha vaqtga o‘tadi.
5. **“Natijani JSON yuklash”** orqali hodisalar va xavf qiymatlarini saqlang.

`RoadSight_test_20s.mp4` sun’iy test videosi yuklash va interfeysni sinash uchun yaratilgan. Unda **0 hodisa chiqishi mumkin**; bu haqiqiy yo‘l videosidagi aniqlik sinovi emas. Yuklangan video tahlil tugagach serverdan o‘chiriladi.

Saytni o‘z kompyuteringizda ishlatish uchun [QUICKSTART_UZ.md](QUICKSTART_UZ.md) qo‘llanmasini yoki quyidagi **Setup** bo‘limini bajaring. GitHubdan yuklashda **`daemon-eye-toyota` → Code → Download ZIP** ni tanlang. O‘rtog‘ingizga demo havolasi va MP4 faylning o‘zini yuborish yetarli.

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

To run a separate local demo:

```bash
python app.py
```

Open `http://127.0.0.1:5000`. This address points to your own computer. The publicly deployed demo is [http://167.99.245.20:8088](http://167.99.245.20:8088). Both show event intervals, a clickable risk curve and a downloadable JSON result. The web demo limits uploads to MP4, 120 seconds, 250 MB and at most 4K frame area. These demo limits do not replace the official evaluation harness.

Run checks separately from the running server:

```bash
python -m unittest discover -s tests -v
node tests/test_web_upload.cjs
```

Node.js is needed only for the browser-script regression fixture, not for running the Python demo. The regression invokes the actual JavaScript file-change and analysis handlers with a DOM fixture. It reproduces the previous missing-helper error and checks valid/invalid file selection, preview state, button enabling, asynchronous result/download handling, API error recovery and duration limits.

**Verified:** all 14 Python unit/regression tests and the Node.js upload regression passed. They cover geometry, the official interface, event boundaries, causal prefix independence and state reset. Separately, the unchanged official harness processed a synthetic 4.0-second, 640×360, 25-FPS clip using the real YOLO checkpoint: 0 events, 100 risk samples, 5.5 seconds on CPU against a 12-second budget. The official evaluator reported VALID with no errors or warnings. A repeat produced identical events/risk values (runtime 4.7 seconds). This is a software smoke test, not organizer-sample accuracy or a GPU benchmark.

```bash
docker build -t roadsight .
docker run --rm -p 5000:5000 roadsight
# Offline harness, with weights already included when building the image:
docker run --rm -v /absolute/videos:/data/test:ro -v /absolute/output:/output roadsight python run_submission.py --videos /data/test --out /output/predictions.json --team DaemonEye
```

The demo image installs CPU PyTorch, uses one Gunicorn worker to avoid loading multiple model copies, and honors `PORT` (default 5000). It includes the supplied weights or downloads them at build time if missing. This Docker image is intended for the CPU demo; use the local GPU installation for GPU judging.

## Deployment

The current demo runs on the existing DigitalOcean server at **[http://167.99.245.20:8088](http://167.99.245.20:8088)**. Its health endpoint is [`/health`](http://167.99.245.20:8088/health).

The initial-deployment commands for an existing server are:

```bash
git clone --branch daemon-eye-toyota https://github.com/ttemurbek/visiontime-ai.git roadsight-daemon-eye
cd roadsight-daemon-eye
bash deploy/existing_server.sh 167.99.245.20
```

These are **first-install commands**, not an update command for the already-running container. The script stops if `daemon-eye-demo` already exists or port 8088 is occupied. See [deploy/README_UZ.md](deploy/README_UZ.md) for prerequisites, resource checks and log commands. The current deployment status is recorded in this README; the deployment guide also contains general pre-deployment checks.

See [QUICKSTART_UZ.md](QUICKSTART_UZ.md), [REPORT.md](REPORT.md), [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). The package uses no additional training dataset and no hosted inference API.
