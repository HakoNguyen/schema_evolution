import json
from pathlib import Path
from dataclasses import asdict, is_dataclass
from datetime import datetime
import copy

from src.schema_evolution.engines.base import (
    BaseEngine,
    ColumnSchema,
    ChangeType,
    ChangeSeverity,
    ForeignKeySchema,
    SchemaChange,
    TableSchema,
)

CHANGE_SEVERITY_MAP: dict[ChangeType, ChangeSeverity] = {
    ChangeType.ADD_COLUMN: ChangeSeverity.NON_BREAKING,  # không dùng trực tiếp, xem _classify_add_column_severity
    ChangeType.DROP_COLUMN: ChangeSeverity.BREAKING,
    ChangeType.RENAME_COLUMN: ChangeSeverity.BREAKING,
    ChangeType.WIDEN_TYPE: ChangeSeverity.NON_BREAKING,
    ChangeType.NARROW_TYPE: ChangeSeverity.BREAKING,
    ChangeType.CHANGE_TYPE_INCOMPATIBLE: ChangeSeverity.BREAKING,
    ChangeType.NOT_NULL_TO_NULLABLE: ChangeSeverity.NON_BREAKING,
    ChangeType.NULLABLE_TO_NOT_NULL: ChangeSeverity.BREAKING,
    ChangeType.ADD_PRIMARY_KEY: ChangeSeverity.BREAKING,
    ChangeType.DROP_PRIMARY_KEY: ChangeSeverity.BREAKING,
    ChangeType.CHANGE_PRIMARY_KEY: ChangeSeverity.BREAKING,
    ChangeType.ADD_FOREIGN_KEY: ChangeSeverity.BREAKING,
    ChangeType.DROP_FOREIGN_KEY: ChangeSeverity.NON_BREAKING,
    ChangeType.CHANGE_FOREIGN_KEY_TARGET: ChangeSeverity.BREAKING,
    ChangeType.CHANGE_FOREIGN_KEY_ACTION: ChangeSeverity.BREAKING,
}

class SchemaRegistry:
    def __init__(self, registry_dir: str):
        self.registry_dir = Path(registry_dir)
        self.registry_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, table_name: str) -> Path:
        return self.registry_dir / f"{table_name}.json"

    def _read_raw(self, table_name: str) -> dict | None:
        path = self._path(table_name)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def load(self, table_name: str) -> TableSchema | None:
        raw = self._read_raw(table_name)
        if raw is None:
            return None
        s = raw["table_schema"]
        return TableSchema(
            table_name=s["table_name"],
            columns=[ColumnSchema(**c) for c in s.get("columns", [])],
            primary_key=s.get("primary_key", []),
            foreign_keys=[ForeignKeySchema(**fk) for fk in s.get("foreign_keys", [])],
        )

    def save(self, table_name: str, schema: TableSchema) -> None:
        current_frozen = self.is_frozen(table_name)
        new_version = self.get_version(table_name) + 1
        data = {
            "table_schema": asdict(schema),
            "is_frozen": current_frozen,
            "version": new_version,
            "updated_at": datetime.now().isoformat(),
        }
        with open(self._path(table_name), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # Ghi thêm 1 bản bất biến vào history/ — mỗi lần save() thành công
        # là 1 version mới (V1, V2, ..., Vn), không ghi đè các bản cũ.
        with open(self._history_path(table_name, new_version), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def is_frozen(self, table_name: str) -> bool:
        raw = self._read_raw(table_name)
        if raw is None:
            return False
        return raw.get("is_frozen", False)

    def get_version(self, table_name: str) -> int:
        raw = self._read_raw(table_name)
        if raw is None:
            return 0
        return raw.get("version", 0)

    def _history_path(self, table_name: str, version: int) -> Path:
        d = self.registry_dir / "history" / table_name
        d.mkdir(parents=True, exist_ok=True)
        return d / f"v{version}.json"

    def list_versions(self, table_name: str) -> list[int]:
        d = self.registry_dir / "history" / table_name
        if not d.exists():
            return []
        versions = []
        for p in d.glob("v*.json"):
            try:
                versions.append(int(p.stem[1:]))
            except ValueError:
                continue
        return sorted(versions)

    def load_version(self, table_name: str, version: int) -> TableSchema | None:
        path = self._history_path(table_name, version)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        s = raw["table_schema"]
        return TableSchema(
            table_name=s["table_name"],
            columns=[ColumnSchema(**c) for c in s.get("columns", [])],
            primary_key=s.get("primary_key", []),
            foreign_keys=[ForeignKeySchema(**fk) for fk in s.get("foreign_keys", [])],
        )

    def get_version_timestamp(self, table_name: str, version: int) -> str | None:
        """Trả về updated_at (ISO string) của 1 version cụ thể, dùng để
        hiển thị mốc thời gian trong Streamlit UI. None nếu version không tồn tại."""
        path = self._history_path(table_name, version)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return raw.get("updated_at")

    def set_frozen(self, table_name: str, frozen: bool) -> None:
        raw = self._read_raw(table_name)
        if raw is None:
            return
        raw["is_frozen"] = frozen
        with open(self._path(table_name), "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)

    def _draft_path(self, table_name: str) -> Path:
        return self.registry_dir / f"{table_name}.draft.json"

    def save_draft(self, table_name: str, schema: TableSchema, breaking_changes: list) -> None:
        # Lưu bản schema "ứng cử viên" (đầy đủ, chưa được duyệt) tách biệt
        # khỏi snapshot chính đang dùng — để approve_change/reject_change
        # dùng sau này.
        data = {
            "table_schema": asdict(schema),
            "breaking_changes": [_serialize_change(c) for c in breaking_changes],
            "detected_at": datetime.now().isoformat(),
        }
        with open(self._draft_path(table_name), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_draft(self, table_name: str) -> dict | None:
        path = self._draft_path(table_name)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def approve_change(self, table_name: str) -> bool:
        draft = self.load_draft(table_name)
        if draft is None:
            return False
        s = draft["table_schema"]
        new_schema = TableSchema(
            table_name=s["table_name"],
            columns=[ColumnSchema(**c) for c in s.get("columns", [])],
            primary_key=s.get("primary_key", []),
            foreign_keys=[ForeignKeySchema(**fk) for fk in s.get("foreign_keys", [])],
        )
        self.set_frozen(table_name, False)
        self.save(table_name, new_schema)
        self._draft_path(table_name).unlink(missing_ok=True)
        return True

    def reject_change(self, table_name: str) -> bool:
        draft = self.load_draft(table_name)
        if draft is None:
            return False
        self.set_frozen(table_name, False)
        self._draft_path(table_name).unlink(missing_ok=True)
        return True


def _serialize_value(v):
    if v is None:
        return None
    if is_dataclass(v):
        return asdict(v)
    if isinstance(v, list):
        return v
    return str(v)


def _serialize_change(change: SchemaChange) -> dict:
    # Chỉ dùng để hiển thị trên Streamlit UI, KHÔNG dùng để deserialize
    # lại thành SchemaChange — bản schema đầy đủ đã có trong table_schema.
    return {
        "change_type": change.change_type.value,
        "severity": change.severity.value,
        "column_name": change.column_name,
        "constraint_name": change.constraint_name,
        "old_value": _serialize_value(change.old_value),
        "new_value": _serialize_value(change.new_value),
    }


def _classify_add_column_severity(col: ColumnSchema) -> ChangeSeverity:
    # IsCompatible(): cột mới an toàn nếu nullable hoặc có default
    if col.nullable or col.default is not None:
        return ChangeSeverity.NON_BREAKING
    return ChangeSeverity.BREAKING


TYPE_HIERARCHY: dict[str, list[str]] = {
    "integer": ["smallint", "int", "bigint"],
    "floating": ["float", "double"],
}
TYPE_TO_FAMILY: dict[str, str] = {
    t: family for family, types in TYPE_HIERARCHY.items() for t in types
}


def _classify_type_change(old_col: ColumnSchema, new_col: ColumnSchema) -> ChangeType:
    if old_col.data_type == new_col.data_type:
        if old_col.max_length is not None and new_col.max_length is not None:
            if new_col.max_length > old_col.max_length:
                return ChangeType.WIDEN_TYPE
            return ChangeType.NARROW_TYPE
        return ChangeType.WIDEN_TYPE

    old_family = TYPE_TO_FAMILY.get(old_col.data_type)
    new_family = TYPE_TO_FAMILY.get(new_col.data_type)
    if old_family is not None and old_family == new_family:
        hierarchy = TYPE_HIERARCHY[old_family]
        if hierarchy.index(new_col.data_type) > hierarchy.index(old_col.data_type):
            return ChangeType.WIDEN_TYPE
        return ChangeType.NARROW_TYPE

    return ChangeType.CHANGE_TYPE_INCOMPATIBLE


def compare_schemas(old: TableSchema, new: TableSchema) -> list[SchemaChange]:
    """
    So sánh 2 TableSchema (old = Registry, new = crawl trực tiếp từ
    Source), trả về list[SchemaChange] mô tả tất cả khác biệt.

    Gợi ý thuật toán (theo 3 nhóm, làm tuần tự để dễ test riêng từng nhóm):

    1. So sánh columns (theo tên):
       - Cột có trong new, không có trong old -> ADD_COLUMN
       - Cột có trong old, không có trong new -> DROP_COLUMN
         (v1: KHÔNG cố suy luận rename, xem phần ghi chú ở đầu file)
       - Cột có ở cả 2, khác nhau ở:
           - data_type -> WIDEN_TYPE / NARROW_TYPE / CHANGE_TYPE_INCOMPATIBLE
             (quyết định logic so sánh "rộng hơn hay hẹp hơn" —
             gợi ý: chỉ so sánh được trong cùng 1 họ type, VD so
             max_length nếu cùng là varchar; khác họ type hẳn thì luôn
             là CHANGE_TYPE_INCOMPATIBLE)
           - nullable: True->False = NULLABLE_TO_NOT_NULL,
             False->True = NOT_NULL_TO_NULLABLE

    2. So sánh primary_key (list[str]):
       - old rỗng, new có -> ADD_PRIMARY_KEY
       - old có, new rỗng -> DROP_PRIMARY_KEY
       - cả 2 đều có nhưng khác nội dung -> CHANGE_PRIMARY_KEY

    3. So sánh foreign_keys (theo constraint_name):
       - có trong new, không có trong old -> ADD_FOREIGN_KEY
       - có trong old, không có trong new -> DROP_FOREIGN_KEY
       - cùng constraint_name nhưng khác ref_table/ref_column
         -> CHANGE_FOREIGN_KEY_TARGET
       - cùng constraint_name nhưng khác on_delete/on_update
         -> CHANGE_FOREIGN_KEY_ACTION

    Mỗi SchemaChange tạo ra cần gán severity từ CHANGE_SEVERITY_MAP,
    không tự quyết định severity rải rác trong hàm này.
    """
    changes: list[SchemaChange] = []
    old_cols = {c.name: c for c in old.columns}
    new_cols = {c.name: c for c in new.columns}

    for name, col in new_cols.items():
        if name not in old_cols:
            changes.append(SchemaChange(
                table_name=new.table_name,
                change_type=ChangeType.ADD_COLUMN,
                severity=_classify_add_column_severity(col),
                column_name=name,
                old_value=None,
                new_value=col,
            ))

    for name, col in old_cols.items():
        if name not in new_cols:
            changes.append(SchemaChange(
                table_name=old.table_name,
                change_type=ChangeType.DROP_COLUMN,
                severity=CHANGE_SEVERITY_MAP[ChangeType.DROP_COLUMN],
                column_name=name,
                old_value=col,
                new_value=None,
            ))

    for name in old_cols.keys() & new_cols.keys():
        old_col = old_cols[name]
        new_col = new_cols[name]

        type_changed = (
            old_col.data_type != new_col.data_type
            or old_col.max_length != new_col.max_length
        )
        if type_changed:
            change_type = _classify_type_change(old_col, new_col)
            changes.append(SchemaChange(
                table_name=new.table_name,
                change_type=change_type,
                severity=CHANGE_SEVERITY_MAP[change_type],
                column_name=name,
                old_value=old_col,
                new_value=new_col,
            ))
        if old_col.nullable != new_col.nullable:
            change_type = (
                ChangeType.NOT_NULL_TO_NULLABLE if new_col.nullable
                else ChangeType.NULLABLE_TO_NOT_NULL
            )
            changes.append(SchemaChange(
                table_name=new.table_name,
                change_type=change_type,
                severity=CHANGE_SEVERITY_MAP[change_type],
                column_name=name,
                old_value=old_col,
                new_value=new_col,
            ))

    if old.primary_key != new.primary_key:
        if not old.primary_key and new.primary_key:
            pk_change = ChangeType.ADD_PRIMARY_KEY
        elif old.primary_key and not new.primary_key:
            pk_change = ChangeType.DROP_PRIMARY_KEY
        else:
            pk_change = ChangeType.CHANGE_PRIMARY_KEY
        changes.append(SchemaChange(
            table_name=new.table_name,
            change_type=pk_change,
            severity=CHANGE_SEVERITY_MAP[pk_change],
            column_name=None,
            old_value=old.primary_key,
            new_value=new.primary_key,
        ))

    old_fks = {fk.constraint_name: fk for fk in old.foreign_keys}
    new_fks = {fk.constraint_name: fk for fk in new.foreign_keys}

    for cname, fk in new_fks.items():
        if cname not in old_fks:
            changes.append(SchemaChange(
                table_name=new.table_name,
                change_type=ChangeType.ADD_FOREIGN_KEY,
                severity=CHANGE_SEVERITY_MAP[ChangeType.ADD_FOREIGN_KEY],
                column_name=fk.column_name,
                constraint_name=cname,
                old_value=None,
                new_value=fk,
            ))

    for cname, fk in old_fks.items():
        if cname not in new_fks:
            changes.append(SchemaChange(
                table_name=old.table_name,
                change_type=ChangeType.DROP_FOREIGN_KEY,
                severity=CHANGE_SEVERITY_MAP[ChangeType.DROP_FOREIGN_KEY],
                column_name=fk.column_name,
                constraint_name=cname,
                old_value=fk,
                new_value=None,
            ))

    for cname in old_fks.keys() & new_fks.keys():
        old_fk = old_fks[cname]
        new_fk = new_fks[cname]
        if old_fk.ref_table != new_fk.ref_table or old_fk.ref_column != new_fk.ref_column:
            changes.append(SchemaChange(
                table_name=new.table_name,
                change_type=ChangeType.CHANGE_FOREIGN_KEY_TARGET,
                severity=CHANGE_SEVERITY_MAP[ChangeType.CHANGE_FOREIGN_KEY_TARGET],
                column_name=new_fk.column_name,
                constraint_name=cname,
                old_value=old_fk,
                new_value=new_fk,
            ))
        elif old_fk.on_delete != new_fk.on_delete or old_fk.on_update != new_fk.on_update:
            changes.append(SchemaChange(
                table_name=new.table_name,
                change_type=ChangeType.CHANGE_FOREIGN_KEY_ACTION,
                severity=CHANGE_SEVERITY_MAP[ChangeType.CHANGE_FOREIGN_KEY_ACTION],
                column_name=new_fk.column_name,
                constraint_name=cname,
                old_value=old_fk,
                new_value=new_fk,
            ))

    return changes


def apply_non_breaking_changes(engine: BaseEngine, changes: list[SchemaChange]) -> list[SchemaChange]:
    if not changes:
        return []

    ddls = engine.generate_ddl(changes)
    applied = []
    for change, ddl in zip(changes, ddls):
        try:
            engine.execute_ddl(ddl)
            applied.append(change)
        except Exception as e:
            print(
                f"[apply_non_breaking_changes] Lỗi khi áp dụng "
                f"{change.change_type} lên {change.table_name}.{change.column_name}: {e}"
            )
    return applied


def _merge_schema(base: TableSchema, applied_changes: list[SchemaChange]) -> TableSchema:
    merged = copy.deepcopy(base)
    cols_by_name = {c.name: c for c in merged.columns}

    for change in applied_changes:
        if change.change_type == ChangeType.ADD_COLUMN:
            merged.columns.append(change.new_value)
        elif change.change_type == ChangeType.WIDEN_TYPE:
            col = cols_by_name.get(change.column_name)
            if col is not None:
                col.data_type = change.new_value.data_type
                col.max_length = change.new_value.max_length
        elif change.change_type == ChangeType.NOT_NULL_TO_NULLABLE:
            col = cols_by_name.get(change.column_name)
            if col is not None:
                col.nullable = True
        elif change.change_type == ChangeType.DROP_FOREIGN_KEY:
            merged.foreign_keys = [
                fk for fk in merged.foreign_keys
                if fk.constraint_name != change.constraint_name
            ]
    return merged


def _extract_pair_name(registry_key: str) -> str | None:
    """
    registry_key thường có dạng "{pair_name}__{table_name}" (do
    scheduler.py build) — tách lấy pair_name để hiện ngữ cảnh rõ hơn
    trong Telegram (biết đang nói về pair/DB nào, không chỉ tên bảng).
    Trả về None nếu registry_key không theo đúng format này.
    """
    if registry_key and "__" in registry_key:
        return registry_key.rsplit("__", 1)[0]
    return None


def run_evolution_check(
    source_engine: BaseEngine,
    target_engine: BaseEngine,
    table_name: str,
    registry: SchemaRegistry,
    notifier=None,
    registry_key: str | None = None,
) -> dict:
    """
    source_engine: DB bị theo dõi thay đổi — chỉ dùng để crawl_metadata,
        KHÔNG bao giờ bị execute_ddl (không tự sửa cấu trúc DB nguồn).
    target_engine: DB cần tự động đồng bộ theo — chỉ dùng để
        apply_non_breaking_changes (execute_ddl), KHÔNG dùng để crawl.
        Có thể khác loại DB với source (VD Postgres -> MySQL), vì
        generate_ddl()/execute_ddl() của target_engine tự lo đúng cú
        pháp riêng của nó.

    Luồng xử lý:
    1. Nếu registry.is_frozen(table_name) -> return sớm, không làm gì
       thêm (đang chờ approve trên UI), có thể trả về status="frozen".
    2. current_schema = source_engine.crawl_metadata(table_name)
    3. old_schema = registry.load(table_name)
       - Nếu None (lần đầu crawl bảng này): registry.save(...) luôn,
         return status="initialized", không coi là "thay đổi". Giả định
         target đã có cấu trúc khớp source lúc khởi tạo (VD cả 2 đều
         chạy init_source.sql).
    4. changes = compare_schemas(old_schema, current_schema)
       - Nếu changes rỗng -> return status="no_change"
    5. Tách changes thành non_breaking và breaking (theo severity).
    6. Nếu có non_breaking: apply_non_breaking_changes(target_engine, ...)
       — DDL chạy trên TARGET, không đụng vào source. Rồi cập nhật
       registry.save(...) — CHỈ cập nhật phần đã áp dụng thành công.
    7. Nếu có breaking: registry.set_frozen(table_name, True), gọi
       notifier để bắn Telegram alert, KHÔNG tự ý execute DDL.
    8. Return dict tổng hợp: {status, non_breaking_applied, breaking_pending}
       để scheduler.py / Streamlit UI hiển thị.
    """

    key = registry_key if registry_key is not None else table_name

    if registry.is_frozen(key):
        return {"status": "frozen", "table": table_name}

    current_schema = source_engine.crawl_metadata(table_name)
    old_schema = registry.load(key)

    if old_schema is None:
        registry.save(key, current_schema)
        return {"status": "initialized", "table": table_name}

    changes = compare_schemas(old_schema, current_schema)
    if not changes:
        return {"status": "no_change", "table": table_name}

    non_breaking = [c for c in changes if c.severity == ChangeSeverity.NON_BREAKING]
    breaking = [c for c in changes if c.severity == ChangeSeverity.BREAKING]

    if not non_breaking:
        applied = []
    elif target_engine is not None:
        applied = apply_non_breaking_changes(target_engine, non_breaking)
    else:
        # Detection-only: không có đích để chạy DDL, ghi nhận thẳng.
        applied = non_breaking

    merged_schema = _merge_schema(old_schema, applied) if applied else old_schema

    if breaking:
        registry.set_frozen(key, True)
        registry.save_draft(key, current_schema, breaking)
        if applied:
            registry.save(key, merged_schema)
        if notifier is not None:
            notifier.notify_breaking_changes(table_name, breaking, pair_name=_extract_pair_name(key))
        status = "breaking_detected"
    else:
        registry.save(key, merged_schema)
        if notifier is not None and applied:
            notifier.notify_auto_sync_applied(table_name, applied, pair_name=_extract_pair_name(key))
        status = "changes_applied"

    return {
        "status": status,
        "table": table_name,
        "non_breaking_applied": applied,
        "breaking_pending": breaking,
    }


def approve_change_and_sync(
    target_engine: BaseEngine | None,
    table_name: str,
    registry: SchemaRegistry,
    registry_key: str | None = None,
) -> dict:
    """
    Approve 1 bảng đang bị frozen, ĐỒNG THỜI tự động chạy DDL tương ứng
    lên target — khép kín vòng lặp Approve, khác với
    SchemaRegistry.approve_change() (chỉ cập nhật Registry, KHÔNG đụng
    DB nào cả).

    Nếu target_engine=None (chế độ detection-only, không có đích thật):
    chỉ cập nhật Registry như approve_change() thông thường, không có
    DDL nào để chạy.

    LƯU Ý: draft chỉ lưu bản tóm tắt breaking_changes (đã serialize,
    không phải SchemaChange đầy đủ) để hiển thị UI — không đủ để build
    lại DDL chính xác. Nên hàm này tính lại TOÀN BỘ diff (old registry vs
    schema trong draft) bằng compare_schemas(), lấy đúng SchemaChange gốc
    (kể cả breaking) để sinh DDL, thay vì cố deserialize draft.
    """
    key = registry_key if registry_key is not None else table_name

    if not registry.is_frozen(key):
        return {"status": "not_frozen", "table": table_name}

    draft = registry.load_draft(key)
    if draft is None:
        return {"status": "no_draft", "table": table_name}

    old_schema = registry.load(key)
    s = draft["table_schema"]
    new_schema = TableSchema(
        table_name=s["table_name"],
        columns=[ColumnSchema(**c) for c in s.get("columns", [])],
        primary_key=s.get("primary_key", []),
        foreign_keys=[ForeignKeySchema(**fk) for fk in s.get("foreign_keys", [])],
    )

    all_changes = compare_schemas(old_schema, new_schema) if old_schema is not None else []

    applied = []
    failed = []
    if target_engine is not None and all_changes:
        ddls = target_engine.generate_ddl(all_changes)
        for change, ddl in zip(all_changes, ddls):
            try:
                target_engine.execute_ddl(ddl)
                applied.append(change)
            except Exception as e:
                failed.append(change)
                print(
                    f"[approve_change_and_sync] Lỗi khi áp dụng "
                    f"{change.change_type} lên target ({table_name}): {e}"
                )

    registry.approve_change(key)

    return {
        "status": "approved",
        "table": table_name,
        "applied_to_target": applied,
        "failed_on_target": failed,
    }