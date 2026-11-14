#!/usr/bin/env bash
# verify.sh — gom lệnh verify BE + FE. Chạy trong WSL (môi trường dev chuẩn — KB-7.1).
# Đọc output THẬT rồi dán vào ticket (skill kb-verify).
#
# Dùng: bash tools/verify.sh
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BE="$ROOT/Knowledge-base"
FE="$ROOT/Knowledge-base-fe"
PY_SYS="$(command -v python3 || command -v python)"

echo "== [1] PII scan (file git-tracked của 2 repo) =="
# Chỉ quét file TRACKED (đúng phạm vi có thể commit) → không đọc .env / artifact local.
for repo in "$BE" "$FE"; do
  if [ -d "$repo/.git" ]; then
    echo "-- $(basename "$repo")"
    ( cd "$repo" && git ls-files -z | xargs -0 -r "$PY_SYS" "$ROOT/tools/pii_scan.py" ) || true
  fi
done

echo
echo "== [2] BE: unit test =="
if [ -d "$BE" ]; then
  if [ -x "$BE/.venv/bin/python" ]; then
    ( cd "$BE" && .venv/bin/python -m pytest -q 2>&1 | tail -n 20 )
  else
    ( cd "$BE" && "$PY_SYS" -m pytest -q 2>&1 | tail -n 20 ) \
      || echo "(pytest chưa cài — tạo venv: uv venv --python 3.13 .venv && uv pip install -r requirements.txt -r requirements-dev.txt)"
  fi
else
  echo "skip: không thấy $BE"
fi

echo
echo "== [3] FE: build =="
if [ -d "$FE" ]; then
  # Node cài qua fnm (KB-7.1): nếu chưa có trong PATH thì thử load fnm.
  if ! command -v npm >/dev/null 2>&1 && [ -x "$HOME/.local/share/fnm/fnm" ]; then
    eval "$("$HOME/.local/share/fnm/fnm" env 2>/dev/null)" || true
  fi
  ( cd "$FE" && npm run build 2>&1 | tail -n 20 ) || echo "(build fail — xem output)"
else
  echo "skip: không thấy $FE"
fi

echo
echo "== [4] Docker (BE, tuỳ chọn) =="
if command -v docker >/dev/null 2>&1; then
  echo "docker build -t kb-be:local .   # trong Knowledge-base/ (~6 phút lần đầu)"
  echo "docker run --rm kb-be:local python -c 'from app.main import app; print(app.title)'"
else
  echo "skip: không có docker CLI"
fi

echo
echo "== [5] Gợi ý chạy app =="
cat <<'EOF'
BE:  cd Knowledge-base && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
     curl http://localhost:8000/            # health
     curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d "{\"message\":\"hello\"}"
FE:  cd Knowledge-base-fe && npm run dev     # http://localhost:3000
EOF
