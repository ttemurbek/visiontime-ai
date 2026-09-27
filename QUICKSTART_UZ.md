# RoadSight / DaemonEye — tez ishga tushirish

**Muhim:** rasmiy tekshiruv fayllari va YOLO11n modeli qo‘shilgan, 14 ta test o‘tgan. Haqiqiy model bilan 4 soniyalik sun’iy video 5,5 soniyada qayta ishlanib, 100 ta xavf qiymati chiqdi; rasmiy format tekshiruvi xatosiz o‘tdi. Bu tanlov videosidagi aniqlik natijasi emas. To‘rtta rasmiy videoning Google Drive yuklash limiti tugagan: natijalar hali yo‘q, kamera chiziqlari belgilanmagan, `predictions_samples.json` bo‘sh. [GitHubdagi loyiha](https://github.com/ttemurbek/visiontime-ai/tree/daemon-eye-toyota) `daemon-eye-toyota` branchida; internetdagi saytni joylash hali yakunlanmagan.

## 1. Papkani oching

ZIPni chiqaring va `solution.py` turgan `traffic-event-challenge` papkasida terminal oching. Yoki GitHubdan aynan ushbu branchni oling:

```bash
git clone --branch daemon-eye-toyota https://github.com/ttemurbek/visiontime-ai.git
cd visiontime-ai
```

Python **3.10, 3.11 yoki 3.12** kerak; 3.11 tavsiya etiladi.

```bash
python -m venv .venv
```

Windows:

```bat
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

## 2. Kutubxonalarni o‘rnating

NVIDIA GPU bilan odatiy o‘rnatish:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Faqat CPU uchun avval yengilroq PyTorch variantini o‘rnating, so‘ng qolgan kutubxonalarni:

```bash
python -m pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.txt
```

CPUda tahlil sekinroq bo‘lishi mumkin. Rasmiy 3× vaqt chegarasiga sig‘ishi haqiqiy videolarda tekshirilishi kerak. Linuxda `libGL.so.1` xatosi chiqsa, tizimga `libgl1` va `libglib2.0-0` paketlari kerak.

## 3. Modelni yuklang

Topshirilayotgan paketda `weights/yolo11n.pt` bor (**5 613 764 bayt**). Agar boshqa nusxada bo‘lmasa, internet yoqilgan holatda Linux/macOS terminalida yoki Windowsdagi **Git Bash** orqali:

```bash
bash weights/download.sh
```

Natijada `weights/yolo11n.pt` paydo bo‘lishi kerak. Bu faylsiz tahlil ishlamaydi. Model tayyor bo‘lgach, tahlil uchun internet talab qilinmaydi.

## 4. Saytni mahalliy oching

```bash
python app.py
```

Brauzerda `http://127.0.0.1:5000` ni oching. MP4 yuklab, hodisalar va xavf grafigini ko‘ring. Ushbu manzil faqat mahalliy ishga tushirish manzili; hakamlarga yuboriladigan ochiq sayt manzili emas.

## 5. Rasmiy videolar va kamera

`Videos.pdf` ichida **C3896.MP4, C3897.MP4, C3902.MP4, C3905.MP4** havolalari bor; jami hajm taxminan **18,8 GB**. Tekshiruvda to‘rttalasi ham Google Drive yuklash limiti xatosini qaytardi. Havolalar `sample_sources.json` ichida ham saqlangan. Fayllarni olish imkoni bo‘lganda `samples/` papkasiga asl nomlari bilan yuklang; tashkilotchidan boshqa ruxsatli yuklash manbasini olish ham mumkin.

Videoni ko‘rib, `config/camera.json` ichida yo‘l, piyodalar o‘tish joyi, yo‘l chiziqlari, svetofor va harakat yo‘nalishini belgilang. Koordinatalar nisbiy: `x / video_eni`, `y / video_boyi`. Bu sozlashni videosiz taxminan to‘ldirish mumkin emas. Bo‘sh sozlamada yo‘l qoidalariga bog‘liq ko‘plab hodisalar topilmaydi.

## 6. Rasmiy natijani yarating

Ikkala qismni birgalikda bajaradigan asosiy buyruq:

```bash
python run_submission.py --videos samples --out predictions_samples.json --team DaemonEye
python evaluate.py --pred predictions_samples.json --validate-only
```

`log.errors` ichidagi xatolarni tekshiring. Har bir videoning ikki qismga ketgan jami vaqti video davomiyligining uch baravaridan oshmasligi kerak. Rasmiy fayllarni yoki vaqt chegarasini o‘zgartirmang.

Aniqlikni o‘lchash uchun videolardagi haqiqiy hodisalarni qo‘lda belgilab `my_labels.json` yarating (`examples/ground_truth.json` shaklida):

```bash
python evaluate.py --pred predictions_samples.json --gt my_labels.json --per-video --json evaluation_report.json
```

`--validate-only` faqat fayl tuzilishini tekshiradi; model aniqligini isbotlamaydi. `examples/` ichidagi natijalar tashkilotchining namunasi, bizning video tahlilimiz emas.

Qo‘shimcha tekshiruv va video statistikasi:

```bash
python -m unittest discover -s tests -v
python tools/eda_samples.py --videos samples --out artifacts/eda
```

## 7. Topshirishda hali kerak

1. Haqiqiy sample natijalari va EDA, kamera sozlamalari, tekshiruv loglari.
2. Barcha kerakli fayllari bor **ochiq GitHub repository** va aniq commit SHA/tag.
3. Internetdan ochiladigan, video yuklash ishlaydigan **sayt havolasi**.
4. Jamoaning tasdiqlangan rollari/profil havolalari va yakuniy hisobot.
5. Tashkilotchining topshirish shakliga kerakli havolalarni kiritish.

Jamoa: **DaemonEye — Tursunov Temurbek, Nosirjonov Muxammadshaxzod, Shukrullo**. Shartnomadagi/topshiriqdagi muddat: **27-sentabr 2026, Toshkent vaqti bilan 23:59**. Ro‘yxatning qolgan bandlari `SUBMISSION_CHECKLIST.md` ichida.
