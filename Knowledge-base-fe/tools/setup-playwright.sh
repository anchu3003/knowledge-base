#!/usr/bin/env bash
# Cài Playwright + Chromium **không cần sudo** (KB-4.9).
#
# Vì sao cần script: Chromium cần 4 lib X11 mà Ubuntu 26.04 minimal (WSL) không có sẵn:
#   libXcomposite, libXdamage, libXfixes, libXrandr
# `npx playwright install --with-deps` sẽ gọi apt (cần root). Cách không cần root:
#   1. `apt-get download` các .deb (chỉ tải, không cài)
#   2. `dpkg -x` bung vào ~/.local/pw-libs
#   3. `playwright.config.ts` trỏ `LD_LIBRARY_PATH` cho **process browser** (launchOptions.env)
#
# Dùng: bash tools/setup-playwright.sh   (chạy 1 lần; idempotent)
set -uo pipefail

ROOT="${PW_LIBS_ROOT:-$HOME/.local/pw-libs}"
LIBS="libxcomposite1 libxdamage1 libxfixes3 libxrandr2"

echo "== 1/3 Tải lib X11 còn thiếu vào $ROOT =="
mkdir -p "$ROOT" && cd "$ROOT" || exit 1
missing=""
for pkg in $LIBS; do
    case "$pkg" in
        libxcomposite1) so=libXcomposite.so.1 ;;
        libxdamage1) so=libXdamage.so.1 ;;
        libxfixes3) so=libXfixes.so.3 ;;
        libxrandr2) so=libXrandr.so.2 ;;
    esac
    if [ -e "$ROOT/root/usr/lib/x86_64-linux-gnu/$so" ]; then
        echo "  ✓ $pkg (đã có)"
    else
        missing="$missing $pkg"
    fi
done
if [ -n "$missing" ]; then
    echo "  → tải:$missing"
    apt-get download $missing >/dev/null 2>&1 || { echo "Tải .deb thất bại (mạng?)" >&2; exit 1; }
    for f in ./*.deb; do dpkg -x "$f" root || exit 1; done
    rm -f ./*.deb
    echo "  ✓ đã bung .deb vào $ROOT/root"
fi

echo "== 2/3 Cài package @playwright/test + Chromium =="
cd "$(dirname "$0")/.." || exit 1
npm ls @playwright/test >/dev/null 2>&1 || npm i -D @playwright/test
npx playwright install chromium chromium-headless-shell

echo "== 3/3 Chạy thử =="
npm run test:e2e || true
echo
echo "Xong. Lệnh dùng hằng ngày:"
echo "  npm run test:e2e                          # verify UI trên container (:3010)"
echo "  APP_URL=http://localhost:3000 npm run test:e2e   # verify khi đang 'npm run dev' (:3000)"
