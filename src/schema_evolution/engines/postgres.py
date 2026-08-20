from src.schema_evolution.engines.base import (
    BaseEngine,
    ColumnSchema,
    ForeignKeySchema,
    TableSchema,
    SchemaChange,
    ChangeType,
)

import psycopg2

TYPE_MAP = {
    "character varying": "varchar",
    "character": "char",
    "text": "text",
    "integer": "int",
    "bigint": "bigint",
    "smallint": "smallint",
    "boolean": "boolean",
    "numeric": "numeric",
    "real": "float",
    "double precision": "double",
    "timestamp without time zone": "timestamp",
    "timestamp with time zone": "timestamptz",
    "date": "date",
    "time without time zone": "time",
    "json": "json",
    "jsonb": "jsonb",
    "uuid": "uuid",
}

NORMALIZED_TO_POSTGRES = {
    "double": "double precision",
    "float": "real",
    "timestamptz": "timestamp with time zone",
    "timestamp": "timestamp without time zone",
}


class PostgresEngine(BaseEngine):
    @property
    def engine_type(self) -> str:
        return "postgres"

    def connect(self) -> None:
        self.connection = psycopg2.connect(**self.connection_config)
        self.connection.autocommit = False

    def disconnect(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def health_check(self) -> bool:
        if self.connection is None:
            return False
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except Exception:
            return False

    def list_tables(self) -> list[str]:
        query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """
        with self.connection.cursor() as cur:
            cur.execute(query)
            return [row[0] for row in cur.fetchall()]

    def crawl_metadata(self, table_name: str) -> TableSchema:
        return TableSchema(
            table_name=table_name,
            columns=self._crawl_columns(table_name),
            primary_key=self._crawl_primary_keys(table_name),
            foreign_keys=self._crawl_foreign_keys(table_name),
        )

    def _crawl_columns(self, table_name: str) -> list[ColumnSchema]:
        query = """
        SELECT column_name, data_type, is_nullable, column_default, character_maximum_length
        FROM information_schema.columns
        WHERE table_name = %s AND table_schema = 'public'
        ORDER BY ordinal_position
        """
        with self.connection.cursor() as cur:
            cur.execute(query, (table_name,))
            rows = cur.fetchall()

        columns = []
        for name, data_type, is_nullable, default, max_length in rows:
            columns.append(
                ColumnSchema(
                    name=name,
                    data_type=self._normalize_type(data_type),
                    nullable=(is_nullable == "YES"),
                    default=default,
                    max_length=max_length,
                )
            )
        return columns

    def _crawl_primary_keys(self, table_name: str) -> list[str]:
        query = """
        SELECT kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY'
            AND tc.table_name = %s
            AND tc.table_schema = 'public'
        ORDER BY kcu.ordinal_position
        """
        with self.connection.cursor() as cur:
            cur.execute(query, (table_name,))
            return [row[0] for row in cur.fetchall()]

    def _crawl_foreign_keys(self, table_name: str) -> list[ForeignKeySchema]:
        query = """
        SELECT
            tc.constraint_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name,
            rc.delete_rule,
            rc.update_rule
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        JOIN information_schema.referential_constraints AS rc
            ON rc.constraint_name = tc.constraint_name
            AND rc.constraint_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_name = %s
            AND tc.table_schema = 'public'
        """
        with self.connection.cursor() as cur:
            cur.execute(query, (table_name,))
            rows = cur.fetchall()

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

    def _normalize_type(self, pg_type: str) -> str:
        return TYPE_MAP.get(pg_type, pg_type)

    def _render_type(self, column: ColumnSchema) -> str:
        pg_type = NORMALIZED_TO_POSTGRES.get(column.data_type, column.data_type)
        if column.max_length is not None and pg_type in ("varchar", "char"):
            return f"{pg_type}({column.max_length})"
        return pg_type

    def generate_ddl(self, changes: list[SchemaChange]) -> list[str]:
        statements = []
        for change in changes:
            if change.change_type == ChangeType.ADD_COLUMN:
                col = change.new_value
                type_sql = self._render_type(col)
                null_sql = "" if col.nullable else " NOT NULL"
                default_sql = f" DEFAULT {col.default}" if col.default is not None else ""
                statements.append(
                    f"ALTER TABLE {change.table_name} "
                    f"ADD COLUMN {col.name} {type_sql}{null_sql}{default_sql}"
                )
            elif change.change_type == ChangeType.WIDEN_TYPE:
                col = change.new_value
                type_sql = self._render_type(col)
                statements.append(
                    f"ALTER TABLE {change.table_name} "
                    f"ALTER COLUMN {change.column_name} TYPE {type_sql}"
                )
            elif change.change_type == ChangeType.NOT_NULL_TO_NULLABLE:
                statements.append(
                    f"ALTER TABLE {change.table_name} "
                    f"ALTER COLUMN {change.column_name} DROP NOT NULL"
                )
            elif change.change_type == ChangeType.DROP_FOREIGN_KEY:
                statements.append(
                    f"ALTER TABLE {change.table_name} "
                    f"DROP CONSTRAINT {change.constraint_name}"
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
                type_sql = self._render_type(col)
                # USING ép kiểu tường minh — cần thiết khi đổi kiểu không
                # tương thích trực tiếp (VD varchar -> int), nếu không
                # Postgres sẽ từ chối ALTER COLUMN TYPE.
                statements.append(
                    f"ALTER TABLE {change.table_name} "
                    f"ALTER COLUMN {change.column_name} TYPE {type_sql} "
                    f"USING {change.column_name}::{type_sql}"
                )
            elif change.change_type == ChangeType.NULLABLE_TO_NOT_NULL:
                statements.append(
                    f"ALTER TABLE {change.table_name} "
                    f"ALTER COLUMN {change.column_name} SET NOT NULL"
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
                    f"PostgresEngine.generate_ddl không hỗ trợ "
                    f"change_type={change.change_type}"
                )
        return statements

    def execute_ddl(self, ddl_statement: str) -> None:
        try:
            with self.connection.cursor() as cur:
                cur.execute(ddl_statement)
            self.connection.commit()
        except Exception:
            # Postgres: 1 câu lệnh fail giữa transaction sẽ khoá cả
            # connection (mọi lệnh sau đều báo "current transaction is
            # aborted") cho tới khi rollback. Rollback ngay để các câu
            # DDL/bảng tiếp theo trong cùng chu kỳ không bị lây lỗi.
            self.connection.rollback()
            raise

    def test_ddl(self, changes: list[SchemaChange]) -> tuple[bool, str]:
        if not changes:
            return True, "No changes to test."
        
        statements = self.generate_ddl(changes)
        try:
            with self.connection.cursor() as cur:
                for stmt in statements:
                    cur.execute(stmt)
            # Unconditionally rollback to discard changes
            self.connection.rollback()
            return True, "Sandbox test passed (transaction rolled back)."
        except Exception as e:
            self.connection.rollback()
            return False, f"Sandbox test failed: {str(e)}"