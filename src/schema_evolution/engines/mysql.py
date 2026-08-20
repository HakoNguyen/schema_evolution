from src.schema_evolution.engines.base import (
    BaseEngine,
    ColumnSchema,
    ForeignKeySchema,
    TableSchema,
    SchemaChange,
    ChangeType,
)

import mysql.connector

TYPE_MAP = {
    "varchar": "varchar",
    "char": "char",
    "text": "text",
    "int": "int",
    "bigint": "bigint",
    "smallint": "smallint",
    "tinyint": "smallint",
    "decimal": "numeric",
    "float": "float",
    "double": "double",
    "datetime": "timestamp",
    "timestamp": "timestamp",
    "date": "date",
    "time": "time",
    "json": "json",
}

NORMALIZED_TO_MYSQL = {
    "int": "INT",
    "bigint": "BIGINT",
    "smallint": "SMALLINT",
    "boolean": "BOOLEAN",
    "numeric": "DECIMAL",
    "float": "FLOAT",
    "double": "DOUBLE",
    "timestamp": "DATETIME",
    "date": "DATE",
    "time": "TIME",
    "text": "TEXT",
    "json": "JSON",
    "varchar": "VARCHAR",
    "char": "CHAR",
}


class MySQLEngine(BaseEngine):
    @property
    def engine_type(self) -> str:
        return "mysql"

    def connect(self) -> None:
        self.connection = mysql.connector.connect(**self.connection_config)
        # QUAN TRỌNG: mysql-connector-python mặc định autocommit=False. Kết
        # hợp với isolation level mặc định của MySQL (REPEATABLE READ),
        # câu SELECT đầu tiên sẽ "khoá" lại 1 snapshot cố định — mọi lần
        # crawl_metadata() sau đó trong CÙNG transaction sẽ không thấy
        # được thay đổi mới do connection khác commit (khác Postgres dùng
        # READ COMMITTED, không bị vấn đề này). Bật autocommit để mỗi câu
        # SELECT luôn đọc dữ liệu mới nhất, không bị kẹt snapshot cũ.
        self.connection.autocommit = True

    def disconnect(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def health_check(self) -> bool:
        if self.connection is None:
            return False
        try:
            self.connection.ping(reconnect=False, attempts=1, delay=0)
            return True
        except Exception:
            return False

    def list_tables(self) -> list[str]:
        query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE'
        """
        cur = self.connection.cursor()
        cur.execute(query)
        rows = cur.fetchall()
        cur.close()
        return [row[0] for row in rows]

    def crawl_metadata(self, table_name: str) -> TableSchema:
        return TableSchema(
            table_name=table_name,
            columns=self._crawl_columns(table_name),
            primary_key=self._crawl_primary_key(table_name),
            foreign_keys=self._crawl_foreign_keys(table_name),
        )

    def _crawl_columns(self, table_name: str) -> list[ColumnSchema]:
        query = """
        SELECT column_name, data_type, column_type, is_nullable, column_default, character_maximum_length
        FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = %s
        ORDER BY ordinal_position
        """
        cur = self.connection.cursor()
        cur.execute(query, (table_name,))
        rows = cur.fetchall()
        cur.close()

        columns = []
        for name, data_type, column_type, is_nullable, default, max_length in rows:
            columns.append(
                ColumnSchema(
                    name=name,
                    data_type=self._normalize_type(data_type, column_type),
                    nullable=(is_nullable == "YES"),
                    default=default,
                    max_length=max_length,
                )
            )
        return columns

    def _crawl_primary_key(self, table_name: str) -> list[str]:
        query = """
        SELECT column_name
        FROM information_schema.key_column_usage
        WHERE table_schema = DATABASE() AND table_name = %s
            AND constraint_name = 'PRIMARY'
        ORDER BY ordinal_position
        """
        cur = self.connection.cursor()
        cur.execute(query, (table_name,))
        rows = cur.fetchall()
        cur.close()
        return [row[0] for row in rows]

    def _crawl_foreign_keys(self, table_name: str) -> list[ForeignKeySchema]:
        query = """
        SELECT
                kcu.constraint_name,
                kcu.column_name,
                kcu.referenced_table_name,
                kcu.referenced_column_name,
                rc.delete_rule,
                rc.update_rule
            FROM information_schema.key_column_usage kcu
            JOIN information_schema.referential_constraints rc
              ON kcu.constraint_name = rc.constraint_name
             AND kcu.table_schema = rc.constraint_schema
            WHERE kcu.table_schema = DATABASE()
              AND kcu.table_name = %s
              AND kcu.referenced_table_name IS NOT NULL
        """
        cur = self.connection.cursor()
        cur.execute(query, (table_name,))
        rows = cur.fetchall()
        cur.close()

        fks = []
        for constraint_name, column_name, ref_table, ref_column, delete_rule, update_rule in rows:
            fks.append(
                ForeignKeySchema(
                    constraint_name=constraint_name,
                    column_name=column_name,
                    ref_table=ref_table,
                    ref_column=ref_column,
                    on_delete=delete_rule,
                    on_update=update_rule,
                )
            )
        return fks

    def _normalize_type(self, data_type: str, column_type: str) -> str:
        if data_type == "tinyint" and column_type == "tinyint(1)":
            return "boolean"
        return TYPE_MAP.get(data_type, data_type)

    def _render_type(self, column: ColumnSchema) -> str:
        mysql_type = NORMALIZED_TO_MYSQL.get(column.data_type, column.data_type.upper())
        if mysql_type == "BOOLEAN":
            return "TINYINT(1)"
        if column.max_length and mysql_type in ("VARCHAR", "CHAR"):
            return f"{mysql_type}({column.max_length})"
        return mysql_type

    def _render_full_column_def(self, column: ColumnSchema) -> str:
        type_sql = self._render_type(column)
        null_sql = "NULL" if column.nullable else "NOT NULL"
        default_sql = f" DEFAULT {column.default}" if column.default is not None else ""
        return f"{column.name} {type_sql} {null_sql}{default_sql}"

    def generate_ddl(self, changes: list[SchemaChange]) -> list[str]:
        statements = []
        for change in changes:
            if change.change_type == ChangeType.ADD_COLUMN:
                col = change.new_value
                statements.append(
                    f"ALTER TABLE {change.table_name} "
                    f"ADD COLUMN {self._render_full_column_def(col)}"
                )
            elif change.change_type == ChangeType.WIDEN_TYPE:
                col = change.new_value
                statements.append(
                    f"ALTER TABLE {change.table_name} "
                    f"MODIFY COLUMN {self._render_full_column_def(col)}"
                )
            elif change.change_type == ChangeType.NOT_NULL_TO_NULLABLE:
                col = change.new_value
                statements.append(
                    f"ALTER TABLE {change.table_name} "
                    f"MODIFY COLUMN {self._render_full_column_def(col)}"
                )
            elif change.change_type == ChangeType.DROP_FOREIGN_KEY:
                statements.append(
                    f"ALTER TABLE {change.table_name} "
                    f"DROP FOREIGN KEY {change.constraint_name}"
                )
            # --- Các loại BREAKING dưới đây chỉ dùng khi Approve (sau khi
            # kỹ sư đã duyệt) — không bao giờ được apply_non_breaking_changes
            # gọi tới trong luồng auto-sync thông thường. ---
            elif change.change_type == ChangeType.DROP_COLUMN:
                statements.append(
                    f"ALTER TABLE {change.table_name} DROP COLUMN {change.column_name}"
                )
            elif change.change_type in (ChangeType.NARROW_TYPE, ChangeType.CHANGE_TYPE_INCOMPATIBLE):
                col = change.new_value
                statements.append(
                    f"ALTER TABLE {change.table_name} "
                    f"MODIFY COLUMN {self._render_full_column_def(col)}"
                )
            elif change.change_type == ChangeType.NULLABLE_TO_NOT_NULL:
                col = change.new_value
                statements.append(
                    f"ALTER TABLE {change.table_name} "
                    f"MODIFY COLUMN {self._render_full_column_def(col)}"
                )
            elif change.change_type == ChangeType.ADD_FOREIGN_KEY:
                fk = change.new_value
                on_delete = f" ON DELETE {fk.on_delete}" if fk.on_delete else ""
                on_update = f" ON UPDATE {fk.on_update}" if fk.on_update else ""
                statements.append(
                    f"ALTER TABLE {change.table_name} "
                    f"ADD CONSTRAINT {fk.constraint_name} "
                    f"FOREIGN KEY ({fk.column_name}) REFERENCES {fk.ref_table}({fk.ref_column})"
                    f"{on_delete}{on_update}"
                )
            else:
                raise ValueError(
                    f"MySQLEngine.generate_ddl không hỗ trợ "
                    f"change_type={change.change_type}"
                )
        return statements

    def execute_ddl(self, ddl_statement: str) -> None:
        try:
            cur = self.connection.cursor()
            cur.execute(ddl_statement)
            cur.close()
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def test_ddl(self, changes: list[SchemaChange]) -> tuple[bool, str]:
        if not changes:
            return True, "No changes to test."
        
        tables = {change.table_name for change in changes}
        created_sandboxes = []
        
        try:
            cur = self.connection.cursor()
            # 1. Create sandbox tables
            for table_name in tables:
                sandbox_name = f"__sandbox_{table_name}"
                cur.execute(f"DROP TABLE IF EXISTS {sandbox_name}")
                cur.execute(f"CREATE TABLE {sandbox_name} LIKE {table_name}")
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
                cur.execute(sandbox_stmt)
                
            return True, "Sandbox test passed (applied to clone table)."
        except Exception as e:
            return False, f"Sandbox test failed: {str(e)}"
        finally:
            # 3. Cleanup
            if created_sandboxes:
                try:
                    cur = self.connection.cursor()
                    for sandbox_name in created_sandboxes:
                        cur.execute(f"DROP TABLE IF EXISTS {sandbox_name}")
                    cur.close()
                except Exception:
                    pass