# Mavjud DigitalOcean serverida ishga tushirish

Bu skriptni **serverning o‘z terminalida** qo‘lda bajaring. U yangi Droplet yaratmaydi, server hajmini o‘zgartirmaydi va mavjud saytlarni qayta ishga tushirmaydi. Docker oldindan o‘rnatilgan bo‘lishi kerak.

Ko‘rilayotgan server manzili: **167.99.245.20**. RAMning hozirgi bo‘sh miqdori va **8088** porti masofadan tekshirilmagan; skript ularni ish boshlashdan oldin tekshiradi. Kamida 1536 MiB `MemAvailable` bo‘lmasa boshlamaydi. Image yig‘ish uchun ham disk, RAM va internet kerak; 1536 MiB / 1.5 CPU cheklovi ishga tushgan konteynerga qo‘llanadi.

DigitalOcean server konsolida yoki o‘zingizning SSH terminalingizda:

```bash
git clone --branch daemon-eye-toyota https://github.com/ttemurbek/visiontime-ai.git roadsight-daemon-eye
cd roadsight-daemon-eye
bash deploy/existing_server.sh 167.99.245.20
```

Agar loyihani ZIPdan chiqargan bo‘lsangiz, `solution.py` bor papkaga kirib faqat oxirgi buyruqni bajaring. Agar Docker uchun ruxsat yetishmasa, administrator sifatida shu buyruqni bajaring; skript foydalanuvchi guruhlari yoki Docker sozlamalarini o‘zgartirmaydi.

Skript quyidagilarni bajaradi:

1. Docker, `curl`, `ss`, Python 3 va loyiha fayllarini tekshiradi.
2. `daemon-eye-demo` konteyneri allaqachon mavjud yoki TCP 8088 band bo‘lsa to‘xtaydi; ularni o‘chirmaydi.
3. Joriy `Dockerfile` orqali alohida image yig‘adi.
4. Bitta Gunicorn worker bilan `daemon-eye-demo`ni ishga tushiradi: **1.5 CPU**, **1536 MiB RAM**, `unless-stopped`, **8088 → 5000**.
5. Mahalliy `/health` javobi va model fayli mavjudligini tekshiradi, so‘ng berilgan hostdan URL chiqaradi.

Mahalliy tekshiruv o‘tsa, boshqa qurilmadan **http://167.99.245.20:8088** ni ochib ko‘ring. Skript UFW/DigitalOcean firewallini yoki boshqa portlarni o‘zgartirmaydi; shu sabab mahalliy tekshiruvning o‘tishi tashqi kirish ochilganini bildirmaydi. Skript domen yoki tashqi IPni hech qayerdan o‘zi aniqlamaydi.

Holat va loglarni ko‘rish:

```bash
docker ps --filter name=daemon-eye-demo
docker logs --tail 100 daemon-eye-demo
curl --fail http://127.0.0.1:8088/health
```

Takror ishga tushirish mavjud konteynerni almashtirmaydi. Yangilashdan oldin uning holatini ko‘rib, alohida reja tanlang. Bu faylning berilgani serverga deploy amalga oshirilganini anglatmaydi.
