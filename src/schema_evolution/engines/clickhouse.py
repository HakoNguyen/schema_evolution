import re

from src.schema_evolution.engines.base import (
    BaseEngine, 
    ColumnSchema, 
    ForeignKeySchema, 
    TableSchema, 
    SchemaChange, 
    ChangeType,
    render_portable_default,
    sandbox_table,
)

import clickhouse_connect

TYPE_MAP = {
    "String": "text",
    "Int8": "smallint",
    "Int16": "smallint",
    "Int32": "int",
    "Int64": "bigint",
    "UInt8": "smallint",
    "UInt16": "smallint",
    "UInt32": "int",
    "UInt64": "bigint",
    "Float32": "float",
    "Float64": "double",
    "Bool": "boolean",
    "Date": "date",
    "DateTime": "timestamp",
    "DateTime64": "timestamp",
    "UUID": "uuid",
}

NORMALIZED_TO_CLICKHOUSE = {
    "text": "String",
    "char": "String",
    "varchar": "String",
    "smallint": "Int16",
    "int": "Int32",
    "bigint": "Int64",
    "float": "Float32",
    "double": "Float64",
    "boolean": "Bool",
    "date": "Date32",  # Date chỉ từ 1970: ngày sinh/ngày cũ hơn bị ghi thành 1970-01-01
    # Micro giây = độ chính xác tối đa của Postgres/MySQL -> không mất phần dưới giây.
    "timestamp": "DateTime64(6)",
    "timestamptz": "DateTime64(6, 'UTC')",
    "uuid": "UUID",
    # NUMERIC không ghi precision: Float64 làm tròn tiền tệ -> dùng Decimal rộng nhất.
    # shortcut: giá trị >38 chữ số phần nguyên bị ClickHouse từ chối (lỗi rõ ràng, không làm tròn ngầm).
    "numeric": "Decimal(76, 38)",
    "json": "String",
}

SANDBOX_SAMPLE_ROWS = 10000

FIXED_STRING_RE = re.compile(r"^FixedString\((\d+)\)$")

def _q(identifier: str) -> str:
    """Tên cột trong backtick: cột như unit-price/order không làm hỏng câu DDL."""
    return "`" + identifier.replace("`", "``") + "`"


def _nullable(ch_type: str) -> str:
    """ClickHouse cấm Nullable(LowCardinality(T)) (lỗi 43); dạng đúng là LowCardinality(Nullable(T))."""
    if ch_type.startswith(("Nullable(", "LowCardinality(Nullable(")):
        return ch_type
    if ch_type.startswith("LowCardinality("):
        return f"LowCardinality(Nullable({ch_type[len('LowCardinality('):-1]}))"
    return f"Nullable({ch_type})"


class ClickHouseEngine(BaseEngine): 
    @property
    def engine_type(self) -> str:
        return "clickhouse"

    def connect(self) -> None:
        cfg = self.connection_config 
        self.connection = clickhouse_connect.get_client(
            host=cfg["host"], 
            port=cfg["port"],
            username=cfg.get("user", "default"),
            password=cfg.get("password", ""),
            database=cfg["database"],
            connect_timeout=cfg.get("connect_timeout", 5),
        )

    def disconnect(self) -> None:
        if self.connection is not None: 
            self.connection.close()
            self.connection = None

    def health_check(self) -> bool:
        if self.connection is None: 
            return False
        try: 
            self.connection.command("SELECT 1")
            return True
        except Exception: 
            return False

    def list_tables(self) -> list[str]:
        query = """
        SELECT name FROM system.tables 
        WHERE database = currentDatabase() AND engine NOT LIKE '%View%'
        """
        result = self.connection.query(query)
        return [row[0] for row in result.result_rows]

    def crawl_metadata(self, table_name: str) -> TableSchema:
        return TableSchema(
            table_name=table_name, 
            columns=self._crawl_columns(table_name),
            primary_key=self._crawl_primary_key(table_name),
            foreign_keys=[],
        )

    def _crawl_columns(self, table_name: str) -> list[ColumnSchema]: 
        query = """
        SELECT name, type, default_expression
        FROM system.columns
        WHERE database = currentDatabase() AND table = %(table_name)s 
        ORDER BY position 
        """
        result = self.connection.query(query, parameters={"table_name": table_name})

        columns = []
        for name, raw_type, default_expr in result.result_rows: 
            nullable, inner_type, max_length = self._parse_type(raw_type)
            columns.append(
                ColumnSchema(
                    name=name,
                    data_type=self._normalize_type(inner_type),
                    nullable=nullable,
                    default=default_expr if default_expr else None, 
                    max_length=max_length,
                )
            )
        return columns

    def _crawl_primary_key(self, table_name: str) -> list[str]:
        query = """
        SELECT primary_key FROM system.tables
        WHERE database = currentDatabase() AND name = %(table_name)s
        """

        result = self.connection.query(query, parameters={"table_name": table_name})
        if not result.result_rows or not result.result_rows[0][0]:
            return []
        raw = result.result_rows[0][0]
        return [col.strip() for col in raw.split(",") if col.strip()]

    def _parse_type(self, raw_type: str) -> tuple[bool, str, int | None]:
        nullable = False
        inner = raw_type
        if inner.startswith("Nullable(") and inner.endswith(")"):
            nullable = True
            inner = inner[len("Nullable("): -1]

        fixed_match = FIXED_STRING_RE.match(inner)
        if fixed_match: 
            return nullable, "String", int(fixed_match.group(1))

        return nullable, inner, None

    def _normalize_type(self, ch_type: str) -> str:
        return TYPE_MAP.get(ch_type, "json")

    def _render_type(self, column: ColumnSchema) -> str:
        base_type = NORMALIZED_TO_CLICKHOUSE.get(column.data_type, "String")
        if column.data_type == "numeric" and column.precision:
            base_type = f"Decimal({min(column.precision, 76)},{column.scale or 0})"
        # char(n)/varchar(n) -> String: FixedString(n) tính theo BYTE (tiếng Việt UTF-8 bị cắt/NULL) và đệm byte 0.
        if column.nullable: 
            return f"Nullable({base_type})"
        return base_type

    def generate_ddl(self, changes: list[SchemaChange]) -> list[str]:
        statements = []
        for change in changes:
            if change.change_type == ChangeType.ADD_COLUMN:
                col = change.new_value
                type_sql = self._render_type(col)
                default = render_portable_default(col.default, now_sql="now()")
                default_sql = f" DEFAULT {default}" if default is not None else ""
                statements.append(
                    f"ALTER TABLE {change.table_name} "
                    f"ADD COLUMN {_q(col.name)} {type_sql}{default_sql}"
                )
            elif change.change_type == ChangeType.WIDEN_TYPE:
                col = change.new_value
                type_sql = self._render_type(col)
                statements.append(
                    f"ALTER TABLE {change.table_name} "
                    f"MODIFY COLUMN {_q(change.column_name)} {type_sql}"
                )
            elif change.change_type == ChangeType.NOT_NULL_TO_NULLABLE:
                # Giữ đúng kiểu đang có ở đích (VD UInt32 tạo tay), chỉ thêm Nullable: dựng lại kiểu
                # từ registry có thể đổi UInt32 -> Int32 và làm 4294967295 thành -1.
                current = self._current_type(change.table_name, change.column_name)
                if current is None:
                    type_sql = self._render_type(change.new_value)  # col.nullable đã là True
                else:
                    type_sql = _nullable(current)
                statements.append(
                    f"ALTER TABLE {change.table_name} "
                    f"MODIFY COLUMN {_q(change.column_name)} {type_sql}"
                )
            elif change.change_type == ChangeType.DROP_FOREIGN_KEY:
                # ClickHouse không có FK -> không bao giờ thực sự phát sinh
                # change_type này khi target là ClickHouse, nhưng vẫn xử lý
                # tường minh (no-op) để không rơi vào nhánh else gây lỗi.
                statements.append(f"-- NO-OP: ClickHouse khong co FK ({change.constraint_name})")
            # --- Các loại BREAKING dưới đây chỉ dùng khi Approve (sau khi
            # kỹ sư đã duyệt) — không bao giờ được apply_non_breaking_changes
            # gọi tới trong luồng auto-sync thông thường. ---
            elif change.change_type == ChangeType.RENAME_COLUMN:
                old_name = change.column_name
                new_name = change.new_value.name if hasattr(change.new_value, 'name') else str(change.new_value)
                statements.append(
                    f"ALTER TABLE {change.table_name} RENAME COLUMN {_q(old_name)} TO {_q(new_name)}"
                )
            elif change.change_type == ChangeType.DROP_COLUMN:
                statements.append(
                    f"ALTER TABLE {change.table_name} DROP COLUMN {_q(change.column_name)}"
                )
            elif change.change_type in (ChangeType.NARROW_TYPE, ChangeType.CHANGE_TYPE_INCOMPATIBLE):
                col = change.new_value
                type_sql = self._render_type(col)
                statements.append(
                    f"ALTER TABLE {change.table_name} "
                    f"MODIFY COLUMN {_q(change.column_name)} {type_sql}"
                )
            elif change.change_type == ChangeType.NULLABLE_TO_NOT_NULL:
                col = change.new_value
                type_sql = self._render_type(col)  # col.nullable đã là False
                statements.append(
                    f"ALTER TABLE {change.table_name} "
                    f"MODIFY COLUMN {_q(change.column_name)} {type_sql}"
                )
            elif change.change_type in (ChangeType.ADD_FOREIGN_KEY, ChangeType.CHANGE_FOREIGN_KEY_TARGET,
                                        ChangeType.CHANGE_FOREIGN_KEY_ACTION):
                # Nguồn Postgres/MySQL đổi khoá ngoại: ClickHouse không có FK nên không có DDL nào để chạy.
                # Sau khi kỹ sư duyệt, chỉ cần cập nhật baseline; raise ở đây sẽ làm Approve thất bại mãi.
                statements.append(f"-- NO-OP: ClickHouse khong co FK ({change.constraint_name})")
            else:
                raise ValueError(
                    f"ClickHouseEngine.generate_ddl không hỗ trợ "
                    f"change_type={change.change_type}"
                )
        return statements
 
    def _current_type(self, table: str, column: str) -> str | None:
        """Kiểu thật của cột ở đích (None nếu chưa kết nối/không thấy)."""
        if self.connection is None:
            return None
        database, _, name = table.rpartition(".")
        rows = self.connection.query(
            "SELECT type FROM system.columns WHERE database = if(%(d)s = '', currentDatabase(), %(d)s) "
            "AND table = %(t)s AND name = %(c)s",
            parameters={"d": database, "t": name, "c": column},
        ).result_rows
        return rows[0][0] if rows else None

    def execute_ddl(self, ddl_statement: str) -> None:
        if ddl_statement.startswith("--"):
            return  # no-op, không gửi lên server
        self.connection.command(ddl_statement)

    def test_ddl(self, changes: list[SchemaChange]) -> tuple[bool, str]:
        if not changes:
            return True, "No changes to test."
        
        tables = {change.table_name for change in changes}
        created_sandboxes = []
        
        try:
            # 1. Create sandbox tables
            for table_name in tables:
                sandbox_name = sandbox_table(table_name)
                self.connection.command(f"DROP TABLE IF EXISTS {sandbox_name}")
                self.connection.command(f"CREATE TABLE {sandbox_name} AS {table_name}")
                created_sandboxes.append(sandbox_name)
                # Copy mẫu dữ liệu thật để bắt lỗi chuyển kiểu/NOT NULL.
                self.connection.command(
                    f"INSERT INTO {sandbox_name} SELECT * FROM {table_name} LIMIT {SANDBOX_SAMPLE_ROWS}"
                )
            
            # 2. Apply DDL to sandbox tables
            statements = self.generate_ddl(changes)
            for stmt, change in zip(statements, changes):
                if stmt.startswith("--"):
                    continue  # no-op (VD khoá ngoại): server báo "Empty query" nếu gửi lên
                sandbox_name = sandbox_table(change.table_name)
                sandbox_stmt = stmt.replace(
                    f"ALTER TABLE {change.table_name} ",
                    f"ALTER TABLE {sandbox_name} ",
                    1
                )
                # mutations_sync=1: MODIFY COLUMN là mutation bất đồng bộ —
                # phải chờ chạy xong trên dữ liệu thì lỗi chuyển kiểu mới lộ ra.
                self.connection.command(sandbox_stmt, settings={"mutations_sync": 1})

            return True, "Sandbox test passed (applied to clone table)."
        except Exception as e:
            return False, f"Sandbox test failed: {str(e)}"
        finally:
            # 3. Cleanup
            if created_sandboxes:
                try:
                    for sandbox_name in created_sandboxes:
                        self.connection.command(f"DROP TABLE IF EXISTS {sandbox_name}")
                except Exception:
                    pass