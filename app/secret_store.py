"""
Bí mật (mật khẩu DB, token) KHÔNG nằm trong file YAML được commit.

YAML chỉ chứa tham chiếu:   password: ${EXCHANGE_PG_PASSWORD}
Giá trị thật lấy từ (ưu tiên giảm dần): biến môi trường thật > config/secrets.env (gitignored).

- Engine thay giá trị thật vào lúc tạo kết nối (resolve), không bao giờ ghi ngược ra file.
- API/UI chỉ thấy tham chiếu; giá trị viết thẳng trong YAML (kiểu cũ) bị che thành MASK
  và được giữ nguyên khi lưu lại (unmask).
"""
import os
import re
from pathlib import Path

SECRETS_FILE = "secrets.env"
MASK = "********"
SECRET_KEYS = {"password", "bot_token", "sasl_plain_password", "token", "secret", "api_key"}
_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def secrets_path(config_dir: Path) -> Path:
    return Path(config_dir) / SECRETS_FILE


def load_env(config_dir: Path) -> dict[str, str]:
    """config/secrets.env (KEY=VALUE, # là comment) rồi đè bằng biến môi trường thật."""
    values: dict[str, str] = {}
    path = secrets_path(config_dir)
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[key.strip()] = value
    return {**values, **os.environ}


def resolve(value, env: dict[str, str], missing: set[str]):
    """Thay mọi ${VAR} trong chuỗi/dict/list; tên biến không có giá trị được thêm vào missing."""
    if isinstance(value, dict):
        return {k: resolve(v, env, missing) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(v, env, missing) for v in value]
    if isinstance(value, str):
        def sub(m):
            if m.group(1) in env:
                return env[m.group(1)]
            missing.add(m.group(1))
            return m.group(0)
        return _REF.sub(sub, value)
    return value


def missing_error(missing: set[str]) -> str:
    return (f"missing secret(s): {', '.join(sorted(missing))} — "
            f"define in config/{SECRETS_FILE} or as environment variables")


def _is_literal_secret(key, value) -> bool:
    return key in SECRET_KEYS and isinstance(value, str) and value != "" and not _REF.fullmatch(value)


def mask(value):
    """Che giá trị bí mật viết thẳng (không phải ${VAR}) trước khi trả về cho UI."""
    if isinstance(value, dict):
        return {k: MASK if _is_literal_secret(k, v) else mask(v) for k, v in value.items()}
    if isinstance(value, list):
        return [mask(v) for v in value]
    return value


def unmask(new, old):
    """UI gửi lại MASK = "không đổi": lấy lại giá trị cũ từ file, không ghi chuỗi MASK ra đĩa."""
    if isinstance(new, dict):
        old = old if isinstance(old, dict) else {}
        return {k: (old.get(k) if v == MASK and k in SECRET_KEYS else unmask(v, old.get(k))) for k, v in new.items()}
    if isinstance(new, list):
        return [unmask(v, None) for v in new]
    return new
