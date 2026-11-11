"""
Pipeline Manager: nguồn sự thật DUY NHẤT về các pipeline mà engine đang giám sát.

- Đọc config/pipelines/*.yaml, quét lại mỗi SYNC_SECONDS: file mới -> khởi động worker,
  file sửa -> khởi động lại worker, file xoá -> dừng worker. Không cần khởi động lại engine.
- Mỗi pipeline là một PipelineWorker độc lập (thread + kết nối DB riêng). File cấu hình lỗi
  hay DB của pipeline A sập chỉ ảnh hưởng pipeline A.
- Kafka: một consumer cho mỗi cluster (app/kafka_consumer.py) chỉ chuyển message cho worker.
"""
import threading
import time
from pathlib import Path

import yaml

from app import runtime_status
from app.event_log import event_logger
from app.kafka_consumer import _topic_matches, run_cluster_consumer
from app.scheduler import (
    DEFAULT_FALLBACK_INTERVAL, build_pairs, check_with_secrets, ensure_connected, load_pipeline_specs,
    log_detected_change, validate_main_config,
)
from app.secret_store import load_env, secrets_path
from app.components import LagReader, build_observed
from src.schema_evolution.core import SchemaRegistry, make_registry_key, run_evolution_check
from src.schema_evolution.notification import TelegramNotifier

SYNC_SECONDS = 3
COMPONENT_CHECK_SECONDS = 2  # gỡ freeze ở API/CLI -> connector chạy lại sau tối đa ~2s


class PipelineWorker:
    """Giám sát 1 pipeline: quét định kỳ + kiểm tra khi Kafka báo cấu trúc message đổi."""

    def __init__(self, spec: dict, registry: SchemaRegistry, notifier: TelegramNotifier, global_cfg: dict):
        self.spec = spec
        self.name = spec["name"]
        self.tables = list(spec["tables"])
        detection = spec.get("detection") or {}
        self.event_driven = detection.get("mode") == "event_driven"
        self.kafka_cfg = {**(global_cfg.get("kafka") or {}), **(detection.get("kafka") or {})}
        self.topic = self.kafka_cfg.get("topic", self.name)
        self.bootstrap = self.kafka_cfg.get("bootstrap_servers", "localhost:19092")
        # polling: chu kỳ riêng của pipeline (detection.interval_seconds), không có thì lấy mặc định chung.
        self.interval = (detection.get("fallback_polling_interval_seconds", DEFAULT_FALLBACK_INTERVAL)
                         if self.event_driven else detection.get("interval_seconds")
                         or (global_cfg.get("scheduler") or {}).get("interval_seconds", 60))
        pair = build_pairs([spec])[0]  # chỉ khởi tạo engine, chưa kết nối
        self.source, self.target = pair["source_engine"], pair["target_engine"]
        self.registry, self.notifier = registry, notifier
        # Thành phần engine tự quan sát (kafka_group) / điều khiển (kafka_connect: pause/resume theo freeze).
        self.observed = build_observed(spec)
        self.lag = LagReader(self.bootstrap) if any(c.group for c in self.observed) else None

        self.seen: dict[str, str] = {}             # bảng -> fingerprint đã kiểm tra xong
        self._pending: dict[str, str | None] = {}  # bảng -> fingerprint chờ kiểm tra (None = bắt buộc)
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"pipeline-{self.name}")
        # Thread riêng: Kafka Connect/broker treo (timeout vài giây) không được làm chậm việc phát hiện schema.
        self._observe_now = threading.Event()
        self._observer = (threading.Thread(target=self._observe_loop, daemon=True, name=f"observe-{self.name}")
                          if self.observed else None)

    def matches(self, topic: str) -> bool:
        return _topic_matches(topic, self.topic) or _topic_matches(topic, self.name)

    def notify(self, table: str, fingerprint: str | None) -> None:
        """Gọi từ thread Kafka consumer: chỉ ghi nhận và đánh thức worker, không chặn."""
        if fingerprint is not None and self.seen.get(table) == fingerprint:
            return
        with self._lock:
            self._pending[table] = fingerprint  # gộp: nhiều message cùng lúc -> 1 lần kiểm tra
        self._wake.set()

    def start(self) -> None:
        self._thread.start()
        if self._observer is not None:
            self._observer.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        self._observe_now.set()
        self._thread.join(timeout=15)
        if self._observer is not None:
            self._observer.join(timeout=15)

    def _check(self, table: str, source: str) -> dict:
        result = run_evolution_check(self.source, self.target, table, self.registry, self.notifier,
                                     registry_key=make_registry_key(self.name, table),
                                     target_table=(self.spec.get("table_targets") or {}).get(table))
        print(f"[{self.name}] {table}: {result['status']} ({source})")
        log_detected_change(self.name, table, result, source=source)
        if result["status"] == "changes_applied":
            for comp in self.observed:
                if table in comp.tables:
                    comp.mark_synced()
        return result

    def _connect(self) -> None:
        ensure_connected(self.source)
        if self.target is not None:
            ensure_connected(self.target)

    def _scan(self) -> None:
        try:
            self._connect()
        except Exception as e:
            print(f"[{self.name}] cannot connect: {e}")
            runtime_status.record_scan(self.name, ok=False, error=f"Mất kết nối: {e}")
            return
        errors = []
        for table in self.tables:
            try:
                self._check(table, "polling")
            except Exception as e:
                errors.append(f"{table}: {e}")
                print(f"[{self.name}] scan {table} failed: {e}")
        runtime_status.record_scan(self.name, ok=not errors, error="; ".join(errors) or None)

    def _observe_components(self) -> None:
        for comp in self.observed:
            try:
                frozen = [t for t in comp.tables if self.registry.is_frozen(make_registry_key(self.name, t))]
                comp.observe(frozen, self.notifier, self.lag)
            except Exception as e:  # lỗi bất ngờ ở 1 component không được dừng việc giám sát schema
                print(f"[{self.name}] component {comp.name} check failed: {e}")

    def _observe_loop(self) -> None:
        try:
            while not self._stop.is_set():
                self._observe_components()
                self._observe_now.wait(COMPONENT_CHECK_SECONDS)  # hoặc sớm hơn: worker vừa kiểm tra xong
                self._observe_now.clear()
        finally:
            if self.lag is not None:
                self.lag.close()

    def _run(self) -> None:
        print(f"[{self.name}] worker started ({'event_driven' if self.event_driven else 'polling'}, scan every {self.interval}s)")
        next_scan = time.monotonic()  # quét ngay khi khởi động: khởi tạo baseline / bắt kịp thay đổi khi engine tắt
        try:
            while not self._stop.is_set():
                self._wake.wait(timeout=max(0.0, next_scan - time.monotonic()))
                self._wake.clear()
                if self._stop.is_set():
                    break
                with self._lock:
                    pending, self._pending = self._pending, {}
                for table, fingerprint in pending.items():
                    if fingerprint is not None and self.seen.get(table) == fingerprint:
                        continue
                    try:
                        self._connect()
                        self._check(table, "kafka")
                        if fingerprint is not None:
                            self.seen[table] = fingerprint  # chỉ ghi nhớ khi kiểm tra thành công
                    except Exception as e:
                        print(f"[{self.name}] check {table} failed: {e}")
                if time.monotonic() >= next_scan:
                    self._scan()
                    next_scan = time.monotonic() + self.interval
                self._observe_now.set()  # bảng vừa freeze -> pause connector ngay, không chờ hết chu kỳ
        finally:
            for engine in (self.source, self.target):
                if engine is not None:
                    try:
                        engine.disconnect()
                    except Exception:
                        pass
            print(f"[{self.name}] worker stopped")


class PipelineManager:
    """
    Cấu hình chia 2 loại (như Prometheus/Nginx/Airflow):
    - Bootstrap, đổi phải khởi động lại: registry.dir (nơi lưu trạng thái).
    - Runtime, tự nạp lại: config/pipelines/*.yaml, và trong main.yaml: telegram, kafka, scheduler.
    File mới bị lỗi -> giữ cấu hình đang chạy (last-known-good) và báo lỗi, không dừng giám sát.
    """

    def __init__(self, config_path: str = "config/main.yaml"):
        self.config_path = Path(config_path)
        self.pipelines_dir = self.config_path.parent / "pipelines"
        self.secrets_file = secrets_path(self.config_path.parent)
        cfg, problems = check_with_secrets(yaml.safe_load(self.config_path.read_text(encoding="utf-8")),
                                           load_env(self.config_path.parent), validate_main_config)
        if problems:  # lúc khởi động chưa có cấu hình nào chạy tốt để giữ lại -> dừng hẳn, báo rõ
            raise ValueError(f"{self.config_path}: {'; '.join(problems)}")
        self.global_cfg = cfg
        self.registry = SchemaRegistry(cfg["registry"]["dir"])
        event_logger.persist_to(Path(cfg["registry"]["dir"]) / "_events.jsonl")  # cùng chỗ với lịch sử schema
        runtime_status.persist_components_to(Path(cfg["registry"]["dir"]) / "_components.json")
        self.notifier = self._make_notifier(cfg)
        self.workers: dict[str, PipelineWorker] = {}
        self.errors: dict[str, str] = {}  # tên file pipeline -> lỗi cấu hình
        self.main_error: str | None = None
        self.version = 0                  # tăng mỗi lần tập pipeline đổi (consumer đăng ký lại topic)
        self._files = None
        self._main_seen = self._main_state()
        self._lock = threading.Lock()
        self._consumers: dict[str, threading.Event] = {}

    @staticmethod
    def _make_notifier(cfg: dict) -> TelegramNotifier:
        tg = cfg.get("telegram") or {}
        return TelegramNotifier(tg.get("bot_token", ""), tg.get("chat_id", ""))

    def _secrets_state(self):
        try:
            st = self.secrets_file.stat()
            return st.st_mtime_ns, st.st_size
        except FileNotFoundError:
            return None

    def _main_state(self):
        try:
            st = self.config_path.stat()
            return st.st_mtime_ns, st.st_size, self._secrets_state()  # đổi secrets.env cũng phải nạp lại
        except FileNotFoundError:
            return None

    def _reload_main(self) -> bool:
        """Nạp lại main.yaml nếu đổi. True = phần kafka/scheduler đổi -> phải khởi động lại worker."""
        state = self._main_state()
        if state == self._main_seen:
            return False
        self._main_seen = state
        try:
            cfg, problems = check_with_secrets(yaml.safe_load(self.config_path.read_text(encoding="utf-8")),
                                               load_env(self.config_path.parent), validate_main_config)
        except (OSError, yaml.YAMLError) as e:
            problems = [f"invalid YAML: {e}"]
        if problems:
            self.main_error = "; ".join(problems) + " — still running with the last valid config"
            print(f"[PipelineManager] main.yaml rejected: {self.main_error}")
            return False
        self.main_error = None
        running_dir = self.global_cfg["registry"]["dir"]
        if cfg["registry"]["dir"] != running_dir:
            self.main_error = f"registry.dir change needs a restart — still using '{running_dir}'"
            cfg = {**cfg, "registry": self.global_cfg["registry"]}
        old, self.global_cfg = self.global_cfg, cfg
        if (cfg.get("telegram") or {}) != (old.get("telegram") or {}):
            self.notifier = self._make_notifier(cfg)
            with self._lock:
                for worker in self.workers.values():
                    worker.notifier = self.notifier
            print("[PipelineManager] telegram settings reloaded")
        restart = any((cfg.get(k) or {}) != (old.get(k) or {}) for k in ("kafka", "scheduler"))
        if restart:
            print("[PipelineManager] kafka/scheduler settings changed — restarting workers")
        return restart

    def snapshot(self) -> dict:
        """Cấu hình engine ĐANG chạy (cho API/UI), không phải nội dung file có thể đang lỗi."""
        with self._lock:
            errors = dict(self.errors)
            if self.main_error:
                errors["main.yaml"] = self.main_error
            return {**self.global_cfg, "pairs": [w.spec for w in self.workers.values()], "pipeline_errors": errors}

    def _file_state(self):
        try:
            # secrets.env đổi -> pipeline dùng bí mật đó có cấu hình (đã thay) mới -> worker nạp lại.
            return tuple(sorted((f.name, f.stat().st_mtime_ns, f.stat().st_size)
                                for f in self.pipelines_dir.glob("*.yaml"))) + (self._secrets_state(),)
        except FileNotFoundError:
            return None  # file vừa bị xoá giữa lúc quét -> coi như đổi, quét lại lượt sau

    def sync(self) -> bool:
        """Áp dụng thay đổi trong main.yaml và config/pipelines/. True nếu tập worker thay đổi."""
        restart_all = self._reload_main()
        files = self._file_state()
        if not restart_all and files is not None and files == self._files:
            return False
        self._files = files
        specs, errors = load_pipeline_specs(self.pipelines_dir)
        wanted = {s["name"]: s for s in specs}
        if restart_all:  # kafka mặc định có thể đổi -> consumer kết nối lại với cấu hình mới
            for stop in self._consumers.values():
                stop.set()
            self._consumers.clear()
        with self._lock:
            for name in list(self.workers):
                if restart_all or wanted.get(name) != self.workers[name].spec:
                    print(f"[PipelineManager] {'reloading' if name in wanted else 'removing'} '{name}'")
                    self.workers.pop(name).stop()
                    runtime_status.forget(name)
            for name, spec in wanted.items():
                if name in self.workers:
                    continue
                try:
                    worker = PipelineWorker(spec, self.registry, self.notifier, self.global_cfg)
                except Exception as e:
                    errors[f"{name}.yaml"] = f"cannot start: {e}"
                    continue
                worker.start()
                self.workers[name] = worker
            self.errors = errors
            self.version += 1
        for file, err in errors.items():
            print(f"[PipelineManager] config error in {file}: {err}")
        self._sync_consumers()
        return True

    def event_workers(self, bootstrap: str) -> list[PipelineWorker]:
        with self._lock:
            return [w for w in self.workers.values() if w.event_driven and w.bootstrap == bootstrap]

    def _sync_consumers(self) -> None:
        with self._lock:
            needed = {w.bootstrap for w in self.workers.values() if w.event_driven}
        for bootstrap in list(self._consumers):
            if bootstrap not in needed:
                self._consumers.pop(bootstrap).set()
        for bootstrap in needed - self._consumers.keys():
            stop = threading.Event()
            self._consumers[bootstrap] = stop
            threading.Thread(target=run_cluster_consumer, args=(bootstrap, self, stop),
                             daemon=True, name=f"kafka-{bootstrap}").start()

    def run_forever(self) -> None:
        print(f"[PipelineManager] watching {self.pipelines_dir} every {SYNC_SECONDS}s")
        try:
            while True:
                try:
                    self.sync()
                except Exception as e:  # không để 1 lỗi bất ngờ dừng việc giám sát
                    print(f"[PipelineManager] sync failed: {e}")
                time.sleep(SYNC_SECONDS)
        except KeyboardInterrupt:
            print("\n[PipelineManager] stopping...")
        finally:
            for stop in self._consumers.values():
                stop.set()
            for worker in list(self.workers.values()):
                worker.stop()
