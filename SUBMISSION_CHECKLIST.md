# Submission checklist — DaemonEye

Deadline stated in the supplied brief: **27 September 2026, 23:59, Asia/Tashkent**. A locally runnable package alone is not the full submission.

## Verified package content

- [x] Team name and three supplied names recorded without invented roles/surnames.
- [x] `solution.py` defines `CLASSES`, `detect_events`, `RiskEstimator.reset` and `RiskEstimator.step`.
- [x] Official `run_submission.py`, `evaluate.py` and `examples/` copied unchanged; byte comparisons verified.
- [x] Pinned dependency file, Dockerfile, local web demo, tests and English/Uzbek instructions included.
- [x] Model/data attribution and known limitations documented.
- [x] All 14 unit/regression tests passed in the prepared environment.
- [x] Actual local YOLO11n checkpoint loaded: 5,613,764 bytes, checksum recorded.
- [x] Real-detector synthetic 4-second smoke: 100 risk samples, 5.5-second CPU runtime, official format VALID (no errors/warnings).

## Required before calling the submission complete

- [ ] Install dependencies in a clean environment and run `python -m unittest discover -s tests -v`.
- [x] Ensure `weights/yolo11n.pt` is available offline and model weights total at most 5 GB.
- [ ] Complete downloads of the four official sample MP4s; verify each decodes.
- [ ] Calibrate the camera geometry using those videos.
- [ ] Produce actual sample EDA, annotations and failure examples.
- [ ] Replace the empty `predictions_samples.json` with outputs for **every** supplied sample.
- [ ] Run the unchanged official harness and evaluator; retain runtime/error logs and measured metrics.
- [ ] Check no video is over the default combined 3× duration budget.
- [ ] Confirm members' roles, profile links and previous work.
- [ ] Publish a public repository containing the implementation and required artifacts.
- [ ] Record the final submitted commit SHA or tag.
- [ ] Publish a public website and verify a fresh MP4 upload and playback through that URL.
- [ ] Include team, approach, data/weights, actual sample EDA, event/risk visualizations, report and download/repository links on the site.
- [ ] Submit the repository commit/tag and live website URL through the organizer's submission channel.

## Commands

```bash
python run_submission.py --videos samples --out predictions_samples.json --team DaemonEye
python evaluate.py --pred predictions_samples.json --validate-only
python evaluate.py --pred predictions_samples.json --gt my_labels.json --per-video --json evaluation_report.json
```

An empty JSON can satisfy structural checks while providing no sample evidence. A format check cannot establish accuracy. Do not use the organizer's illustrative `examples/predictions.json` as model predictions.

**Current sample blocker:** all four supplied Drive links returned download-quota errors. Files C3896.MP4, C3897.MP4, C3902.MP4 and C3905.MP4 are unavailable for analysis. Exact URLs/status are recorded in `sample_sources.json`.

## Constraints and score

- Offline local inference; no hosted inference API; no future frames in Part B; no additional footage from the same camera beyond authorized samples.
- Additional datasets/weights, if introduced, need source and license documentation.
- Model score: `M = 0.7 × Score_A + 0.3 × Score_B`; if the test set has no accidents, `M = Score_A`.
- Elimination score: `0.6 × M + 0.25 × Website + 0.15 × Code`.
- Event score averages class F1 at temporal IoU 0.3, 0.5 and 0.7. Anticipation combines chance-normalized AP, alarm F1 and mean time-to-accident; see the unchanged evaluator for exact definitions.
