#!/usr/bin/env bash
# 지금 접속해 있는 서버(예: 이미 만든 Google Cloud VM)에 바로 설치 / 업데이트합니다.
# Ubuntu / Debian 기준. sudo 권한이 필요합니다.
#
#   설치·업데이트:  bash install_vm.sh
#   설정 다시 입력: bash install_vm.sh --env
#
# 실제 설정은 저장소 밖의 /etc/screener.env 에 보관하고, 실행할 때마다 앱 폴더의 .env 로 복사합니다.
# (저장소에 .env 가 들어 있어도 서버 설정이 덮어써지지 않게 하기 위해서입니다.)
set -euo pipefail

REPO="${REPO:-https://github.com/jinmin888/stocks.git}"
BRANCH="${BRANCH:-master}"
APP_DIR="${APP_DIR:-/opt/stocks}"
ENV_FILE="${ENV_FILE:-/etc/screener.env}"
PORT=8000
MODE="${1:-install}"
SUDO=""; [ "$(id -u)" = "0" ] || SUDO="sudo"

meta() {  # Google Cloud 메타데이터 서버 (GCP VM 이 아니면 빈 값)
  curl -fsS -m 3 -H "Metadata-Flavor: Google" \
    "http://metadata.google.internal/computeMetadata/v1/instance/$1" 2>/dev/null || true
}

echo "== 1/5 스왑 · 기본 도구 =="
MEM_MB="$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)"
if [ "$MEM_MB" -lt 3500 ] && [ "$(swapon --noheadings 2>/dev/null | wc -l)" = "0" ] && [ ! -f /swapfile ]; then
  echo "메모리 ${MEM_MB}MB: 빌드 중 메모리 부족을 막기 위해 스왑 2GB 를 만듭니다."
  $SUDO fallocate -l 2G /swapfile && $SUDO chmod 600 /swapfile && $SUDO mkswap /swapfile >/dev/null \
    && $SUDO swapon /swapfile && echo '/swapfile none swap sw 0 0' | $SUDO tee -a /etc/fstab >/dev/null \
    || echo "스왑 생성 실패 (계속 진행합니다)" >&2
fi
export DEBIAN_FRONTEND=noninteractive
if ! command -v git >/dev/null || ! command -v curl >/dev/null; then
  $SUDO apt-get update -q && $SUDO apt-get install -y -q git curl
fi

echo "== 2/5 Docker =="
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | $SUDO sh
fi
$SUDO docker compose version >/dev/null 2>&1 || { echo "docker compose 를 사용할 수 없습니다. Docker 를 최신 버전으로 설치하세요." >&2; exit 1; }

echo "== 3/5 소스 받기 ($BRANCH) =="
if [ -d "$APP_DIR/.git" ]; then
  $SUDO git -C "$APP_DIR" fetch -q origin "$BRANCH"
  $SUDO git -C "$APP_DIR" checkout -q -f "$BRANCH"
  $SUDO git -C "$APP_DIR" reset -q --hard "origin/$BRANCH"
else
  $SUDO git clone -q --branch "$BRANCH" "$REPO" "$APP_DIR"
fi
echo "버전: $($SUDO git -C "$APP_DIR" log -1 --format='%h %s')"

echo "== 4/5 설정 =="
IP="$(meta network-interfaces/0/access-configs/0/external-ip)"
if [ -z "$IP" ]; then IP="$(curl -fsS -m 5 https://api.ipify.org 2>/dev/null || true)"; fi
if $SUDO test -f "$ENV_FILE" && [ "$MODE" != "--env" ]; then
  echo "기존 설정($ENV_FILE)을 그대로 사용합니다. 바꾸려면: bash install_vm.sh --env"
else
  if [ -z "$IP" ]; then read -r -p "이 서버의 외부 IP 또는 도메인: " IP; fi
  echo "설정을 입력하세요 (비밀번호는 화면에 표시되지 않습니다). 사이트 주소: http://$IP:$PORT"
  while true; do
    read -r -s -p "사이트 로그인 비밀번호 (8자 이상): " pw; echo
    read -r -s -p "한 번 더 입력: " pw2; echo
    case "$pw" in *"'"*) echo "작은따옴표(')는 사용할 수 없습니다."; continue ;; esac
    [ "$pw" = "$pw2" ] && [ "${#pw}" -ge 8 ] && break
    echo "비밀번호가 다르거나 8자보다 짧습니다. 다시 입력하세요."
  done
  read -r -p "KRX 아이디 (한국 주식 전체/지수 스캔용, 없으면 Enter): " krx_id
  krx_pw=""
  if [ -n "$krx_id" ]; then
    read -r -s -p "KRX 비밀번호: " krx_pw; echo
    case "$krx_pw" in *"'"*) echo "KRX 비밀번호에 작은따옴표(')가 있어 자동 설정할 수 없습니다. 나중에 $ENV_FILE 을 직접 수정하세요." >&2; krx_pw="" ;; esac
  fi
  read -r -p "Kakao REST API 키 (카카오톡 알림용, 없으면 Enter): " kakao
  kakao_secret=""
  if [ -n "$kakao" ]; then read -r -s -p "Kakao Client Secret (사용 안 하면 Enter): " kakao_secret; echo; fi
  read -r -p "카카오톡 메시지 언어 zh/ko [ko]: " lang
  TMP="$(mktemp)"; chmod 600 "$TMP"
  cat > "$TMP" <<EOF
APP_USERNAME=admin
APP_PASSWORD='$pw'
SECRET_KEY=$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')
PUBLIC_URL=http://$IP:$PORT
COOKIE_SECURE=0
KRX_ID=$krx_id
KRX_PW='$krx_pw'
KAKAO_REST_API_KEY=$kakao
KAKAO_CLIENT_SECRET='$kakao_secret'
NOTIFY_LANG=${lang:-ko}
DOMAIN=
EOF
  $SUDO install -m 600 -o root -g root "$TMP" "$ENV_FILE"
  rm -f "$TMP"
fi
$SUDO install -m 600 "$ENV_FILE" "$APP_DIR/.env"

echo "== 5/5 빌드 · 실행 (처음에는 5~10분 걸립니다) =="
(cd "$APP_DIR" && $SUDO docker compose up -d --build 2>&1 | tail -5)

OK=""
for _ in $(seq 1 30); do
  if out="$(curl -fsS -m 5 "http://localhost:$PORT/api/health" 2>/dev/null)"; then OK=1; echo "서비스 정상: $out"; break; fi
  sleep 5
done
[ -n "$OK" ] || { echo "서비스가 응답하지 않습니다. 로그: cd $APP_DIR && $SUDO docker compose logs --tail 50 app" >&2; exit 1; }

NAME="$(meta name)"; ZONE="$(meta zone)"; ZONE="${ZONE##*/}"
cat <<EOF

설치 완료
  주소:     http://${IP:-<서버IP>}:$PORT   (아이디 admin)
  업데이트: bash install_vm.sh
  설정변경: bash install_vm.sh --env
  로그:     cd $APP_DIR && $SUDO docker compose logs --tail 100 app
  카카오:   Redirect URI  http://${IP:-<서버IP>}:$PORT/api/kakao/callback ,  사이트 도메인  http://${IP:-<서버IP>}:$PORT
EOF
if [ -n "$NAME" ]; then
  cat <<EOF

브라우저에서 접속이 안 되면 방화벽에서 $PORT 포트를 열어야 합니다.
이 VM 안에서는 권한이 없으니, Google Cloud Shell(https://shell.cloud.google.com)에서 아래 두 줄을 실행하세요:

  gcloud compute firewall-rules create screener-allow-web --network default --allow tcp:$PORT,tcp:80,tcp:443 --target-tags screener --source-ranges 0.0.0.0/0
  gcloud compute instances add-tags $NAME --zone $ZONE --tags screener

참고: 외부 IP 가 '임시(ephemeral)'이면 VM 을 중지했다 켤 때 주소가 바뀝니다.
콘솔 → VPC 네트워크 → IP 주소에서 '고정(static)'으로 승격해 두세요.
EOF
fi
