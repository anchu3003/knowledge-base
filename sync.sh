#!/usr/bin/env bash
# ---------------------------------------------------------------------------
#  sync.sh | lam moi repo showcase (GitHub) tu 3 repo goc tren GitLab
# ---------------------------------------------------------------------------
#  - CHI DOC GitLab: clone sang /tmp, khong push, khong tao ref, khong doi gi.
#  - `git filter-repo` la deterministic => cac commit cu giu nguyen SHA sau
#    rewrite, nen lan sync sau chi la merge thuong (khong can force-push).
#  - Tai lieu ca nhan (`Interview/`) bi loai khoi TOAN BO lich su cua ban
#    public: bien STRIP_<REPO> (mac dinh be=Interview, fe/root=rong).
#
#  Dung:
#      ./sync.sh                # sync ca 3 repo roi push (neu co remote `github`)
#      ./sync.sh be             # chi 1 repo: be | fe | root
#      NO_PUSH=1 ./sync.sh      # sync, khong push
#      STRIP_BE=Interview       # (mac dinh) duong dan bi loai, cach nhau bang ','
#
#  Nguon co the override (mac dinh: duong dan local cua repo GitLab):
#      SRC_BE, SRC_FE, SRC_ROOT, REF (mac dinh: main), WORK (thu muc tam)
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WORK=${WORK:-/tmp/kb-showcase-sync}
REF=${REF:-main}
SRC_BE=${SRC_BE:-$HOME/mygit/personal-side-projects/knowledge-base/Knowledge-base}
SRC_FE=${SRC_FE:-$HOME/mygit/personal-side-projects/knowledge-base/Knowledge-base-fe}
SRC_ROOT=${SRC_ROOT:-$HOME/mygit/personal-side-projects/knowledge-base}
STRIP_BE=${STRIP_BE-Interview}
STRIP_FE=${STRIP_FE-}
STRIP_ROOT=${STRIP_ROOT-}

command -v git-filter-repo >/dev/null 2>&1 || {
  echo "thieu git-filter-repo:  uv tool install git-filter-repo" >&2; exit 2; }

sync_one() {
  local name=$1 src=$2 prefix=$3 strip=$4
  echo "==> $name   ($prefix/  <-  $src)"

  rm -rf "$WORK/$name"
  if [ -d "$src" ]; then
    git clone --quiet --no-local "$src" "$WORK/$name"
  else
    git clone --quiet "$src" "$WORK/$name"
  fi

  # 1) loai duong dan khong duoc public (truoc khi prefix)
  if [ -n "$strip" ]; then
    local IFS=,
    for path in $strip; do
      [ -n "$path" ] || continue
      echo "    strip: $path"
      git -C "$WORK/$name" filter-repo --invert-paths --path "$path" --force >/dev/null
    done
  fi

  # 2) dua moi thu vao thu muc con
  git -C "$WORK/$name" filter-repo --to-subdirectory-filter "$prefix" --force >/dev/null

  git -C "$ROOT_DIR" remote add "$name" "$WORK/$name"
  git -C "$ROOT_DIR" fetch --quiet "$name"
  if git -C "$ROOT_DIR" merge --no-edit "$name/$REF"; then
    echo "    ok: merged $name/$REF"
  else
    echo "    LOI: conflict - sua tay trong $ROOT_DIR (remote '$name' van con)" >&2
    exit 1
  fi
  git -C "$ROOT_DIR" remote remove "$name"
}

mkdir -p "$WORK"

case "${1:-all}" in
  be)   sync_one be   "$SRC_BE"   Knowledge-base    "$STRIP_BE" ;;
  fe)   sync_one fe   "$SRC_FE"   Knowledge-base-fe "$STRIP_FE" ;;
  root) sync_one root "$SRC_ROOT" root              "$STRIP_ROOT" ;;
  all)  sync_one be   "$SRC_BE"   Knowledge-base    "$STRIP_BE"
        sync_one fe   "$SRC_FE"   Knowledge-base-fe "$STRIP_FE"
        sync_one root "$SRC_ROOT" root              "$STRIP_ROOT" ;;
  *)    echo "usage: ./sync.sh [all|be|fe|root]" >&2; exit 2 ;;
esac

if [ "${NO_PUSH:-0}" = "1" ]; then
  echo "NO_PUSH=1 - bo qua push"
  exit 0
fi

if git -C "$ROOT_DIR" remote get-url github >/dev/null 2>&1; then
  git -C "$ROOT_DIR" push github "$REF"
  echo "pushed -> github/$REF"
else
  echo "chua co remote 'github' - bo qua push"
fi

