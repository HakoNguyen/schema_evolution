"""Mức 2: xác thực API (auth.users trong main.yaml) và ghi lại ai là người duyệt."""
import asyncio
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from starlette.requests import Request
from starlette.responses import PlainTextResponse

import api.main as api
from app.event_log import event_logger
from app.scheduler import validate_main_config
from src.schema_evolution.core import SchemaRegistry
from src.schema_evolution.engines.base import ChangeSeverity, ChangeType, ColumnSchema, SchemaChange, TableSchema

ADMIN, REPORTER = "admin-token-0123456789", "loader-token-0123456789"
USERS = {"hieu": {"role": "admin", "token": ADMIN}, "loader": {"role": "reporter", "token": REPORTER}}


def _call(method: str, path: str, token: str | None = None, users=USERS) -> tuple[int, str | None]:
    """Chạy middleware như uvicorn; endpoint giả đọc user từ request.state như endpoint thật."""
    scope = {"type": "http", "method": method, "path": path, "query_string": b"", "state": {},
             "headers": [(b"authorization", f"Bearer {token}".encode())] if token else []}
    seen = {}

    async def call_next(request):
        seen["user"] = Request(request.scope).state.user
        return PlainTextResponse("ok")

    original = api.load_config
    api.load_config = lambda *a: {"auth": {"users": users}} if users else {}
    try:
        resp = asyncio.run(api.require_token(Request(scope), call_next))
    finally:
        api.load_config = original
    return resp.status_code, seen.get("user")


def test_middleware_roles():
    approve = "/api/tables/shop__orders/approve"
    assert _call("POST", approve, users=None) == (200, None)                  # chưa bật auth: như trước
    assert _call("GET", "/api/gate/shop/orders") == (200, None)              # đọc luôn mở
    assert _call("POST", approve)[0] == 401
    assert _call("POST", approve, "wrong-token-0123456789")[0] == 401
    assert _call("POST", approve, REPORTER)[0] == 403                        # data plane không được duyệt
    assert _call("PUT", "/api/config/pipelines/shop", REPORTER)[0] == 403
    assert _call("POST", "/api/pipelines/shop/components/loader", REPORTER) == (200, "loader")
    assert _call("POST", approve, ADMIN) == (200, "hieu")
    assert _call("DELETE", "/api/config/pipelines/shop", ADMIN) == (200, "hieu")
    print("[PASS] test_middleware_roles")


def test_auth_config_errors():
    base = {"registry": {"dir": "registry"}}
    assert validate_main_config({**base, "auth": {"users": USERS}}) == []
    for bad in ({"users": {}},
                {"users": {"a": {"role": "admin", "token": "short"}}},
                {"users": {"a": {"role": "root", "token": ADMIN}}},
                {"users": {"a": {"role": "admin", "token": ADMIN, "extra": 1}}},
                {"users": {"a": {"role": "admin", "token": ADMIN}, "b": {"role": "reporter", "token": ADMIN}}}):
        assert validate_main_config({**base, "auth": bad}), bad
    print("[PASS] test_auth_config_errors")


def test_reject_records_reviewer():
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as d:
        os.chdir(d)
        try:
            Path("config/pipelines").mkdir(parents=True)
            Path("config/main.yaml").write_text(
                f"registry: {{dir: '{(Path(d) / 'reg').as_posix()}'}}\ntelegram: {{bot_token: '', chat_id: ''}}\n",
                encoding="utf-8")
            reg = SchemaRegistry(str(Path(d) / "reg"))
            schema = TableSchema("orders", [ColumnSchema("id", "bigint", False)])
            reg.save("shop/orders", schema)
            reg.set_frozen("shop/orders", True)
            reg.save_draft("shop/orders", schema, [SchemaChange(
                "orders", ChangeType.DROP_COLUMN, ChangeSeverity.BREAKING, column_name="note")])

            result = api.reject_changes("shop__orders", SimpleNamespace(state=SimpleNamespace(user="hieu")))
            assert result == {"status": "success"}
            assert event_logger.get_events()[0]["ddl"].startswith("[review] Rejected by hieu:")
        finally:
            os.chdir(cwd)
    print("[PASS] test_reject_records_reviewer")


if __name__ == "__main__":
    test_middleware_roles()
    test_auth_config_errors()
    test_reject_records_reviewer()
