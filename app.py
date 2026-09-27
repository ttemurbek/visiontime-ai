"""Bounded, asynchronous single-process demo for the official solution interfaces.

Run with ``python app.py``. The in-memory job store intentionally targets a small
hackathon demo; use a shared queue/store before deploying multiple processes.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
from pathlib import Path
import tempfile
import threading
import time
import uuid

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename
from solution import RiskEstimator, detect_events

ROOT = Path(__file__).resolve().parent
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 250 * 1024 * 1024
MAX_SECONDS = 120
MAX_PENDING = 3
JOB_TTL = 3600
_jobs: dict[str, dict] = {}
_lock = threading.Lock()
_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="roadsight")


def _update(job_id, **fields):
    with _lock:
        _jobs[job_id].update(fields)


def _run_job(job_id: str, path: Path, meta: dict):
    cap = None
    try:
        import cv2
        # Serialized execution keeps detector state and memory use predictable.
        _update(job_id, status="running", phase="events", progress=None,
                message="Hodisalar aniqlanmoqda. CPU tezligiga qarab bir necha daqiqa olishi mumkin.")
        events = detect_events(str(path))
        _update(job_id, phase="risk", progress=0,
                message="Hodisalar tayyor. Kadrlar bo‘yicha xavf hisoblanmoqda.")
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise ValueError("Video qayta ochilmadi.")
        estimator = RiskEstimator()
        estimator.reset({"video_id": meta["filename"], "fps": meta["fps"],
                         "width": meta["width"], "height": meta["height"],
                         "n_frames": meta["frames"]})
        risk = []
        index = 0
        output_stride = max(1, round(meta["fps"] / 5))
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            t = index / meta["fps"]
            if t > MAX_SECONDS:
                raise ValueError("Video 2 daqiqalik cheklovdan oshdi.")
            score = float(estimator.step(frame, t))
            if not math.isfinite(score):
                raise ValueError("Model yaroqsiz xavf qiymatini qaytardi.")
            if index % output_stride == 0:
                risk.append([round(t, 3), min(1.0, max(0.0, score))])
                _update(job_id, progress=min(99, round(index / meta["frames"] * 100)))
            index += 1
        if not index:
            raise ValueError("Videoda o‘qiladigan kadr topilmadi.")
        result = {**meta, "events": events, "risk": risk,
                  "team": "DaemonEye", "method": "YOLO + geometric-rule baseline",
                  "risk_note": "Heuristic score in [0,1], not a calibrated crash probability."}
        _update(job_id, status="done", phase="done", progress=100,
                message="Tahlil tugadi.", result=result, finished_at=time.time())
    except Exception as exc:
        app.logger.exception("Analysis job %s failed", job_id)
        message = "Tahlil bajarilmadi. Boshqa MP4 video bilan qayta urinib ko‘ring."
        if isinstance(exc, FileNotFoundError):
            message = "Tahlil xizmati hozir tayyor emas. Keyinroq urinib ko‘ring."
        elif isinstance(exc, ValueError):
            message = str(exc)
        _update(job_id, status="error", message=message, finished_at=time.time())
    finally:
        if cap is not None:
            cap.release()
        path.unlink(missing_ok=True)


@app.get("/")
def index():
    return send_from_directory(ROOT / "web", "index.html")


@app.get("/health")
def health():
    weights = Path(os.environ.get("TRAFFIC_WEIGHTS", ROOT / "weights" / "yolo11n.pt"))
    return jsonify({"status": "ok", "model_ready": weights.is_file(), "max_duration_sec": MAX_SECONDS})


@app.get("/downloads/predictions_samples.json")
def download_samples():
    return send_from_directory(ROOT, "predictions_samples.json", as_attachment=True)


@app.get("/downloads/yolo11n.pt")
def download_weights():
    return send_from_directory(ROOT / "weights", "yolo11n.pt", as_attachment=True)


@app.get("/report")
def report():
    return send_from_directory(ROOT, "REPORT.md", mimetype="text/plain; charset=utf-8")


@app.get("/api/samples")
def samples():
    summary_path = ROOT / "artifacts" / "eda" / "eda_summary.json"
    try:
        raw = json.loads(summary_path.read_text(encoding="utf-8"))
        rows = raw if isinstance(raw, list) else raw.get("videos", [])
        # Trajectories can be very large; the original EDA JSON remains downloadable.
        rows = [{k: v for k, v in row.items() if k != "tracked_trajectories"} for row in rows]
    except (OSError, ValueError, AttributeError, TypeError):
        rows = []
    return jsonify({"status": "available" if rows else "pending", "videos": rows,
                    "message": "Haqiqiy sample EDA natijalari" if rows else
                    "Tashkilotchi videolarini yuklash limiti sabab sample EDA hali tayyor emas."})


@app.get("/artifacts/eda/<path:asset>")
def eda_asset(asset):
    if Path(asset).suffix.lower() not in {".jpg", ".jpeg", ".png", ".json"}:
        return jsonify({"error": "Fayl topilmadi."}), 404
    return send_from_directory(ROOT / "artifacts" / "eda", asset)


@app.errorhandler(413)
def too_large(_exc):
    return jsonify({"error": "Fayl 250 MB limitdan katta. Qisqaroq MP4 yuklang."}), 413


@app.post("/api/analyze")
def analyze():
    upload = request.files.get("video")
    if not upload or not upload.filename:
        return jsonify({"error": "MP4 videoni tanlang."}), 400
    if Path(upload.filename).suffix.lower() != ".mp4":
        return jsonify({"error": "Faqat .mp4 format qabul qilinadi."}), 400
    path = None
    handed_off = False
    try:
        import cv2
        with tempfile.NamedTemporaryFile(prefix="roadsight-", suffix=".mp4", delete=False) as tmp:
            path = Path(tmp.name)
            upload.save(tmp)
        cap = cv2.VideoCapture(str(path))
        try:
            if not cap.isOpened():
                return jsonify({"error": "Videoni ochib bo‘lmadi."}), 400
            fps = float(cap.get(cv2.CAP_PROP_FPS))
            frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            ok, _frame = cap.read()
        finally:
            cap.release()
        if not ok or not math.isfinite(fps) or fps <= 0 or frames <= 0 or width <= 0 or height <= 0:
            return jsonify({"error": "MP4 metadata yoki kadrlarini o‘qib bo‘lmadi."}), 400
        duration = frames / fps
        if duration > MAX_SECONDS:
            return jsonify({"error": "Demo uchun video 2 daqiqadan oshmasin."}), 400
        if width * height > 3840 * 2160:
            return jsonify({"error": "Video o‘lchami 4K dan oshmasin."}), 400
        meta = {"filename": secure_filename(upload.filename) or "video.mp4",
                "duration": duration, "fps": fps, "frames": frames,
                "width": width, "height": height}
        job_id = uuid.uuid4().hex
        with _lock:
            now = time.time()
            expired = [k for k, v in _jobs.items() if now - v.get("finished_at", now) > JOB_TTL]
            for k in expired:
                del _jobs[k]
            if sum(v["status"] in {"queued", "running"} for v in _jobs.values()) >= MAX_PENDING:
                return jsonify({"error": "Navbat to‘ldi. Joriy tahlil tugagach qayta urinib ko‘ring."}), 429
            _jobs[job_id] = {"status": "queued", "phase": "queued", "progress": None,
                             "message": "Tahlil navbatga qo‘yildi.", "created_at": now}
        _worker.submit(_run_job, job_id, path, meta)
        handed_off = True
        return jsonify({"job_id": job_id, "status": "queued", "metadata": meta}), 202
    except Exception:
        app.logger.exception("Upload rejected")
        return jsonify({"error": "Video qabul qilinmadi. MP4 faylini tekshiring."}), 500
    finally:
        if path is not None and not handed_off:
            path.unlink(missing_ok=True)


@app.get("/api/jobs/<job_id>")
def job_status(job_id):
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return jsonify({"error": "Tahlil topilmadi yoki natija muddati tugagan."}), 404
        return jsonify(dict(job))


@app.get("/api/jobs/<job_id>/download")
def job_download(job_id):
    with _lock:
        job = _jobs.get(job_id)
        if job is None or job["status"] != "done":
            return jsonify({"error": "Natija hali tayyor emas."}), 404
        result = job["result"]
        # Same `videos` shape used by the official run_submission.py output.
        payload = {"team": "DaemonEye", "videos": {result["filename"]: {"events": result["events"], "risk": result["risk"]}}}
    response = app.response_class(json.dumps(payload, ensure_ascii=False, indent=2), mimetype="application/json")
    response.headers["Content-Disposition"] = 'attachment; filename="predictions.json"'
    return response


@app.get("/<path:asset>")
def assets(asset: str):
    return send_from_directory(ROOT / "web", asset)


if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "0.0.0.0"),
            port=int(os.environ.get("PORT", "5000")), debug=False, threaded=True)
