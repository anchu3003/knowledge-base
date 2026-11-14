#!/usr/bin/env bash
# setup-wsl-docker-engine.sh — KB-7.1 (migrate dev env sang WSL)
#
# Cài Docker Engine (docker-ce) TRỰC TIẾP trong distro WSL Ubuntu, thay cho
# Docker Desktop WSL integration (symlink /usr/bin/docker → /mnt/wsl/docker-desktop/...).
#
# Cách chạy:
#   sudo bash tools/setup-wsl-docker-engine.sh
#
# Trước khi chạy (khuyến nghị): Docker Desktop → Settings → Resources → WSL integration
#   → TẮT cho distro Ubuntu (nếu không Desktop sẽ tạo lại symlink + bind-mount socket).
set -euo pipefail

log() { printf '\n==> %s\n' "$*"; }

if [ "$(id -u)" -ne 0 ]; then
  echo "Phải chạy bằng sudo: sudo bash $0" >&2
  exit 1
fi

REAL_USER="${SUDO_USER:-$USER}"

log "1/6 — Xoá CLI symlink do Docker Desktop WSL integration tạo (nếu có)"
for f in /usr/bin/docker /usr/bin/docker-compose /usr/bin/docker-credential-desktop.exe /usr/local/bin/kubectl; do
  if [ -L "$f" ]; then
    rm -f "$f"
    echo "  removed symlink $f"
  fi
done

log "2/6 — Cài dependency"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl gnupg

log "3/6 — Thêm Docker apt repo (fallback codename nếu distro quá mới)"
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

CODENAME=$(. /etc/os-release && echo "${VERSION_CODENAME:-noble}")
CHOSEN=""
for c in "$CODENAME" noble jammy; do
  if curl -fsSLI "https://download.docker.com/linux/ubuntu/dists/$c/Release" >/dev/null 2>&1; then
    CHOSEN="$c"
    break
  fi
done
if [ -z "$CHOSEN" ]; then
  echo "Không tìm được dists Docker phù hợp cho $CODENAME" >&2
  exit 1
fi
echo "  distro codename=$CODENAME → dùng repo '$CHOSEN'"

ARCH=$(dpkg --print-architecture)
echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $CHOSEN stable" \
  > /etc/apt/sources.list.d/docker.list

log "4/6 — Cài docker-ce + buildx + compose plugin"
apt-get update -qq
apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

log "5/6 — Bật service (systemd đã bật trong /etc/wsl.conf) + thêm user vào group docker"
systemctl enable --now docker
usermod -aG docker "$REAL_USER" || true

log "6/6 — Verify"
docker --version
docker run --rm hello-world

cat <<'EOF'

XONG. Lưu ý:
  - Docker Desktop → Settings → Resources → WSL integration: TẮT cho distro Ubuntu,
    nếu không Desktop sẽ tạo lại symlink /usr/bin/docker và bind-mount /var/run/docker.sock.
  - Mở terminal MỚI (để group docker có hiệu lực) rồi kiểm tra:
      docker info | head -20
      systemctl is-active docker
EOF
