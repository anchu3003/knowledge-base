#!/usr/bin/env bash
# UI verification bằng **Chrome thật** (KB-4.9 follow-up) — chạy từ WSL.
#
# Tại sao cần script này:
#   - Chrome/Edge trên Windows chỉ mở DevTools ở `127.0.0.1:9222` (Chrome mới bỏ qua
#     `--remote-debugging-address=0.0.0.0`) ⇒ tiến trình trong WSL **không** kết nối được cổng đó.
#   - `node.exe` trên Windows thì gọi được cả `127.0.0.1:9222` (CDP) và `localhost:3010` (WSL forward).
#   ⇒ driver (`tools/ui-verify.mjs`) chạy bằng node.exe, script này lo bật/tắt Chrome headless.
#
# Dùng:
#   bash tools/ui-verify.sh                    # tự bật Chrome headless nếu CDP chưa có
#   APP_URL=http://localhost:3010 bash tools/ui-verify.sh
#   OUT_DIR='C:\Temp\shots' bash tools/ui-verify.sh
set -uo pipefail

CHROME='/mnt/c/Program Files/Google/Chrome/Application/chrome.exe'
NODE='/mnt/c/Program Files/nodejs/node.exe'
PROFILE='C:\Temp\kb-ui-verify-profile'
PORT="${CDP_PORT:-9222}"
STARTED=0

if [ ! -x "$CHROME" ]; then
    echo "Không thấy Chrome ở: $CHROME" >&2
    exit 3
fi
if [ ! -x "$NODE" ]; then
    echo "Không thấy node.exe ở: $NODE (cài Node cho Windows hoặc sửa biến NODE)" >&2
    exit 3
fi

# WSL không curl được cổng của Windows ⇒ kiểm bằng netstat.exe
# Lưu ý: KHÔNG dùng `netstat.exe | grep -q` với `pipefail` — `grep -q` thoát sớm làm netstat bị SIGPIPE (141)
# và pipeline trả non-zero dù đã match. Capture output rồi so khớp bằng pattern của bash.
cdp_up() {
    local out line
    out=$(netstat.exe -an 2>/dev/null)
    # so khớp TỪNG DÒNG: ":9222" và LISTENING phải cùng một dòng (pattern trên cả blob dễ khớp sai
    # sang dòng TIME_WAIT của kết nối cũ).
    while IFS= read -r line; do
        case "$line" in
            *":${PORT} "*LISTENING*) return 0 ;;
        esac
    done <<< "$out"
    return 1
}

# Đóng instance headless do lần chạy trước để lại (nhận diện bằng user-data-dir riêng, KHÔNG đụng
# Chrome user đang dùng).
kill_stale_verify_chrome() {
    powershell.exe -NoProfile -Command "
        Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" |
        Where-Object { \$_.CommandLine -like '*kb-ui-verify-profile*' } |
        ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }
    " >/dev/null 2>&1 || true
}

if ! cdp_up; then
    echo "Bật Chrome headless (CDP :${PORT})..."
    kill_stale_verify_chrome
    sleep 1
    ( cd /mnt/c && "$CHROME" --headless=new --disable-gpu \
        --remote-debugging-port="$PORT" \
        --user-data-dir="$PROFILE" \
        --no-first-run --no-default-browser-check about:blank </dev/null >/tmp/kb-chrome.log 2>&1 & )
    STARTED=1
    for _ in $(seq 1 30); do
        cdp_up && break
        sleep 1
    done
    if ! cdp_up; then
        echo "Chrome không mở CDP :${PORT}. Xem /tmp/kb-chrome.log" >&2
        exit 4
    fi
fi

"$NODE" tools/ui-verify.mjs
RC=$?

# Chỉ đóng Chrome nếu chính script này bật (không đụng Chrome user đang dùng)
if [ "$STARTED" = "1" ]; then
    "$NODE" --input-type=module -e "
        const v = await (await fetch('http://127.0.0.1:${PORT}/json/version')).json();
        const ws = new WebSocket(v.webSocketDebuggerUrl);
        ws.onopen = () => { ws.send(JSON.stringify({id: 1, method: 'Browser.close'})); setTimeout(() => process.exit(0), 300); };
    " >/dev/null 2>&1 || true
fi

exit "$RC"
