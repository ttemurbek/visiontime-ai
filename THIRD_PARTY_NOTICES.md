# Third-party notices

## Ultralytics YOLO11n

The default detector is **Ultralytics YOLO11n**, pretrained on COCO. The runtime package is pinned to `ultralytics==8.3.0`; the checkpoint is downloaded using the official model name `yolo11n.pt`. The original model architecture and pretrained weights are not the team's work. Ultralytics publishes its open-source software/models under AGPL-3.0 and also offers an enterprise license. Keep the applicable upstream license and notices with any redistribution.

- Model documentation: https://docs.ultralytics.com/models/yolo11/
- Source and license: https://github.com/ultralytics/ultralytics
- Licensing information: https://www.ultralytics.com/license

## COCO

COCO is the pretraining dataset for the default checkpoint. COCO annotations are provided under CC BY 4.0; source images retain the applicable per-image licenses. No COCO images or annotations are redistributed by this project. No additional training or fine-tuning dataset is used.

- Dataset: https://cocodataset.org/
- Terms: https://cocodataset.org/#termsofuse

## Organizer materials

`run_submission.py`, `evaluate.py`, `examples/ground_truth.json` and `examples/predictions.json` are supplied by the **WIUT Hackathon CV track organizers** and included unchanged. They are not team-authored code or measured outputs. Their inclusion does not imply that the team's model achieves the example scores. Organizer sample footage is not bundled, and no new redistribution license is asserted for it.

## Runtime dependencies

NumPy, OpenCV, PyTorch, torchvision, Flask, Gunicorn and their transitive dependencies retain their own upstream licenses and notices. Consult installed package metadata and the upstream distributions. This notice does not relicense third-party components or claim ownership of their pretrained models or data.
