"""Mức 2-3: components: khai báo trong YAML — missing, lag consumer group, pause/resume Kafka Connect."""
import json
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app import runtime_status
from app.components import ObservedComponent
from app.pipeline_manager import PipelineWorker
from app.scheduler import validate_pipeline_spec


class FakeConnect(BaseHTTPRequestHandler):
    """Giả Kafka Connect REST: GET /connectors/x/status, PUT pause|resume, POST restart."""
    state, tasks, calls = "RUNNING", ["RUNNING"], []

    def _reply(self, code, body=None):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if body is not None:
            self.wfile.write(json.dumps(body).encode())

    def do_GET(self):
        cls = FakeConnect
        self._reply(200, {"name": "s", "connector": {"state": cls.state},
                          "tasks": [{"id": i, "state": s} for i, s in enumerate(cls.tasks)]})

    def do_PUT(self):
        FakeConnect.calls.append(("PUT", self.path))
        FakeConnect.state = "PAUSED" if self.path.endswith("/pause") else "RUNNING"
        self._reply(202)

    def do_POST(self):
        FakeConnect.calls.append(("POST", self.path))
        FakeConnect.tasks = ["RUNNING" for _ in FakeConnect.tasks]
        self._reply(202, {})

    def log_message(self, *args):
        pass


def _server():
    FakeConnect.state, FakeConnect.tasks, FakeConnect.calls = "RUNNING", ["RUNNING"], []
    srv = HTTPServer(("127.0.0.1", 0), FakeConnect)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


class Notifier:
    def __init__(self):
        self.sent = []

    def send_message(self, text):
        self.sent.append(text)
        return True


class FakeLag:
    def __init__(self, result):
        self.result = result

    def read(self, group):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _component(pipeline, name):
    return next(c for c in runtime_status.get_components(pipeline) if c["name"] == name)


def _sink(pipeline, url, connector="trades jdbc", **extra):
    return ObservedComponent(pipeline, {"name": "trades-sink", "kafka_connect": {"url": url, "connector": connector},
                                        **extra}, ["trades"])


def test_pause_when_frozen_resume_and_restart_failed_when_open():
    srv, url = _server()
    try:
        comp, notifier = _sink("p3", url), Notifier()

        comp.observe(["trades"], notifier, None)
        assert FakeConnect.calls == [("PUT", "/connectors/trades%20jdbc/pause")], FakeConnect.calls
        assert _component("p3", "trades-sink")["state"] == "paused"

        comp.observe(["trades"], notifier, None)  # đã PAUSED: không gọi lại
        assert len(FakeConnect.calls) == 1

        FakeConnect.tasks = ["FAILED"]  # message schema mới tới sink trước lúc kịp pause
        comp.observe([], notifier, None)
        assert FakeConnect.calls[1:] == [("PUT", "/connectors/trades%20jdbc/resume"),
                                         ("POST", "/connectors/trades%20jdbc/restart?includeTasks=true&onlyFailed=true")]
        assert _component("p3", "trades-sink")["state"] == "running"

        comp.observe([], notifier, None)  # đang chạy, bảng mở: không làm gì
        assert len(FakeConnect.calls) == 3

        FakeConnect.state, FakeConnect.tasks = "RUNNING", ["FAILED"]  # task chết vì lý do khác, không freeze
        comp.observe([], notifier, None)
        assert len(FakeConnect.calls) == 3, "chỉ restart task khi chính engine resume"
        assert _component("p3", "trades-sink")["state"] == "failed"
        assert notifier.sent == []
    finally:
        srv.shutdown()
    print("[PASS] test_pause_when_frozen_resume_and_restart_failed_when_open")


def test_unreachable_connect_alerts_once_while_frozen():
    srv, url = _server()
    srv.shutdown()
    srv.server_close()  # cổng đóng: connection refused
    comp, notifier = _sink("p3b", url), Notifier()
    comp.observe([], notifier, None)
    assert notifier.sent == [] and _component("p3b", "trades-sink")["state"] == "failed"  # bảng mở: chỉ hiện trên UI
    comp.observe(["trades"], notifier, None)
    comp.observe(["trades"], notifier, None)
    assert len(notifier.sent) == 1 and "Cannot pause" in notifier.sent[0], notifier.sent
    print("[PASS] test_unreachable_connect_alerts_once_while_frozen")


def test_kafka_group_lag():
    lag_only = ObservedComponent("p2", {"name": "s3-sink", "kafka_group": "g"}, ["trades"])
    lag_only.observe([], Notifier(), FakeLag(("Empty", 42, 3)))
    c = _component("p2", "s3-sink")
    assert c["state"] == "stopped" and c["metrics"]["consumer_lag"] == 42 and c["metrics"]["partitions"] == 3
    lag_only.observe([], Notifier(), FakeLag(("Stable", 0, 3)))
    assert _component("p2", "s3-sink")["state"] == "running"
    lag_only.observe([], Notifier(), FakeLag(ConnectionError("no broker")))
    c = _component("p2", "s3-sink")
    assert c["state"] == "failed" and "no broker" in c["message"]

    srv, url = _server()
    try:  # có cả connector: trạng thái lấy từ connector, lag chỉ thêm chỉ số
        both = _sink("p2", url, connector="c", kafka_group="connect-c")
        both.observe(["trades"], Notifier(), FakeLag(("Stable", 7, 1)))
        c = _component("p2", "trades-sink")
        assert c["state"] == "paused" and c["metrics"]["consumer_lag"] == 7 and c["metrics"]["connector_state"] == "PAUSED"
    finally:
        srv.shutdown()
    print("[PASS] test_kafka_group_lag")


def test_declared_missing_and_persisted_across_restart():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "_components.json"
        try:
            runtime_status._persisted_at = 0
            runtime_status.persist_components_to(path)
            runtime_status.record_component("p2p", "loader", {"state": "running", "metrics": {"rows": 5}})
            assert json.loads(path.read_text(encoding="utf-8"))["p2p"]["loader"]["metrics"] == {"rows": 5}

            runtime_status._components.clear()  # "khởi động lại"
            runtime_status.persist_components_to(path)
            runtime_status._components["p2p"]["loader"]["reported_at"] -= 60
            declared = [{"name": "loader"}, {"name": "spark", "role": "batch"}]
            comps = {c["name"]: c for c in runtime_status.get_components("p2p", declared)}
            assert comps["loader"]["state"] == "stale" and comps["loader"]["metrics"] == {"rows": 5}
            assert comps["spark"]["state"] == "missing" and comps["spark"]["role"] == "batch"
            assert comps["spark"]["age_seconds"] is None
        finally:
            runtime_status._persist_path = None
    print("[PASS] test_declared_missing_and_persisted_across_restart")


SPEC = {
    "name": "p3c",
    "source": {"type": "postgres", "config": {"host": "localhost", "dbname": "exchange"}},
    "tables": ["trades", "tickers"],
}


def test_worker_pauses_only_sinks_whose_tables_are_frozen():
    srv, url = _server()
    try:
        spec = {**SPEC, "components": [
            {"name": "trades-sink", "tables": ["trades"], "kafka_connect": {"url": url, "connector": "a"}},
            {"name": "tickers-sink", "tables": ["tickers"], "kafka_connect": {"url": url, "connector": "b"}},
            {"name": "loader"},  # chỉ khai báo: tự báo cáo qua Reporting API, engine không quan sát
        ]}
        assert validate_pipeline_spec(spec) == []
        worker = PipelineWorker(spec, SimpleNamespace(is_frozen=lambda key: key == "p3c/tickers"), Notifier(), {})
        assert [c.name for c in worker.observed] == ["trades-sink", "tickers-sink"] and worker.lag is None
        worker._observe_components()
        assert FakeConnect.calls == [("PUT", "/connectors/b/pause")], FakeConnect.calls
    finally:
        srv.shutdown()
    print("[PASS] test_worker_pauses_only_sinks_whose_tables_are_frozen")


def test_component_config_errors():
    def errors(components):
        return [e for e in validate_pipeline_spec({**SPEC, "components": components}) if e.startswith("components")]

    ok = {"name": "s", "role": "sink", "kafka_group": "g",
          "kafka_connect": {"url": "http://localhost:8083", "connector": "x"}}
    assert errors([ok, {"name": "loader"}]) == []
    assert errors([{**ok, "kafka_conect": {}}])  # gõ sai = sink không bao giờ được pause
    assert errors([{**ok, "tables": ["orders"]}])  # bảng không thuộc pipeline
    assert errors([{**ok, "kafka_connect": {"url": "localhost:8083", "connector": "x"}}])
    assert errors([{**ok, "kafka_group": ""}])
    assert errors([ok, ok])  # trùng tên
    assert errors([ok, {**ok, "name": "s2", "kafka_connect": {"url": "http://localhost:8083/", "connector": "x"}}])
    assert errors("s")
    print("[PASS] test_component_config_errors")


def test_one_connector_one_pipeline():
    """2 pipeline điều khiển cùng 1 connector -> pause/resume ngược nhau liên tục (đã thấy khi chạy thật)."""
    from app.scheduler import load_pipeline_specs
    sink = "components: [{name: s, kafka_connect: {url: 'http://localhost:8083', connector: shared}}]\n"
    with tempfile.TemporaryDirectory() as d:
        for name in ("a", "b"):
            (Path(d) / f"{name}.yaml").write_text(
                f"name: {name}\nsource: {{type: postgres, config: {{host: h, dbname: d}}}}\ntables: [t]\n" + sink,
                encoding="utf-8")
        specs, errors = load_pipeline_specs(Path(d), env={})
        assert [s["name"] for s in specs] == ["a"] and "already controlled by a.yaml" in errors["b.yaml"], errors
    print("[PASS] test_one_connector_one_pipeline")


if __name__ == "__main__":
    test_pause_when_frozen_resume_and_restart_failed_when_open()
    test_unreachable_connect_alerts_once_while_frozen()
    test_kafka_group_lag()
    test_declared_missing_and_persisted_across_restart()
    test_worker_pauses_only_sinks_whose_tables_are_frozen()
    test_component_config_errors()
    test_one_connector_one_pipeline()
