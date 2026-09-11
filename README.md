# VisionTime AI

Kamera yoki video orqali eshikdan kirish-chiqishni aniqlab, kelish-ketish vaqtini hisoblaydigan Computer Vision demo.

## Ishga tushirish

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Brauzerda `http://127.0.0.1:8000` ni oching.

Kamera/video modulini alohida terminalda yoqing:

```bash
pip install -r requirements-vision.txt
python -m vision.run_camera --source 0 --camera-id front-door --line 0.5
```

`--source 0` USB web-kamera. Video bilan ishlatish uchun `--source "sample.mp4"` bering.

> Bu demo yuzni tanimaydi. `track_id` kameradagi vaqtinchalik kuzatuv raqami; shaxsni bog‘lash uchun QR/beyjik yoki rozilik asosidagi alohida identifikatsiya qo‘shiladi.
