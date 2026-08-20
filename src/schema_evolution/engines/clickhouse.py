import re

from src.schema_evolution.engines.base import (
    BaseEngine, 
    ColumnSchema, 
    ForeignKeySchema, 
    TableSchema, 
    SchemaChange, 
    ChangeType,
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
    "date": "Date",
    "timestamp": "DateTime",
    "timestamptz": "DateTime",
    "uuid": "UUID",
    "numeric": "Float64",  
    "json": "String",       
}

FIXED_STRING_RE = re.compile(r"^FixedString\((\d+)\)$")

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
        if column.max_length and base_type == "String": 
            base_type = f"FixedString({column.max_length})"
        if column.nullable: 
            return f"Nullable({base_type})"
        return base_type

    def generate_ddl(self, changes: list[SchemaChange]) -> list[str]:
        statements = []
        for change in changes:
            if change.change_type == ChangeType.ADD_COLUMN:
                col = change.new_value
                type_sql = self._render_type(col)
                default_sql = f" DEFAULT {col.default}" if col.default is not None else ""
                statements.append(
                    f"ALTER TABLE {change.table_name} "
                    f"ADD COLUMN {col.name} {type_sql}{default_sql}"
                )
            elif change.change_type == ChangeType.WIDEN_TYPE:
                col = change.new_value
                type_sql = self._render_type(col)
                statements.append(
                    f"ALTER TABLE {change.table_name} "
                    f"MODIFY COLUMN {change.column_name} {type_sql}"
                )
            elif change.change_type == ChangeType.NOT_NULL_TO_NULLABLE:
                col = change.new_value
                type_sql = self._render_type(col)  # col.nullable đã là True
                statements.append(
                    f"ALTER TABLE {change.table_name} "
                    f"MODIFY COLUMN {change.column_name} {type_sql}"
                )
            elif change.change_type == ChangeType.DROP_FOREIGN_KEY:
                # ClickHouse không có FK -> không bao giờ thực sự phát sinh
                # change_type này khi target là ClickHouse, nhưng vẫn xử lý
                # tường minh (no-op) để không rơi vào nhánh else gây lỗi.
                statements.append(f"-- NO-OP: ClickHouse khong co FK ({change.constraint_name})")
            # --- Các loại BREAKING dưới đây chỉ dùng khi Approve (sau khi
            # kỹ sư đã duyệt) — không bao giờ được apply_non_breaking_changes
            # gọi tới trong luồng auto-sync thông thường. ---
            elif change.change_type == ChangeType.DROP_COLUMN:
                statements.append(
                    f"ALTER TABLE {change.table_name} DROP COLUMN {change.column_name}"
                )
            elif change.change_type in (ChangeType.NARROW_TYPE, ChangeType.CHANGE_TYPE_INCOMPATIBLE):
                col = change.new_value
                type_sql = self._render_type(col)
                statements.append(
                    f"ALTER TABLE {change.table_name} "
                    f"MODIFY COLUMN {change.column_name} {type_sql}"
                )
            elif change.change_type == ChangeType.NULLABLE_TO_NOT_NULL:
                col = change.new_value
                type_sql = self._render_type(col)  # col.nullable đã là False
                statements.append(
                    f"ALTER TABLE {change.table_name} "
                    f"MODIFY COLUMN {change.column_name} {type_sql}"
                )
            elif change.change_type == ChangeType.ADD_FOREIGN_KEY:
                # ClickHouse không có FK -> nếu gặp trường hợp này (không nên
                # xảy ra vì Mongo source luôn trả foreign_keys=[]) thì báo lỗi
                # rõ ràng thay vì âm thầm bỏ qua.
                raise ValueError(
                    "ClickHouseEngine không hỗ trợ ADD_FOREIGN_KEY — ClickHouse "
                    "không có ràng buộc khoá ngoại ở DB level."
                )
            else:
                raise ValueError(
                    f"ClickHouseEngine.generate_ddl không hỗ trợ "
                    f"change_type={change.change_type}"
                )
        return statements
 
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
                sandbox_name = f"__sandbox_{table_name}"
                self.connection.command(f"DROP TABLE IF EXISTS {sandbox_name}")
                self.connection.command(f"CREATE TABLE {sandbox_name} AS {table_name}")
                created_sandboxes.append(sandbox_name)
            
            # 2. Apply DDL to sandbox tables
            statements = self.generate_ddl(changes)
            for stmt, change in zip(statements, changes):
                sandbox_name = f"__sandbox_{change.table_name}"
                sandbox_stmt = stmt.replace(
                    f"ALTER TABLE {change.table_name} ",
                    f"ALTER TABLE {sandbox_name} ",
                    1
                )
                self.execute_ddl(sandbox_stmt)
                
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