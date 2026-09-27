#!/usr/bin/env bash
# Run manually on the existing Linux Docker server; no remote SSH is performed.
set -euo pipefail

fail() { printf 'Xato: %s\n' "$*" >&2; exit 1; }
usage() {
    printf 'Foydalanish: bash deploy/existing_server.sh SERVER_IP_YOKI_HOST\n' >&2
    printf 'Misol: bash deploy/existing_server.sh 167.99.245.20\n' >&2
    exit 2
}
[[ $# -eq 1 ]] || usage
public_host=$1
[[ "$public_host" =~ ^[A-Za-z0-9][A-Za-z0-9.-]*$ ]] || fail 'Faqat IP yoki domen kiriting; http://, port yoki yo‘l qo‘shmang.'

container_name=daemon-eye-demo
public_port=8088
image_tag="daemon-eye-demo:manual-$(date -u +%Y%m%d%H%M%S)-$$"
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$project_dir"
[[ -f Dockerfile && -f solution.py ]] || fail 'Loyiha Dockerfile yoki solution.py topilmadi.'
for required in docker curl ss python3; do
    command -v "$required" >/dev/null 2>&1 || fail "$required o‘rnatilmagan. Skript hech qanday paket o‘rnatmaydi."
done
docker info >/dev/null 2>&1 || fail 'Docker daemon bilan aloqa yoki ruxsat yo‘q. Docker holati va foydalanuvchi ruxsatini tekshiring.'

check_unused() {
    if docker container inspect "$container_name" >/dev/null 2>&1; then
        fail "$container_name konteyneri mavjud. U to‘xtatilmaydi va o‘chirilmaydi; avval holatini tekshiring."
    fi
    local listeners published
    listeners=$(ss -H -ltn "sport = :$public_port")
    [[ -z "$listeners" ]] || fail "TCP $public_port band. Boshqa servisga tegilmadi."
    published=$(docker ps --format '{{.Ports}}')
    [[ "$published" != *":${public_port}->"* ]] || fail "Docker TCP $public_port portini allaqachon egallagan."
}
check_unused

# Inspect this server instead of assuming that the advertised RAM is free.
if [[ -r /proc/meminfo ]]; then
    available_kib=$(awk '$1 == "MemAvailable:" {print $2}' /proc/meminfo)
    if [[ "$available_kib" =~ ^[0-9]+$ ]]; then
        printf 'Hozirgi MemAvailable: %s MiB\n' "$((available_kib / 1024))"
        (( available_kib >= 1572864 )) || fail 'Hozir 1536 MiB erkin RAM yo‘q; yig‘ish boshlanmadi. Boshqa servislar o‘zgartirilmadi.'
    fi
fi
printf 'Image joriy loyiha Dockerfile orqali yig‘iladi: %s\n' "$image_tag"
printf 'Yig‘ish internet, disk va vaqt talab qiladi. Ishlaydigan konteyner chegarasi: 1.5 CPU / 1536 MiB.\n'
docker build --tag "$image_tag" .

# Recheck after a potentially long build; Docker run also rejects port/name races.
check_unused
docker run --detach \
    --name "$container_name" \
    --restart unless-stopped \
    --cpus 1.5 \
    --memory 1536m \
    --memory-swap 1536m \
    --pids-limit 256 \
    --security-opt no-new-privileges:true \
    --log-driver json-file --log-opt max-size=10m --log-opt max-file=3 \
    --publish "0.0.0.0:${public_port}:5000" \
    --env PORT=5000 \
    --env OMP_NUM_THREADS=2 \
    --env MKL_NUM_THREADS=2 \
    "$image_tag" \
    gunicorn --bind 0.0.0.0:5000 --workers 1 --threads 2 --timeout 600 app:app

printf 'Mahalliy /health tekshirilmoqda...\n'
for attempt in $(seq 1 30); do
    if curl --fail --silent --show-error --max-time 3 "http://127.0.0.1:${public_port}/health" 2>/dev/null \
        | python3 -c 'import json,sys; p=json.load(sys.stdin); sys.exit(0 if p.get("status")=="ok" and p.get("model_ready") is True else 1)' 2>/dev/null; then
        printf '\nMahalliy servis va model fayli tekshiruvi muvaffaqiyatli.\n'
        printf 'Tashqi brauzerda tekshiring: http://%s:%s\n' "$public_host" "$public_port"
        printf 'Bu tekshiruv tashqi tarmoqdan kirish ochiqligini tasdiqlamaydi. Firewall o‘zgartirilmadi.\n'
        printf 'Log: docker logs --tail 100 %s\n' "$container_name"
        exit 0
    fi
    if [[ $(docker inspect --format '{{.State.Running}}' "$container_name") != true ]]; then
        break
    fi
    sleep 2
done
printf 'Health tekshiruvi o‘tmadi. Konteyner tekshirish uchun saqlandi; boshqa servislar o‘zgartirilmadi.\n' >&2
docker logs --tail 80 "$container_name" >&2 || true
exit 1
