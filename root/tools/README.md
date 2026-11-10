# tools/ — script hỗ trợ

Script tiện tay cho quy trình. Không phải source app. Xem `AGENTS.md` §10.

| File | Việc | Chạy |
|---|---|---|
| `pii_scan.py` | Quét PII/secret trong file (lưới an toàn trước commit) | `python tools/pii_scan.py <file\|dir>` |
| `verify.sh` | Gom lệnh verify BE + FE | `bash tools/verify.sh` |

## pii_scan.py

- Quét đệ quy được: `python tools/pii_scan.py .`
- Bỏ qua `.git/.venv/node_modules/.next/__pycache__/chroma_db`, file nhị phân.
- Bỏ qua thư mục `tests/` (test dùng dữ liệu **giả** theo quy ước — `.clinerules/30-pii-safety.md`).
- Bỏ qua dòng định nghĩa regex (`re.compile`, `pattern`) để không tự bắt chính scanner.
- Bỏ qua placeholder hợp lệ (`example.com`, `REDACTED`, `your_...`, `localhost`, `...`).
- Exit code `1` nếu có nghi vấn → tiện gắn vào pre-commit sau này.

Quy ước: **không** commit secret/PII (`.clinerules/30-pii-safety.md`). Nếu nghi lộ key → **rotate ngay**.
