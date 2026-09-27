#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
from pathlib import Path
import shutil
from ultralytics import YOLO

target = Path("weights/yolo11n.pt")
target.parent.mkdir(parents=True, exist_ok=True)
# Loading this official model name triggers Ultralytics' checkpoint download.
model = YOLO("yolo11n.pt")
source = Path("yolo11n.pt")
if not source.is_file():
    source = Path(getattr(model, "ckpt_path", "yolo11n.pt"))
if source.is_file() and source.resolve() != target.resolve():
    shutil.copy2(source, target)
if not target.is_file() or target.stat().st_size == 0:
    raise SystemExit("Model download failed; confirm internet access and retry.")
print(f"Ready: {target} ({target.stat().st_size:,} bytes)")
PY
