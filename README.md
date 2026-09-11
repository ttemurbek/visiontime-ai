# VisionTime AI

**Kamera yoki video orqali eshikdan kirish-chiqishni aniqlab, kelish-ketish vaqtini hisoblaydigan Computer Vision tizimi.**

## Nima qiladi?

VisionTime AI videodagi odamni aniqlaydi, virtual eshik chizig‘idan o‘tganini qayd etadi va quyidagilarni veb-panelda ko‘rsatadi:

- qachon keldi;
- qachon ketdi;
- ichkarida qancha vaqt bo‘ldi;
- kamera nomi va vaqtinchalik Track ID.

> Hozirgi demo yuzni tanimaydi. `track_id` faqat kamera ichidagi vaqtinchalik raqam. Keyingi versiyada QR-beyjik yoki rozilik asosidagi identifikatsiya orqali xodim ismi qo‘shiladi.

## Kimlar uchun?

- Ofislar va do‘konlar
- O‘quv markazlari
- Ombor va ishlab chiqarish joylari
- Tadbir yoki kirish punktlari

## Loyiha qismlari

1. **AI kamera moduli** — odamni video/kamerada topadi va harakatini kuzatadi.
2. **Veb-panel** — kelish-ketish hodisalarini jadvalda ko‘rsatadi.
3. **Ma’lumotlar bazasi** — hodisalarni saqlaydi.

## Tez ishga tushirish

### 1. Loyihani yuklab olish

GitHub sahifasidagi yashil **Code** → **Download ZIP** tugmasini bosing.

Dasturchilar esa Terminalda quyidagini yozadi:

```bash
git clone https://github.com/ttemurbek/visiontime-ai.git
cd visiontime-ai
```

### 2. Asosiy o‘rnatish

Ubuntu Terminal’ni oching: `Ctrl + Alt + T`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Terminal boshida `(.venv)` yozuvi chiqishi kerak.

### 3. Veb-panelni ochish

```bash
uvicorn app.main:app --reload
```

Terminalni yopmang. Brauzerda quyidagi manzilni oching:

```text
http://127.0.0.1:8000
```

Panelda Kamera, Track ID, Keldi, Ketdi va Davomiylik ustunlari ko‘rinadi.

## AI kamera modulini o‘rnatish

Yangi Terminal oynasini oching va loyiha papkasiga kiring:

```bash
cd visiontime-ai
source .venv/bin/activate
```

CPU uchun AI modulini o‘rnating:

```bash
pip install --timeout 120 --retries 10 --index-url https://download.pytorch.org/whl/cpu torch torchvision
pip install --timeout 120 --retries 10 ultralytics opencv-python requests
```

## Kamera bilan ishlash

USB yoki ichki kamera ishlasa:

```bash
python -m vision.run_camera --source 0 --camera-id front-door --line 0.5
```

- `--source 0` — birinchi kamera.
- `front-door` — kamera nomi.
- `--line 0.5` — ekranning o‘rtasidagi virtual eshik chizig‘i.

Kamera oynasida:

- yashil ramka — AI aniqlagan odam;
- `#27` kabi yozuv — vaqtinchalik Track ID;
- sariq chiziq — virtual kirish-chiqish chegarasi.

Odam chapdan o‘ngga o‘tsa `IN` (keldi), teskari tomonga o‘tsa `OUT` (ketdi) hodisasi veb-panelga yuboriladi.

Kamera oynasini yopish uchun `q` tugmasini bosing.

## Kamera bo‘lmasa, video bilan sinash

```bash
python -m vision.run_camera --source "/to‘liq/video/yo‘li/test.mp4" --camera-id front-door --line 0.5
```

Masalan:

```bash
python -m vision.run_camera --source "/home/user/Downloads/video.mp4" --camera-id front-door --line 0.5
```

Video ichidagi odam sariq chiziqni kesib o‘tsa, hodisa jadvalga yoziladi. So‘ng brauzerdagi **Yangilash** tugmasini bosing.

## Muammolar va yechim

### `Kamera/video ochilmadi: 0`

Ubuntu kamera qurilmasini ko‘rmayapti. Quyidagilarni tekshiring:

- noutbukdagi kamera yopqichi ochiqmi;
- kamera bloklash tugmasi yoqilmaganmi;
- Zoom, Telegram yoki Chrome kamerani band qilmaganmi;
- USB web-kamera ulanganmi.

Kamera bo‘lmasa, loyihani video fayl bilan sinab ko‘rish mumkin.

### GitHub’dan boshqalar foydalanishi

Repo **Public** bo‘lsa, har kim uni yuklab olishi mumkin. GitHub akkaunti talab qilinmaydi.

Oddiy foydalanuvchi kod o‘rnatmaydi. Keyingi bosqichda loyiha internet serverga joylashtiriladi: kamera ishxonadagi kompyuterda ishlaydi, rahbarlar esa telefondan veb-panelni ko‘radi.

## GitHub bilan ishlash

Yangi o‘zgarishlarni olish:

```bash
git pull
```

O‘zgarishlarni GitHub’ga yuborish:

```bash
git add .
git commit -m "Yangi o‘zgarish"
git push
```

GitHub Terminalda oddiy parol qabul qilmaydi. Kirish uchun `gh auth login --web --git-protocol https` buyrug‘idan foydalaning.

## Keyingi reja

- QR-beyjik bilan xodimni aniqlash
- Telegram orqali kunlik hisobot
- Kechikkanlar ro‘yxati
- “Hozir kimlar ichkarida?” ko‘rsatkichi
- Bir nechta kamera
- Excel/PDF hisobot
- Mobil ilova
- Internetga joylashtirilgan rahbar paneli
