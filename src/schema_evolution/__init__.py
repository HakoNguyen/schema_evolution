import sys

# Windows: stdout bị chuyển hướng (log file, service) mặc định cp1252/cp1258 -> print tiếng Việt
# ném UnicodeEncodeError giữa luồng xử lý (VD sau khi đã ALTER target nhưng trước khi ghi event).
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
