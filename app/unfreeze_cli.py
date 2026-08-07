"""
unfreeze_cli.py — Script tạm để approve/reject 1 bảng đang bị frozen,
dùng khi chưa có Streamlit UI (app.py).

approve: tự động build target_engine từ đúng pair trong config.yaml,
gọi approve_change_and_sync() để vừa duyệt vừa CHẠY DDL LÊN TARGET
(khép kín vòng lặp, không chỉ ghi sổ Registry).
reject: chỉ cập nhật Registry (không cần đụng DB nào).

Cách chạy (đứng trong thư mục app/, đã activate venv):
    python unfreeze_cli.py reject pg_to_mysql__customers
    python unfreeze_cli.py approve pg_to_mysql__customers
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml
from src.schema_evolution.core import SchemaRegistry, approve_change_and_sync
from src.schema_evolution.notification import TelegramNotifier
from scheduler import ENGINE_REGISTRY


def _extract_pair_name(registry_key: str) -> str | None:
    if registry_key and "__" in registry_key:
        return registry_key.rsplit("__", 1)[0]
    return None


def _find_pair_config(config: dict, pair_name: str) -> dict | None:
    for p in config.get("pairs", []):
        if p["name"] == pair_name:
            return p
    return None


def _build_target_engine(pair_config: dict):
    target_spec = pair_config.get("target")
    if not target_spec:
        return None
    engine_cls = ENGINE_REGISTRY[target_spec["type"]]
    engine = engine_cls(target_spec["config"])
    engine.connect()
    return engine


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("approve", "reject"):
        print("Cách dùng: python unfreeze_cli.py [approve|reject] <registry_key>")
        print("VD:        python unfreeze_cli.py reject pg_to_mysql__customers")
        sys.exit(1)

    action = sys.argv[1]
    registry_key = sys.argv[2]

    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    registry = SchemaRegistry(config["registry"]["dir"])
    notifier = TelegramNotifier(
        bot_token=config["telegram"]["bot_token"],
        chat_id=config["telegram"]["chat_id"],
    )

    if not registry.is_frozen(registry_key):
        print(f"'{registry_key}' hiện không bị frozen, không cần làm gì.")
        return

    table_name = registry_key.rsplit("__", 1)[-1] if "__" in registry_key else registry_key
    pair_name = _extract_pair_name(registry_key)

    if action == "approve":
        target_engine = None
        if pair_name:
            pair_config = _find_pair_config(config, pair_name)
            if pair_config is None:
                print(
                    f"CẢNH BÁO: không tìm thấy pair '{pair_name}' trong config.yaml "
                    f"— approve chỉ cập nhật Registry, KHÔNG đồng bộ target."
                )
            else:
                try:
                    target_engine = _build_target_engine(pair_config)
                except Exception as e:
                    print(
                        f"CẢNH BÁO: không kết nối được target ({e}) "
                        f"— approve chỉ cập nhật Registry, KHÔNG đồng bộ target."
                    )

        result = approve_change_and_sync(target_engine, table_name, registry, registry_key=registry_key)
        print(f"approve_change_and_sync('{registry_key}') -> {result['status']}")
        if result.get("applied_to_target"):
            print(f"  Đã đồng bộ lên target: {[c.change_type.value for c in result['applied_to_target']]}")
        if result.get("failed_on_target"):
            print(f"  LỖI khi đồng bộ lên target: {[c.change_type.value for c in result['failed_on_target']]}")

        if target_engine is not None:
            target_engine.disconnect()

        if result["status"] == "approved":
            notifier.notify_change_reviewed(table_name, approved=True, pair_name=pair_name)
    else:
        ok = registry.reject_change(registry_key)
        print(f"reject_change('{registry_key}') -> {ok}")
        if ok:
            notifier.notify_change_reviewed(table_name, approved=False, pair_name=pair_name)

    print(f"is_frozen sau khi xử lý: {registry.is_frozen(registry_key)}")


if __name__ == "__main__":
    main()