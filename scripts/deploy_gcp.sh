#!/usr/bin/env bash
# Google Cloud VM 배포 / 업데이트 스크립트 — Google Cloud Shell 에서 실행합니다.
#
#   처음 배포:   bash deploy_gcp.sh
#   업데이트:    bash deploy_gcp.sh            (VM 이 이미 있으면 git pull + 재빌드만 수행)
#   설정 변경:   bash deploy_gcp.sh --env      (.env 를 다시 입력해서 교체)
#   삭제:        bash deploy_gcp.sh --delete   (VM, 고정 IP, 방화벽 규칙 삭제. 데이터도 삭제됨)
#
# 환경 변수로 바꿀 수 있는 값:
#   PROJECT (기본: gcloud 현재 프로젝트)   ZONE (기본: asia-northeast3-a, 서울)
#   NAME (기본: screener)                  MACHINE (기본: e2-small, 2GB)
#   DISK_GB (기본: 30)                     SOURCE_RANGES (기본: 0.0.0.0/0, 접속 허용 IP 대역)
#   REPO / BRANCH (기본: 이 저장소의 master)
set -euo pipefail

PROJECT="${PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}"
ZONE="${ZONE:-asia-northeast3-a}"
REGION="${ZONE%-*}"
NAME="${NAME:-screener}"
MACHINE="${MACHINE:-e2-small}"
DISK_GB="${DISK_GB:-30}"
SOURCE_RANGES="${SOURCE_RANGES:-0.0.0.0/0}"
REPO="${REPO:-https://github.com/jinmin888/stocks.git}"
BRANCH="${BRANCH:-master}"
APP_DIR=/opt/stocks
MODE="${1:-deploy}"

if [ -z "$PROJECT" ] || [ "$PROJECT" = "(unset)" ]; then
  echo "프로젝트가 설정되지 않았습니다. 먼저 실행하세요:  gcloud config set project <프로젝트ID>" >&2
  exit 1
fi
ACCOUNT="$(gcloud config get-value account 2>/dev/null || true)"
case "$ACCOUNT" in *gserviceaccount.com)
  cat >&2 <<EOF
지금은 서비스 계정($ACCOUNT)으로 로그인되어 있습니다. VM 안에서 실행한 것으로 보입니다.
VM 의 서비스 계정은 새 VM 을 만들 권한이 없습니다. 둘 중 하나를 선택하세요:
  1) 지금 이 VM 에 바로 설치:
       curl -fsSLO https://raw.githubusercontent.com/jinmin888/stocks/master/scripts/install_vm.sh && bash install_vm.sh
  2) 새 VM 을 만들려면 Google Cloud Shell(https://shell.cloud.google.com)에서 이 스크립트를 실행
EOF
  exit 1 ;;
esac
G=(gcloud --project "$PROJECT" --quiet)
ssh_vm() { "${G[@]}" compute ssh "$NAME" --zone "$ZONE" --command "$1"; }
vm_exists() { "${G[@]}" compute instances describe "$NAME" --zone "$ZONE" >/dev/null 2>&1; }

echo "프로젝트: $PROJECT | 영역: $ZONE | VM: $NAME ($MACHINE, ${DISK_GB}GB)"

# ---------------------------------------------------------------- 삭제
if [ "$MODE" = "--delete" ]; then
  read -r -p "VM '$NAME' 과 데이터(스캔 기록 포함)를 모두 삭제합니다. 계속하려면 '$NAME' 입력: " ans
  [ "$ans" = "$NAME" ] || { echo "취소했습니다."; exit 1; }
  "${G[@]}" compute instances delete "$NAME" --zone "$ZONE" || true
  "${G[@]}" compute addresses delete "$NAME-ip" --region "$REGION" || true
  "${G[@]}" compute firewall-rules delete "$NAME-allow-web" || true
  echo "삭제했습니다."
  exit 0
fi

# ---------------------------------------------------------------- .env 입력
make_env() {
  local ip="$1" out="$2" pw pw2 krx_id krx_pw kakao kakao_secret lang
  echo
  echo "== 설정 입력 (비밀번호는 화면에 표시되지 않습니다) =="
  while true; do
    read -r -s -p "사이트 로그인 비밀번호 (APP_PASSWORD, 8자 이상): " pw; echo
    read -r -s -p "한 번 더 입력: " pw2; echo
    case "$pw" in *"'"*) echo "작은따옴표(')는 사용할 수 없습니다."; continue ;; esac
    [ "$pw" = "$pw2" ] && [ "${#pw}" -ge 8 ] && break
    echo "비밀번호가 다르거나 8자보다 짧습니다. 다시 입력하세요."
  done
  read -r -p "KRX 아이디 (한국 주식 전체/지수 스캔용, 없으면 Enter): " krx_id
  krx_pw=""
  if [ -n "$krx_id" ]; then
    read -r -s -p "KRX 비밀번호: " krx_pw; echo
    case "$krx_pw" in *"'"*) echo "KRX 비밀번호에 작은따옴표(')가 있어 자동 설정할 수 없습니다. 배포 후 VM 의 $APP_DIR/.env 를 직접 수정하세요." >&2; krx_pw="" ;; esac
  fi
  read -r -p "Kakao REST API 키 (카카오톡 알림용, 없으면 Enter): " kakao
  kakao_secret=""
  if [ -n "$kakao" ]; then read -r -s -p "Kakao Client Secret (사용 안 하면 Enter): " kakao_secret; echo; fi
  read -r -p "카카오톡 메시지 언어 zh/ko [ko]: " lang
  umask 077
  cat > "$out" <<EOF
APP_USERNAME=admin
APP_PASSWORD='$pw'
SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))")
PUBLIC_URL=http://$ip:8000
COOKIE_SECURE=0
KRX_ID=$krx_id
KRX_PW='$krx_pw'
KAKAO_REST_API_KEY=$kakao
KAKAO_CLIENT_SECRET='$kakao_secret'
NOTIFY_LANG=${lang:-ko}
DOMAIN=
EOF
}

push_env() {
  local tmp
  tmp="$(mktemp)"
  make_env "$1" "$tmp"
  "${G[@]}" compute scp "$tmp" "$NAME:/tmp/screener.env" --zone "$ZONE"
  rm -f "$tmp"
  ssh_vm "sudo install -m 600 -o root -g root /tmp/screener.env $APP_DIR/.env && rm -f /tmp/screener.env"
}

start_app() {
  echo "== 이미지 빌드 및 실행 (처음에는 5~10분 걸립니다) =="
  # 저장소에 .env 가 들어 있어도 VM 의 실제 설정을 덮어쓰지 않도록, 코드 갱신 전후로 보관했다가 되돌립니다.
  ssh_vm "cd $APP_DIR && sudo cp -p .env /root/.screener.env && sudo git fetch -q origin $BRANCH && sudo git checkout -q -f $BRANCH && sudo git reset -q --hard origin/$BRANCH && sudo cp -p /root/.screener.env .env && sudo docker compose up -d --build 2>&1 | tail -5"
}

wait_health() {
  local ip="$1"
  echo "== 서비스 응답 확인 =="
  for _ in $(seq 1 30); do
    if out="$(curl -fsS -m 5 "http://$ip:8000/api/health" 2>/dev/null)"; then
      echo "정상: $out"
      return 0
    fi
    sleep 5
  done
  echo "아직 응답이 없습니다. 로그 확인:  gcloud compute ssh $NAME --zone $ZONE --command 'cd $APP_DIR && sudo docker compose logs --tail 50 app'" >&2
  return 1
}

# ---------------------------------------------------------------- 업데이트 / 설정 변경
if vm_exists; then
  IP="$("${G[@]}" compute instances describe "$NAME" --zone "$ZONE" --format='get(networkInterfaces[0].accessConfigs[0].natIP)')"
  echo "VM 이 이미 있습니다 ($IP)."
  if [ "$MODE" = "--env" ]; then push_env "$IP"; fi
  start_app
  wait_health "$IP"
  echo "완료: http://$IP:8000"
  exit 0
fi
[ "$MODE" = "--env" ] && { echo "VM 이 없습니다. 먼저 배포하세요." >&2; exit 1; }

# ---------------------------------------------------------------- 새로 만들기
echo "== Compute Engine API 사용 설정 =="
"${G[@]}" services enable compute.googleapis.com

echo "== 고정 IP =="
"${G[@]}" compute addresses describe "$NAME-ip" --region "$REGION" >/dev/null 2>&1 \
  || "${G[@]}" compute addresses create "$NAME-ip" --region "$REGION"
IP="$("${G[@]}" compute addresses describe "$NAME-ip" --region "$REGION" --format='get(address)')"
echo "IP: $IP"

echo "== 방화벽 (8000, 80, 443 ← $SOURCE_RANGES) =="
"${G[@]}" compute firewall-rules describe "$NAME-allow-web" >/dev/null 2>&1 \
  || "${G[@]}" compute firewall-rules create "$NAME-allow-web" --network default \
       --allow tcp:8000,tcp:80,tcp:443 --target-tags "$NAME" --source-ranges "$SOURCE_RANGES"

# VM 첫 부팅 때 root 로 실행되는 스크립트: 스왑, Docker, 소스 받기. 비밀 정보는 넣지 않습니다.
STARTUP="$(mktemp)"
cat > "$STARTUP" <<EOF
#!/bin/bash
set -e
[ -f /var/lib/screener-ready ] && exit 0
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
export DEBIAN_FRONTEND=noninteractive
command -v git >/dev/null || { apt-get update -q && apt-get install -y -q git; }
command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh
[ -d $APP_DIR/.git ] || git clone -q --branch $BRANCH $REPO $APP_DIR
touch /var/lib/screener-ready
EOF

echo "== VM 생성 =="
"${G[@]}" compute instances create "$NAME" --zone "$ZONE" --machine-type "$MACHINE" \
  --image-family ubuntu-2404-lts-amd64 --image-project ubuntu-os-cloud \
  --boot-disk-size "${DISK_GB}GB" --boot-disk-type pd-balanced \
  --address "$IP" --tags "$NAME" --metadata-from-file startup-script="$STARTUP"
rm -f "$STARTUP"

echo "== VM 준비 대기 (Docker 설치, 2~4분) =="
for i in $(seq 1 60); do
  if ssh_vm "test -f /var/lib/screener-ready" 2>/dev/null; then break; fi
  [ "$i" = 60 ] && { echo "VM 준비가 끝나지 않았습니다. 시리얼 로그 확인: gcloud compute instances get-serial-port-output $NAME --zone $ZONE | tail -40" >&2; exit 1; }
  sleep 10
done

push_env "$IP"
start_app
wait_health "$IP"

cat <<EOF

배포 완료
  주소:     http://$IP:8000   (아이디 admin, 방금 입력한 비밀번호)
  업데이트: bash deploy_gcp.sh
  설정변경: bash deploy_gcp.sh --env
  로그:     gcloud compute ssh $NAME --zone $ZONE --command 'cd $APP_DIR && sudo docker compose logs --tail 100 app'
  카카오:   Kakao Developers 에 Redirect URI  http://$IP:8000/api/kakao/callback  와 사이트 도메인  http://$IP:8000  등록
EOF
