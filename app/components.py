"""
Thành phần data plane khai báo trong YAML pipeline (mức 2-3), dùng cho sink không sửa được code:

  components:
    - name: trades-sink
      role: sink                             # tuỳ chọn, hiện trên UI
      tables: [trades]                       # tuỳ chọn, mặc định mọi bảng của pipeline
      kafka_group: connect-trades-sink       # mức 2: engine tự đo consumer lag + nhóm còn sống không
      kafka_connect: {url: http://localhost:8083, connector: trades-sink}  # mức 3: engine pause/resume

Khai báo mà không có gì báo cáo -> UI hiện "missing" (runtime_status.get_components).

kafka_connect là đối chiếu kiểu controller: có bảng nào của component đang frozen thì connector phải
PAUSED, không thì chạy. Mỗi lượt đọc trạng thái thật rồi sửa nếu lệch, nên mọi đường gỡ freeze (approve,
reject, nguồn tự rollback, unfreeze_cli ở tiến trình khác), engine khởi động lại hay ai đó resume tay
khi đang freeze đều được xử lý như nhau.
"""
from urllib.parse import quote

import requests

from app import runtime_status
from app.event_log import event_logger

TIMEOUT = 3
# Trạng thái consumer group (Kafka DescribeGroups) -> trạng thái hiện trên UI
GROUP_STATE = {"Stable": "running", "PreparingRebalance": "starting", "CompletingRebalance": "starting",
               "Empty": "stopped", "Dead": "stopped"}


class KafkaConnectControl:
    def __init__(self, url: str, connector: str):
        self.connector = connector
        self.base = f"{url.rstrip('/')}/connectors/{quote(connector, safe='')}"

    def _call(self, method: str, path: str) -> requests.Response:
        resp = requests.request(method, self.base + path, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp

    def enforce(self, frozen: bool) -> tuple[str | None, str, int]:
        """Đưa connector về trạng thái mong muốn. Trả về (việc đã làm, trạng thái trước đó, số task FAILED)."""
        status = self._call("GET", "/status").json()
        state = status["connector"]["state"]
        failed = sum(t.get("state") == "FAILED" for t in status.get("tasks", []))
        if frozen and state != "PAUSED":
            self._call("PUT", "/pause")
            return "paused", state, failed
        if not frozen and state == "PAUSED":
            self._call("PUT", "/resume")
            if failed:  # task chết vì message schema mới tới trước lúc kịp pause; resume không cứu task FAILED
                self._call("POST", "/restart?includeTasks=true&onlyFailed=true")
            return "resumed", state, failed
        return None, state, failed


class LagReader:
    """Một admin client Kafka cho mỗi worker, mở khi cần, mở lại sau lỗi."""

    def __init__(self, bootstrap: str):
        self.bootstrap, self.admin = bootstrap, None

    def read(self, group: str) -> tuple[str, int | None, int]:
        """(trạng thái group, tổng lag hoặc None nếu group không có partition nào, số partition)."""
        from kafka import KafkaAdminClient, TopicPartition
        from kafka.admin import OffsetSpec
        try:
            if self.admin is None:
                self.admin = KafkaAdminClient(bootstrap_servers=self.bootstrap, request_timeout_ms=5000,
                                              client_id="schema-evolution-lag")
            info = self.admin.describe_groups([group]).get(group) or {}
            committed = {tp: om.offset for tp, om in
                         (self.admin.list_group_offsets({group: None}).get(group) or {}).items() if om.offset >= 0}
            # Partition đã giao nhưng chưa commit lần nào (sink mới chạy) vẫn có lag: tính từ đầu log như rpk
            # (mặc định auto.offset.reset=earliest của sink Kafka Connect).
            assigned = {TopicPartition(a["topic"], p) for m in info.get("members") or []
                        for a in (m.get("member_assignment") or {}).get("assigned_partitions") or []
                        for p in a["partitions"]}
            parts = assigned | committed.keys()
            ends = self.admin.list_partition_offsets({tp: OffsetSpec.LATEST for tp in parts}) if parts else {}
            fresh = parts - committed.keys()
            starts = self.admin.list_partition_offsets({tp: OffsetSpec.EARLIEST for tp in fresh}) if fresh else {}
        except Exception:
            self.close()
            raise
        lag = sum(max(0, ends[tp].offset - (committed[tp] if tp in committed else starts[tp].offset))
                  for tp in parts) if parts else None
        return info.get("group_state") or info.get("state") or "Unknown", lag, len(parts)

    def close(self) -> None:
        if self.admin is not None:
            try:
                self.admin.close()
            except Exception:
                pass
            self.admin = None


class ObservedComponent:
    def __init__(self, pipeline: str, spec: dict, pipeline_tables: list[str]):
        self.pipeline, self.name = pipeline, spec["name"]
        self.role = spec.get("role") or "sink"
        self.tables = spec.get("tables") or list(pipeline_tables)
        kc = spec.get("kafka_connect")
        self.connect = KafkaConnectControl(kc["url"], kc["connector"]) if kc else None
        self.group = spec.get("kafka_group")
        self.alerted = False  # đã cảnh báo không pause được chưa (tránh gửi lại mỗi lượt)

    def observe(self, frozen_tables: list[str], notifier, lag: LagReader | None) -> None:
        report = {"state": "running", "role": self.role, "metrics": {"observed_by": "engine"}, "message": ""}
        if self.connect:
            self._control(frozen_tables, notifier, report)
        if self.group and lag is not None:
            try:
                group_state, total, partitions = lag.read(self.group)
                report["metrics"].update(consumer_lag=total, partitions=partitions, group_state=group_state)
                if not self.connect:  # có connector thì trạng thái connector chính xác hơn
                    report["state"] = GROUP_STATE.get(group_state, "warn")
            except Exception as e:
                report["message"] = (report["message"] + " · " if report["message"] else "") + f"lag: {e}"
                if not self.connect:
                    report["state"] = "failed"
        runtime_status.record_component(self.pipeline, self.name, report)

    def _control(self, frozen_tables: list[str], notifier, report: dict) -> None:
        frozen = bool(frozen_tables)
        try:
            action, state, failed = self.connect.enforce(frozen)
        except (requests.RequestException, KeyError, ValueError) as e:
            report.update(state="failed", message=f"Kafka Connect '{self.connect.connector}': {e}")
            if frozen and not self.alerted:  # bảng đã freeze mà sink vẫn ghi: phải có người xử lý
                self.alerted = True
                text = (f"Cannot pause Kafka Connect connector '{self.connect.connector}' "
                        f"while {', '.join(frozen_tables)} is frozen: {e}")
                print(f"[{self.pipeline}] {text}")
                event_logger.add_event(self.pipeline, ", ".join(frozen_tables), f"[kafka_connect] {text}",
                                       "sink_control_failed", severity="breaking")
                notifier.send_message(f"⚠️ <b>{self.pipeline}</b>: {text}")
            return
        self.alerted = False
        if action:
            why = f"{', '.join(frozen_tables)} frozen" if frozen else "all tables open"
            extra = f", restarted {failed} failed task(s)" if action == "resumed" and failed else ""
            print(f"[{self.pipeline}] kafka_connect {self.connect.connector}: {action} ({why}{extra})")
            event_logger.add_event(self.pipeline, ", ".join(frozen_tables or self.tables),
                                   f"[kafka_connect] {action.capitalize()} connector '{self.connect.connector}' ({why}{extra})",
                                   f"sink_{action}", severity="non_breaking")
            state, failed = ("PAUSED", failed) if action == "paused" else ("RUNNING", 0)
        report["state"] = "failed" if failed or state == "FAILED" else "paused" if state == "PAUSED" else "running"
        report["metrics"].update(connector_state=state, failed_tasks=failed)
        if frozen:
            report["message"] = f"Paused by engine: {', '.join(frozen_tables)} frozen"


def build_observed(spec: dict) -> list[ObservedComponent]:
    return [ObservedComponent(spec["name"], c, spec["tables"])
            for c in spec.get("components") or [] if c.get("kafka_connect") or c.get("kafka_group")]
