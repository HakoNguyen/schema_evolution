import os
import sys
import tempfile
import time
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import app.pipeline_manager as pm
from app.scheduler import load_pipeline_specs

GOOD = """
name: {name}
source: {{type: postgres, config: {{host: localhost, dbname: exchange}}}}
target: {{type: clickhouse, config: {{host: localhost, port: 8123, database: analytics}}}}
tables: [trades]
"""


class FakeWorker:
    """Thay PipelineWorker thật (không kết nối DB) để kiểm tra vòng đời."""
    events = []

    def __init__(self, spec, registry, notifier, global_cfg):
        self.spec, self.name, self.event_driven = spec, spec["name"], False

    def start(self):
        FakeWorker.events.append(("start", self.name))

    def stop(self):
        FakeWorker.events.append(("stop", self.name))


def _write(d: Path, file: str, text: str):
    p = d / file
    p.write_text(text, encoding="utf-8")
    t = time.time() + len(FakeWorker.events)  # mtime khác lần ghi trước
    os.utime(p, (t, t))


def test_load_specs_isolates_bad_files():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        _write(d, "a.yaml", GOOD.format(name="a"))
        _write(d, "broken.yaml", "name: [unclosed")
        _write(d, "badtype.yaml", GOOD.format(name="c").replace("postgres", "oracle"))
        _write(d, "dup.yaml", GOOD.format(name="a"))
        _write(d, "notables.yaml", "name: e\nsource: {type: postgres, config: {}}\n")
        specs, errors = load_pipeline_specs(d)
        assert [s["name"] for s in specs] == ["a"]
        assert set(errors) == {"broken.yaml", "badtype.yaml", "dup.yaml", "notables.yaml"}, errors
        assert "invalid YAML" in errors["broken.yaml"]
        assert "source.type" in errors["badtype.yaml"]
        assert "already used by a.yaml" in errors["dup.yaml"]
        assert "tables" in errors["notables.yaml"]
    print("[PASS] test_load_specs_isolates_bad_files")


def test_connection_fields_validated():
    from app.scheduler import validate_pipeline_spec
    import yaml
    ok = yaml.safe_load(GOOD.format(name="a"))
    assert validate_pipeline_spec(ok) == []
    bad = yaml.safe_load(GOOD.format(name="a"))
    bad["source"]["config"] = {"host": "", "dbname": "x", "database": "y", "port": "abc"}
    bad["target"]["config"].pop("port")
    errs = " | ".join(validate_pipeline_spec(bad))
    assert "source.config.host: required" in errs
    assert "both dbname and database" in errs
    assert "source.config.port: must be a number" in errs
    assert "target.config.port: required for clickhouse" in errs
    legacy = yaml.safe_load(GOOD.format(name="a"))
    legacy["source"]["config"] = {"host": "h", "database": "exchange"}  # psycopg2 nhận 'database' như alias
    assert validate_pipeline_spec(legacy) == []
    print("[PASS] test_connection_fields_validated")


def test_hot_reload_lifecycle():
    original = pm.PipelineWorker
    pm.PipelineWorker = FakeWorker
    FakeWorker.events = []
    try:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "pipelines").mkdir()
            (root / "main.yaml").write_text(f"registry: {{dir: '{(root / 'reg').as_posix()}'}}\n", encoding="utf-8")
            pipes = root / "pipelines"
            mgr = pm.PipelineManager(str(root / "main.yaml"))

            _write(pipes, "a.yaml", GOOD.format(name="a"))
            assert mgr.sync() and set(mgr.workers) == {"a"}
            assert not mgr.sync(), "không đổi file -> không làm gì"

            _write(pipes, "b.yaml", GOOD.format(name="b"))                 # thêm pipeline
            _write(pipes, "broken.yaml", "::: not yaml")                   # file hỏng
            mgr.sync()
            assert set(mgr.workers) == {"a", "b"} and "broken.yaml" in mgr.errors

            _write(pipes, "a.yaml", GOOD.format(name="a").replace("[trades]", "[trades, orders]"))  # sửa a
            FakeWorker.events.clear()
            mgr.sync()
            assert FakeWorker.events == [("stop", "a"), ("start", "a")], FakeWorker.events
            assert mgr.workers["a"].spec["tables"] == ["trades", "orders"]

            (pipes / "b.yaml").unlink()                                    # xoá b
            FakeWorker.events.clear()
            mgr.sync()
            assert FakeWorker.events == [("stop", "b")] and set(mgr.workers) == {"a"}
    finally:
        pm.PipelineWorker = original
    print("[PASS] test_hot_reload_lifecycle")


def test_main_yaml_reload():
    original = pm.PipelineWorker
    pm.PipelineWorker = FakeWorker
    FakeWorker.events = []
    try:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "pipelines").mkdir()
            reg = (root / "reg").as_posix()
            main = root / "main.yaml"
            base = f"registry: {{dir: '{reg}'}}\nscheduler: {{interval_seconds: 60}}\n"
            main.write_text(base, encoding="utf-8")
            _write(root / "pipelines", "a.yaml", GOOD.format(name="a"))
            mgr = pm.PipelineManager(str(main))
            mgr.sync()

            # Telegram đổi: thay notifier cho worker đang chạy, KHÔNG khởi động lại worker.
            FakeWorker.events.clear()
            _write(root, "main.yaml", base + "telegram: {bot_token: 't', chat_id: '1'}\n")
            mgr.sync()
            assert FakeWorker.events == [] and mgr.notifier.bot_token == "t"
            assert mgr.workers["a"].notifier is mgr.notifier

            # Chu kỳ quét đổi: worker khởi động lại để nhận giá trị mới.
            _write(root, "main.yaml", base.replace("60", "30") + "telegram: {bot_token: 't', chat_id: '1'}\n")
            mgr.sync()
            assert FakeWorker.events == [("stop", "a"), ("start", "a")], FakeWorker.events

            # File hỏng: giữ cấu hình đang chạy, báo lỗi, worker không bị đụng tới.
            FakeWorker.events.clear()
            _write(root, "main.yaml", "registry: [broken")
            mgr.sync()
            assert FakeWorker.events == [] and "last valid config" in mgr.main_error
            assert mgr.global_cfg["scheduler"]["interval_seconds"] == 30
            assert "main.yaml" in mgr.snapshot()["pipeline_errors"]

            # registry.dir đổi: không áp dụng khi đang chạy, báo cần khởi động lại.
            _write(root, "main.yaml", base.replace(reg, reg + "_new").replace("60", "30"))
            mgr.sync()
            assert "needs a restart" in mgr.main_error and mgr.global_cfg["registry"]["dir"] == reg
    finally:
        pm.PipelineWorker = original
    print("[PASS] test_main_yaml_reload")


if __name__ == "__main__":
    test_load_specs_isolates_bad_files()
    test_connection_fields_validated()
    test_hot_reload_lifecycle()
    test_main_yaml_reload()
    print("\nALL PIPELINE MANAGER TESTS PASSED!")
