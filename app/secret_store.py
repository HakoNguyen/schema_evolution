"""
Bí mật (mật khẩu DB, token) KHÔNG nằm trong file YAML được commit.

YAML chỉ chứa tham chiếu:   password: ${EXCHANGE_PG_PASSWORD}
Giá trị thật lấy từ (ưu tiên giảm dần): biến môi trường thật > config/secrets.env (gitignored).

- Engine thay giá trị thật vào lúc tạo kết nối (resolve), không bao giờ ghi ngược ra file.
- API/UI chỉ thấy tham chiếu; giá trị viết thẳng trong YAML (kiểu cũ) bị che thành MASK
  và được giữ nguyên khi lưu lại (unmask).
- Mật khẩu thật gõ trên UI/API được chuyển vào secrets.env, YAML chỉ nhận ${VAR} (externalize).
"""
import os
import re
import threading
import time
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


_write_lock = threading.Lock()


def externalize(value, config_dir: Path, prefix: str = ""):
    """
    Thay mọi bí mật viết thẳng bằng ${VAR} và ghi giá trị thật vào config/secrets.env.
    Tên biến theo vị trí: pipeline "shop" + source.config.password -> SHOP_SOURCE_PASSWORD;
    main.yaml telegram.bot_token -> TELEGRAM_BOT_TOKEN. Lưu lại cùng chỗ = cập nhật cùng biến.
    shortcut: biến của pipeline đã xoá vẫn nằm lại trong secrets.env; dọn tay nếu cần.
    """
    found: dict[str, str] = {}

    def walk(v, path):
        if isinstance(v, dict):
            out = {}
            for k, x in v.items():
                if _is_literal_secret(k, x):
                    if "\n" in x or "\r" in x:
                        raise ValueError(f"{'.'.join(path + [k])}: secret cannot contain line breaks")
                    name = re.sub(r"[^A-Z0-9_]", "_", "_".join([prefix, *path, k]).upper()).strip("_")
                    name = name if not name[0].isdigit() else f"P_{name}"
                    found[name] = x
                    out[k] = "${" + name + "}"
                else:
                    out[k] = walk(x, path if k == "config" else path + [k])
            return out
        if isinstance(v, list):
            return [walk(x, path) for x in v]
        return v

    result = walk(value, [])
    if found:
        _save(config_dir, found)
    return result


def _save(config_dir: Path, values: dict[str, str]) -> None:
    """Cập nhật/thêm KEY="value" trong secrets.env, giữ nguyên các dòng khác; ghi atomic."""
    path = secrets_path(config_dir)
    with _write_lock:
        lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
        pending = dict(values)
        for i, line in enumerate(lines):
            key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
            if key in pending:
                lines[i] = f'{key}="{pending.pop(key)}"'
        lines += [f'{k}="{v}"' for k, v in pending.items()]
        atomic_write(path, "\n".join(lines) + "\n")


def atomic_write(path: Path, text: str) -> None:
    """
    Ghi file tạm rồi đổi tên: engine quét mỗi 3s không bao giờ đọc phải file ghi dở.
    Windows: file đang được mở để đọc -> os.replace báo PermissionError -> thử lại.
    Thất bại hẳn thì vẫn xoá file tạm (có thể chứa mật khẩu thật).
    """
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    try:
        for attempt in range(10):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(0.1)
    finally:
        tmp.unlink(missing_ok=True)


def unmask(new, old):
    """UI gửi lại MASK = "không đổi": lấy lại giá trị cũ từ file, không ghi chuỗi MASK ra đĩa."""
    if isinstance(new, dict):
        old = old if isinstance(old, dict) else {}
        return {k: (old.get(k) if v == MASK and k in SECRET_KEYS else unmask(v, old.get(k))) for k, v in new.items()}
    if isinstance(new, list):
        return [unmask(v, None) for v in new]
    return new
