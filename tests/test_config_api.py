"""Kiểm tra các API ghi cấu hình (gọi thẳng hàm endpoint, trong thư mục tạm)."""
import os
import sys
import tempfile
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import yaml
from fastapi import HTTPException

import api.main as api

SPEC = {
    "name": "orders_sync",
    "detection": {"mode": "polling"},
    "source": {"type": "postgres", "config": {"host": "localhost", "port": 5432, "dbname": "shop",
                                                 "user": "u", "password": "p"}},
    "target": {"type": "clickhouse", "config": {"host": "localhost", "port": 8123, "database": "dw"}},
    "tables": ["orders"],
}


def _expect(status: int, fn, *args) -> dict:
    try:
        fn(*args)
    except HTTPException as e:
        assert e.status_code == status, (e.status_code, e.detail)
        return e.detail
    raise AssertionError(f"expected HTTP {status}")


def test_pipeline_config_api():
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as d:
        os.chdir(d)
        try:
            Path("config/pipelines").mkdir(parents=True)
            # Hợp lệ -> ghi file, đọc lại đúng nội dung, giữ thứ tự khoá.
            api.create_pipeline_config(dict(SPEC))
            saved = yaml.safe_load(Path("config/pipelines/orders_sync.yaml").read_text(encoding="utf-8"))
            assert saved == SPEC and list(saved) == list(SPEC)
            assert not list(Path("config/pipelines").glob("*.tmp")), "không để lại file tạm"

            _expect(409, api.create_pipeline_config, dict(SPEC))                          # trùng tên
            bad = {**SPEC, "name": "x", "source": {"type": "postgres", "config": {"host": ""}}}
            detail = _expect(422, api.create_pipeline_config, bad)                        # thiếu host/dbname
            assert any("host" in e for e in detail["errors"]) and any("dbname" in e for e in detail["errors"])
            _expect(422, api.create_pipeline_config, {**SPEC, "name": "../evil"})          # tên chứa đường dẫn

            # Sửa: giữ nguyên tên; đổi tên bị chặn; tên trên URL phải hợp lệ.
            api.update_pipeline_config("orders_sync", {**SPEC, "tables": ["orders", "items"]})
            assert yaml.safe_load(Path("config/pipelines/orders_sync.yaml").read_text(encoding="utf-8"))["tables"] == ["orders", "items"]
            _expect(422, api.update_pipeline_config, "orders_sync", {**SPEC, "name": "renamed"})
            _expect(404, api.update_pipeline_config, "missing", {**SPEC, "name": "missing"})
            _expect(400, api.update_pipeline_config, "..", {**SPEC, "name": ".."})

            _expect(400, api.delete_pipeline_config, "..")
            api.delete_pipeline_config("orders_sync")
            assert not Path("config/pipelines/orders_sync.yaml").exists()
            _expect(404, api.delete_pipeline_config, "orders_sync")

            # main.yaml: sai -> 422, file cũ không bị đụng tới.
            Path("config/main.yaml").write_text("registry: {dir: ./data/registry}\n", encoding="utf-8")
            _expect(422, api.update_system_config, {"registry": {}, "scheduler": {"interval_seconds": -1}})
            assert "dir" in Path("config/main.yaml").read_text(encoding="utf-8")
            api.update_system_config({"registry": {"dir": "./data/registry"}, "scheduler": {"interval_seconds": 30}, "_error": "x"})
            assert yaml.safe_load(Path("config/main.yaml").read_text(encoding="utf-8"))["scheduler"]["interval_seconds"] == 30
        finally:
            os.chdir(cwd)
    print("[PASS] test_pipeline_config_api")


if __name__ == "__main__":
    test_pipeline_config_api()
    print("\nALL CONFIG API TESTS PASSED!")
