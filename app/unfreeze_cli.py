"""
unfreeze_cli.py — Công cụ CLI quản lý và duyệt/từ chối Schema Evolution từ Terminal.

Các lệnh hỗ trợ:
  python -m app.unfreeze_cli list                       : Xem danh sách các bảng đang bị Frozen (chờ duyệt)
  python -m app.unfreeze_cli view <registry_key>        : Xem chi tiết thay đổi nháp (Draft DDL)
  python -m app.unfreeze_cli approve <registry_key>     : Phê duyệt & đồng bộ DDL sang Target DB
  python -m app.unfreeze_cli reject <registry_key>      : Từ chối thay đổi, giữ nguyên baseline cũ

Ví dụ:
  python -m app.unfreeze_cli list
  python -m app.unfreeze_cli approve pg_to_mysql/customers
"""

import sys
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.schema_evolution.core import SchemaRegistry, approve_change_and_sync
from src.schema_evolution.notification import TelegramNotifier
try:
    from app.scheduler import load_config, build_pairs, ENGINE_REGISTRY
except ModuleNotFoundError:
    from scheduler import load_config, build_pairs, ENGINE_REGISTRY


def _extract_pair_name(registry_key: str) -> str | None:
    if "/" in registry_key:
        return registry_key.split("/", 1)[0]
    elif "__" in registry_key:
        return registry_key.split("__", 1)[0]
    return None


def _find_pair_by_name(pairs: list[dict], pair_name: str) -> dict | None:
    for p in pairs:
        if p["name"] == pair_name:
            return p
    return None


def main():
    if len(sys.argv) < 2:
        print("Cu phap CLI:")
        print("  python -m app.unfreeze_cli list")
        print("  python -m app.unfreeze_cli view <registry_key>")
        print("  python -m app.unfreeze_cli approve <registry_key>")
        print("  python -m app.unfreeze_cli reject <registry_key>")
        print("\nVi du: python -m app.unfreeze_cli approve pg_to_mysql/customers")
        sys.exit(1)

    action = sys.argv[1].lower()
    config_path = "config/main.yaml"
    config = load_config(config_path)

    registry = SchemaRegistry(config["registry"]["dir"])
    notifier = TelegramNotifier(
        bot_token=config["telegram"]["bot_token"],
        chat_id=config["telegram"]["chat_id"],
    )

    if action == "list":
        print("=========================================================")
        print(" [FROZEN] DANH SACH BANG DANG BI FROZEN (CHO PHE DUYET)")
        print("=========================================================")
        reg_dir = Path(config["registry"]["dir"])
        frozen_tables = []
        for p in reg_dir.rglob("*.draft.json"):
            pipeline = p.parent.name
            tbl = p.name.replace(".draft.json", "")
            key = f"{pipeline}/{tbl}"
            frozen_tables.append(key)

        if not frozen_tables:
            print("  [OK] Khong co bang nao dang bi frozen!")
        else:
            for idx, item in enumerate(frozen_tables, 1):
                print(f"  {idx}. {item}")
        print("=========================================================")
        return

    if len(sys.argv) < 3:
        print(f"Vui long cung cap <registry_key> cho lenh '{action}'!")
        sys.exit(1)

    registry_key = sys.argv[2]
    pair_name = _extract_pair_name(registry_key)
    table_name = registry_key.split("/")[-1].split("__")[-1]

    if action == "view":
        draft = registry.load_draft(registry_key)
        if not draft:
            print(f"[X] Khong tim thấy ban nhap (Draft) cho key '{registry_key}'. Bang khong bi frozen.")
            return

        print("=========================================================")
        print(f" [VIEW] CHI TIET BAN NHAP DRAFT: {registry_key}")
        print("=========================================================")
        print(f"Thoi gian phat hien: {draft.get('detected_at')}")
        print("\nDanh sach cac thay doi rui ro (Breaking Changes):")
        for idx, c in enumerate(draft.get("breaking_changes", []), 1):
            print(f"  {idx}. [{c.get('severity')}] {c.get('change_type')} -> Cot: {c.get('column_name')}")
            print(f"     Gia tri cu : {c.get('old_value')}")
            print(f"     Gia tri moi: {c.get('new_value')}")
        print("=========================================================")
        return

    if action == "approve":
        if not registry.is_frozen(registry_key):
            print(f"[!] '{registry_key}' hien khong bi frozen.")
            return

        pairs = build_pairs(config["pairs"])
        matching_pair = _find_pair_by_name(pairs, pair_name) if pair_name else None
        target_engine = matching_pair["target_engine"] if matching_pair else None

        result = approve_change_and_sync(target_engine, table_name, registry, registry_key=registry_key)
        print(f"\n[CLI] Ket qua approve_change_and_sync('{registry_key}'): {result['status']}")

        if result.get("applied_to_target"):
            print(f"  [OK] Da tu dong chay DDL len Target DB: {[c.change_type.value for c in result['applied_to_target']]}")
        if result.get("failed_on_target"):
            print(f"  [ERROR] Loi khi ap dung DDL len Target: {[c.change_type.value for c in result['failed_on_target']]}")

        if result["status"] == "approved":
            notifier.notify_change_reviewed(table_name, approved=True, pair_name=pair_name)
            print(f"  [NOTIFY] Da gui thong bao Phe duyyet thanh cong len Telegram!")

    elif action == "reject":
        if not registry.is_frozen(registry_key):
            print(f"[!] '{registry_key}' hien khong bi frozen.")
            return

        ok = registry.reject_change(registry_key)
        print(f"\n[CLI] Tu choi thay doi '{registry_key}': {'Thanh cong' if ok else 'That bai'}")
        if ok:
            notifier.notify_change_reviewed(table_name, approved=False, pair_name=pair_name)
            print(f"  [NOTIFY] Da giu nguyen Baseline cu & gui thong bao Tu choi len Telegram!")

    else:
        print(f"Lenh '{action}' khong hop le! Ho tro: list, view, approve, reject")


if __name__ == "__main__":
    main()