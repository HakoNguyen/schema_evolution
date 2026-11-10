import os
import sys
import tempfile
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import yaml
from fastapi import HTTPException

from app.scheduler import load_pipeline_specs
from app.secret_store import MASK, load_env, mask, resolve, unmask

PIPE = """
name: shop
source: {type: postgres, config: {host: localhost, dbname: shop, user: u, password: "${SHOP_PG_PASSWORD}"}}
tables: [orders]
"""


def test_env_file_and_precedence():
    with tempfile.TemporaryDirectory() as d:
        Path(d, "secrets.env").write_text('# c\nA=1\nB="two words"\nC=\'x=y\'\n\nBAD LINE\n', encoding="utf-8")
        os.environ["B"] = "from-env"
        try:
            env = load_env(Path(d))
        finally:
            del os.environ["B"]
        assert env["A"] == "1" and env["B"] == "from-env" and env["C"] == "x=y"  # env thật thắng file
    missing = set()
    out = resolve({"a": "${A}", "b": ["jdbc://${H}:5432"], "n": 5}, {"A": "s", "H": "db"}, missing)
    assert out == {"a": "s", "b": ["jdbc://db:5432"], "n": 5} and not missing
    resolve({"x": "${NOPE}"}, {}, missing)
    assert missing == {"NOPE"}
    print("[PASS] test_env_file_and_precedence")


def test_pipeline_specs_resolve_and_isolate_missing():
    with tempfile.TemporaryDirectory() as d:
        pipes = Path(d, "pipelines")
        pipes.mkdir()
        (pipes / "shop.yaml").write_text(PIPE, encoding="utf-8")
        (pipes / "other.yaml").write_text(PIPE.replace("shop", "other").replace("SHOP_PG", "OTHER_PG"), encoding="utf-8")
        Path(d, "secrets.env").write_text("SHOP_PG_PASSWORD=s3cret\n", encoding="utf-8")
        specs, errors = load_pipeline_specs(pipes)
        assert [s["name"] for s in specs] == ["shop"]
        assert specs[0]["source"]["config"]["password"] == "s3cret"          # engine nhận giá trị thật
        assert "OTHER_PG_PASSWORD" in errors["other.yaml"]                    # thiếu bí mật chỉ hỏng pipeline đó
        assert "${SHOP_PG_PASSWORD}" in (pipes / "shop.yaml").read_text()     # file không bị ghi giá trị thật
    print("[PASS] test_pipeline_specs_resolve_and_isolate_missing")


def test_mask_unmask_roundtrip():
    stored = {"telegram": {"bot_token": "123:ABC", "chat_id": "9"},
              "source": {"config": {"password": "${PG}", "user": "u"}}}
    shown = mask(stored)
    assert shown["telegram"]["bot_token"] == MASK                 # giá trị viết thẳng bị che
    assert shown["source"]["config"]["password"] == "${PG}"       # tham chiếu thì không phải bí mật
    assert unmask(shown, stored) == stored                        # lưu lại không đổi gì
    edited = unmask({**shown, "telegram": {"bot_token": "NEW", "chat_id": "9"}}, stored)
    assert edited["telegram"]["bot_token"] == "NEW"
    print("[PASS] test_mask_unmask_roundtrip")


def test_api_never_exposes_or_overwrites_secret():
    import api.main as api
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as d:
        os.chdir(d)
        try:
            Path("config/pipelines").mkdir(parents=True)
            Path("config/secrets.env").write_text("SHOP_PG_PASSWORD=s3cret\n", encoding="utf-8")
            Path("config/main.yaml").write_text(
                "registry: {dir: ./reg}\ntelegram: {bot_token: '123:ABC', chat_id: '9'}\n", encoding="utf-8")
            sys_cfg = api.get_system_config()
            assert sys_cfg["telegram"]["bot_token"] == MASK
            api.update_system_config(sys_cfg)                                       # lưu lại y nguyên
            assert yaml.safe_load(Path("config/main.yaml").read_text())["telegram"]["bot_token"] == "123:ABC"

            api.create_pipeline_config(yaml.safe_load(PIPE))
            listed = api.get_pipelines_config()[0]
            assert listed["source"]["config"]["password"] == "${SHOP_PG_PASSWORD}"  # UI chỉ thấy tham chiếu
            bad = yaml.safe_load(PIPE.replace("shop", "nokey").replace("SHOP_PG", "NOKEY_PG"))
            try:
                api.create_pipeline_config(bad)
                raise AssertionError("expected 422")
            except HTTPException as e:
                assert e.status_code == 422 and "NOKEY_PG_PASSWORD" in e.detail["errors"][0]
        finally:
            os.chdir(cwd)
    print("[PASS] test_api_never_exposes_or_overwrites_secret")


if __name__ == "__main__":
    test_env_file_and_precedence()
    test_pipeline_specs_resolve_and_isolate_missing()
    test_mask_unmask_roundtrip()
    test_api_never_exposes_or_overwrites_secret()
    print("\nALL SECRETS TESTS PASSED!")
