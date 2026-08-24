"""
app/cli.py — Enterprise Terminal Interface (CLI / TUI)
Launch via shortcut command:
    schema-check
"""

import sys
import os
import json
import time
from pathlib import Path

# Enable ANSI escape codes on Windows console
if os.name == 'nt':
    os.system('')

# ANSI Color Codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[90m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m\033[37m"
BG_CYAN = "\033[46m\033[30m"

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.schema_evolution.core import SchemaRegistry, approve_change_and_sync
from src.schema_evolution.notification import TelegramNotifier
from app.scheduler import load_config, build_pairs, ENGINE_REGISTRY


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def get_key() -> str:
    """Reads a single keypress from console, including arrow keys UP/DOWN/LEFT/RIGHT, ENTER, and ESC."""
    if os.name == 'nt':
        import msvcrt
        ch = msvcrt.getwch()
        if ch in ('\x00', '\xe0'):
            ch2 = msvcrt.getwch()
            if ch2 == 'H': return 'UP'
            if ch2 == 'P': return 'DOWN'
            if ch2 == 'K': return 'LEFT'
            if ch2 == 'M': return 'RIGHT'
        elif ch in ('\r', '\n'):
            return 'ENTER'
        elif ch == '\x1b':
            return 'ESC'
        return ch
    else:
        import tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                ch2 = sys.stdin.read(1)
                ch3 = sys.stdin.read(1)
                if ch3 == 'A': return 'UP'
                if ch3 == 'B': return 'DOWN'
                if ch3 == 'C': return 'RIGHT'
                if ch3 == 'D': return 'LEFT'
                return 'ESC'
            elif ch in ('\r', '\n'):
                return 'ENTER'
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def get_frozen_tables(registry: SchemaRegistry, config: dict) -> list[dict]:
    reg_dir = Path(config["registry"]["dir"])
    frozen_list = []
    if not reg_dir.exists():
        return frozen_list

    for p in reg_dir.rglob("*.draft.json"):
        pipeline = p.parent.name
        tbl = p.name.replace(".draft.json", "")
        key = f"{pipeline}/{tbl}"
        draft = registry.load_draft(key)
        frozen_list.append({
            "key": key,
            "pipeline": pipeline,
            "table": tbl,
            "draft": draft,
            "path": p
        })
    return frozen_list


def get_all_monitored_tables(registry: SchemaRegistry, config: dict) -> list[dict]:
    reg_dir = Path(config["registry"]["dir"])
    all_tables = []
    if not reg_dir.exists():
        return all_tables

    for p in reg_dir.rglob("*.json"):
        if p.name.endswith(".draft.json"):
            continue
        pipeline = p.parent.name
        tbl = p.name.replace(".json", "")
        key = f"{pipeline}/{tbl}"
        schema = registry.load(key)
        is_frozen = registry.is_frozen(key)
        all_tables.append({
            "key": key,
            "pipeline": pipeline,
            "table": tbl,
            "schema": schema,
            "is_frozen": is_frozen
        })
    return sorted(all_tables, key=lambda x: x["key"])


def print_header():
    print("=" * 100)
    print(f"  {BOLD}SCHEMA EVOLUTION CLI{RESET}")
    print("=" * 100)


def render_split_screen(all_tables: list[dict], selected_idx: int, config: dict):
    left_w = 44
    right_w = 52
    VIEWPORT_HEIGHT = 12

    # Calculate sliding viewport slice so selected item is ALWAYS pinned inside 12-row window
    start_idx = max(0, min(selected_idx - VIEWPORT_HEIGHT // 2, len(all_tables) - VIEWPORT_HEIGHT))
    if start_idx < 0:
        start_idx = 0
    end_idx = min(len(all_tables), start_idx + VIEWPORT_HEIGHT)

    visible_tables = all_tables[start_idx:end_idx]

    print("┌" + "─" * left_w + "┬" + "─" * right_w + "┐")
    hdr_left = f"PIPELINES & TABLES ({selected_idx+1}/{len(all_tables)})"
    print(f"│ {BOLD}{hdr_left:<{left_w-2}}{RESET} │ {BOLD}SCHEMA & PIPELINE DETAILS{RESET:<{right_w-25}} │")
    print("├" + "─" * left_w + "┼" + "─" * right_w + "┤")

    left_lines = []
    for idx_offset, item in enumerate(visible_tables):
        actual_idx = start_idx + idx_offset
        is_sel = (actual_idx == selected_idx)
        status_tag = f"{RED}[FRZ]{RESET}" if item["is_frozen"] else f"{GREEN}[ACT]{RESET}"
        name_str = f"{item['pipeline']}/{item['table']}"
        if len(name_str) > 28:
            name_str = name_str[:25] + "..."

        if is_sel:
            line = f"{BG_BLUE}▶ [{actual_idx+1:>2}] {name_str:<28}{RESET} {status_tag}"
        else:
            line = f"  [{actual_idx+1:>2}] {CYAN}{name_str:<28}{RESET} {status_tag}"
        left_lines.append(line)

    while len(left_lines) < VIEWPORT_HEIGHT:
        left_lines.append(" " * left_w)

    right_lines = []
    if 0 <= selected_idx < len(all_tables):
        curr = all_tables[selected_idx]
        key = curr["key"]
        pipe_name = curr["pipeline"]
        schema = curr["schema"]
        is_frozen = curr["is_frozen"]

        matching_pair = next((p for p in config.get("pairs", []) if p.get("name") == pipe_name), {})
        src_type = matching_pair.get("source", {}).get("type", "unknown")
        tgt_type = matching_pair.get("target", {}).get("type", "Self-Monitor") if matching_pair.get("target") else "Self-Monitor"

        status_str = f"{RED}FROZEN{RESET}" if is_frozen else f"{GREEN}ACTIVE{RESET}"

        right_lines.append(f"{BOLD}Pipeline{RESET}  : {CYAN}{key}{RESET}")
        right_lines.append(f"{BOLD}Topology{RESET}  : {YELLOW}{src_type}{RESET} ➔ {YELLOW}{tgt_type}{RESET}")
        right_lines.append(f"{BOLD}Status  {RESET}  : {status_str}")
        right_lines.append("─" * right_w)

        if schema:
            pk_set = set(schema.primary_key)
            right_lines.append(f"{BOLD}Columns ({len(schema.columns)}):{RESET}")
            for col in schema.columns[:6]:
                pk_flag = f"{YELLOW}[PK]{RESET}" if col.name in pk_set else "    "
                null_flag = f"{DIM}NULL{RESET}" if col.nullable else f"{BOLD}NOT NULL{RESET}"
                col_name = col.name[:14]
                col_type = col.data_type[:10]
                right_lines.append(f" • {CYAN}{col_name:<14}{RESET} {col_type:<10} {null_flag:<14} {pk_flag}")
            if len(schema.columns) > 6:
                right_lines.append(f" {DIM}... (+{len(schema.columns)-6} more){RESET}")
        else:
            right_lines.append(f"{DIM}No schema baseline recorded.{RESET}")

    while len(right_lines) < VIEWPORT_HEIGHT:
        right_lines.append(" " * right_w)

    for r in range(VIEWPORT_HEIGHT):
        l_str = left_lines[r]
        r_str = right_lines[r]
        print(f"│ {l_str} │ {r_str} │")

    print("└" + "─" * left_w + "┴" + "─" * right_w + "┘")


def menu_interactive_split_view(all_tables: list[dict], config: dict):
    if not all_tables:
        print(f"\n{DIM}No monitored tables found.{RESET}")
        input("\nPress Enter...")
        return

    selected_idx = 0
    while True:
        clear_screen()
        print_header()

        render_split_screen(all_tables, selected_idx, config)

        print(f" {BOLD}[UP/DOWN]{RESET} Scroll   {BOLD}[ESC/q]{RESET} Back")

        key = get_key()
        if key in ('ESC', 'q', 'Q'):
            break
        elif key == 'UP':
            selected_idx = (selected_idx - 1) % len(all_tables)
        elif key == 'DOWN':
            selected_idx = (selected_idx + 1) % len(all_tables)


def menu_list_frozen(frozen_tables: list[dict]):
    print(f"\n{BOLD}FROZEN TABLES ({len(frozen_tables)}):{RESET}\n")
    if not frozen_tables:
        print(f"  {GREEN}No tables currently frozen.{RESET}")
        return

    header = "┌───┬────────────────────────┬──────────────────────┬───────────────┬─────────────────────┐"
    titles = "│ # │ Pipeline               │ Table                │ Risks         │ Detected At         │"
    sep    = "├───┼────────────────────────┼──────────────────────┼───────────────┼─────────────────────┤"
    footer = "└───┴────────────────────────┴──────────────────────┴───────────────┴─────────────────────┘"

    print(header)
    print(titles)
    print(sep)

    for idx, item in enumerate(frozen_tables, 1):
        pipe = item['pipeline'][:22]
        tbl = item['table'][:20]
        bc_count = len(item['draft'].get('breaking_changes', [])) if item['draft'] else 0
        time_str = item['draft'].get('detected_at', 'N/A')[:19] if item['draft'] else 'N/A'

        print(f"│{idx:>2} │ {CYAN}{pipe:<22}{RESET} │ {YELLOW}{tbl:<20}{RESET} │ {RED}{bc_count:>9} risks{RESET} │ {DIM}{time_str:<19}{RESET} │")

    print(footer)


def action_view_details(registry: SchemaRegistry, frozen_tables: list[dict]):
    if not frozen_tables:
        print(f"\n{DIM}No frozen tables to inspect.{RESET}")
        input("\nPress Enter...")
        return

    menu_list_frozen(frozen_tables)
    choice = input("\nSelect table # (or 'b'): ").strip()
    if choice.lower() == 'b' or not choice:
        return

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(frozen_tables):
            selected = frozen_tables[idx]
            draft = selected['draft']
            print("\n" + "=" * 86)
            print(f" {BOLD}DRAFT DETAILS:{RESET} {CYAN}{selected['key']}{RESET}")
            print("=" * 86)
            print(f"Detected At: {draft.get('detected_at')}")
            print(f"\n{BOLD}Breaking Changes:{RESET}")
            for i, c in enumerate(draft.get("breaking_changes", []), 1):
                print(f"\n  ({i}) [{RED}{c.get('severity')}{RESET}] {YELLOW}{c.get('change_type')}{RESET}")
                print(f"      Target : {CYAN}{c.get('column_name') or c.get('constraint_name')}{RESET}")
                print(f"      Old    : {c.get('old_value')}")
                print(f"      New    : {c.get('new_value')}")
            print("=" * 86)
        else:
            print(f"{RED}Invalid selection number.{RESET}")
    except ValueError:
        print(f"{RED}Invalid input.{RESET}")

    input("\nPress Enter...")


def action_approve(registry: SchemaRegistry, config: dict, notifier: TelegramNotifier, frozen_tables: list[dict]):
    if not frozen_tables:
        print(f"\n{DIM}No frozen tables to approve.{RESET}")
        input("\nPress Enter...")
        return

    menu_list_frozen(frozen_tables)
    choice = input("\nSelect table # to APPROVE (or 'b'): ").strip()
    if choice.lower() == 'b' or not choice:
        return

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(frozen_tables):
            selected = frozen_tables[idx]
            confirm = input(f"APPROVE & sync '{selected['key']}'? [y/N]: ").strip().lower()
            if confirm == 'y':
                pairs = build_pairs(config["pairs"])
                matching_pair = next((p for p in pairs if p["name"] == selected["pipeline"]), None)
                target_engine = matching_pair["target_engine"] if matching_pair else None

                result = approve_change_and_sync(target_engine, selected["table"], registry, registry_key=selected["key"])
                print(f"\nResult: {GREEN}{result['status'].upper()}{RESET}")

                if result.get("applied_to_target"):
                    print(f"  {GREEN}[SUCCESS] DDL executed on Target DB:{RESET}")
                    for c in result["applied_to_target"]:
                        print(f"     - {c.change_type.value} on '{c.column_name}'")
                if result.get("failed_on_target"):
                    print(f"  {RED}[ERROR] DDL failed on Target DB:{RESET}")
                    for c in result["failed_on_target"]:
                        print(f"     - {c.change_type.value} on '{c.column_name}'")

                if result["status"] == "approved":
                    notifier.notify_change_reviewed(selected["table"], approved=True, pair_name=selected["pipeline"])
                    print(f"  {GREEN}[NOTIFY] Telegram alert sent.{RESET}")
            else:
                print("Cancelled.")
        else:
            print(f"{RED}Invalid selection.{RESET}")
    except ValueError:
        print(f"{RED}Invalid input.{RESET}")

    input("\nPress Enter...")


def action_reject(registry: SchemaRegistry, notifier: TelegramNotifier, frozen_tables: list[dict]):
    if not frozen_tables:
        print(f"\n{DIM}No frozen tables to reject.{RESET}")
        input("\nPress Enter...")
        return

    menu_list_frozen(frozen_tables)
    choice = input("\nSelect table # to REJECT (or 'b'): ").strip()
    if choice.lower() == 'b' or not choice:
        return

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(frozen_tables):
            selected = frozen_tables[idx]
            confirm = input(f"REJECT changes for '{selected['key']}'? [y/N]: ").strip().lower()
            if confirm == 'y':
                ok = registry.reject_change(selected["key"])
                if ok:
                    print(f"\n{GREEN}[SUCCESS] Change rejected. Retained old baseline.{RESET}")
                    notifier.notify_change_reviewed(selected["table"], approved=False, pair_name=selected["pipeline"])
                    print(f"  {GREEN}[NOTIFY] Telegram alert sent.{RESET}")
                else:
                    print(f"{RED}[ERROR] Rejection failed.{RESET}")
            else:
                print("Cancelled.")
        else:
            print(f"{RED}Invalid selection.{RESET}")
    except ValueError:
        print(f"{RED}Invalid input.{RESET}")

    input("\nPress Enter...")


def action_system_overview(config: dict):
    print(f"\n{BOLD}SYSTEM TOPOLOGY:{RESET}")
    print("-" * 86)
    print(f"  Registry : {config['registry']['dir']}")
    print(f"  Interval : {config['scheduler']['interval_seconds']}s")
    print(f"  Kafka    : {CYAN}{config.get('kafka', {}).get('bootstrap_servers', 'N/A')}{RESET}")
    print(f"  Telegram : {config.get('telegram', {}).get('chat_id', 'N/A')}")
    print(f"\n  {BOLD}Pipelines:{RESET}")
    for p in config.get("pairs", []):
        name = p.get("name")
        src_type = p.get("source", {}).get("type")
        tgt_type = p.get("target", {}).get("type") if p.get("target") else "Self-Monitor"
        tables = ", ".join(p.get("tables", []))
        print(f"   * {CYAN}{name:<22}{RESET} ({src_type} ➔ {tgt_type}) | Tables: {YELLOW}{tables}{RESET}")
    print("-" * 86)
    input("\nPress Enter...")


def main():
    config_path = ROOT_DIR / "config" / "main.yaml"
    try:
        config = load_config(str(config_path))
    except Exception as e:
        print(f"{RED}[ERROR] Failed to load config/main.yaml: {e}{RESET}")
        sys.exit(1)

    registry = SchemaRegistry(config["registry"]["dir"])
    notifier = TelegramNotifier(
        bot_token=config["telegram"]["bot_token"],
        chat_id=config["telegram"]["chat_id"],
    )

    menu_idx = 0
    menu_items = [
        ("1", "Explorer (Dual Panel Split View)"),
        ("2", "List Frozen Tables"),
        ("3", "Inspect Draft DDL Details"),
        ("4", "Approve Schema Change & Execute DDL"),
        ("5", "Reject Schema Change & Retain Baseline"),
        ("6", "View System Topology"),
        ("0", "Exit"),
    ]

    while True:
        clear_screen()
        print_header()
        frozen_tables = get_frozen_tables(registry, config)
        all_tables = get_all_monitored_tables(registry, config)

        frozen_str = f"{RED}{len(frozen_tables)} frozen{RESET}" if frozen_tables else f"{GREEN}0 frozen{RESET}"
        monitored_str = f"{CYAN}{len(all_tables)} monitored{RESET}"
        print(f"\n  Status: {frozen_str} | {monitored_str}")
        print(f"\n  {BOLD}COMMANDS:{RESET}")

        for idx, (code, title) in enumerate(menu_items):
            if idx == menu_idx:
                print(f"   {BG_CYAN} ▶ [{code}] {title:<45} {RESET}")
            else:
                print(f"     [{code}] {title}")
        print("-" * 86)
        print(f" {BOLD}[UP/DOWN]{RESET} Move   {BOLD}[ENTER]{RESET} Select")

        key = get_key()

        if key == 'UP':
            menu_idx = (menu_idx - 1) % len(menu_items)
        elif key == 'DOWN':
            menu_idx = (menu_idx + 1) % len(menu_items)
        elif key == 'ENTER':
            choice = menu_items[menu_idx][0]
            if choice == "1":
                menu_interactive_split_view(all_tables, config)
            elif choice == "2":
                clear_screen()
                print_header()
                menu_list_frozen(frozen_tables)
                input("\nPress Enter...")
            elif choice == "3":
                clear_screen()
                print_header()
                action_view_details(registry, frozen_tables)
            elif choice == "4":
                clear_screen()
                print_header()
                action_approve(registry, config, notifier, frozen_tables)
            elif choice == "5":
                clear_screen()
                print_header()
                action_reject(registry, notifier, frozen_tables)
            elif choice == "6":
                clear_screen()
                print_header()
                action_system_overview(config)
            elif choice == "0":
                print("\nGoodbye!\n")
                break


if __name__ == "__main__":
    main()
