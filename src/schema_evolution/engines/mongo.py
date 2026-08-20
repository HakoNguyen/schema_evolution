from datetime import datetime

from src.schema_evolution.engines.base import (
    BaseEngine, 
    ColumnSchema,
    ForeignKeySchema,
    TableSchema,
    SchemaChange, 
    ChangeType,
)

import pymongo
from bson.objectid import ObjectId
from bson.int64 import Int64

SAMPLE_SIZE = 100

class MongoEngine(BaseEngine):
    @property
    def engine_type(self) -> str:
        return "mongodb"

    def connect(self) -> None: 
        host = self.connection_config["host"]
        port = self.connection_config["port"]
        user = self.connection_config.get("user")
        password = self.connection_config.get("password")
        database = self.connection_config["database"]

        if user and password: 
            client = pymongo.MongoClient(
                host=host, port=port, username=user, password=password,
                serverSelectionTimeoutMS = 5000,
            )
        else:
            client = pymongo.MongoClient(host=host, port=port, serverSelectionTimeoutMS=5000)

        self.connection = client
        self.db = client[database]

    def disconnect(self) -> None:
        if self.connection is not None: 
            self.connection.close()
            self.connection = None
            self.db = None

    def health_check(self) -> bool:
        if self.connection is None: 
            return False
        try: 
            self.connection.admin.command("ping")
            return True
        except Exception:
            return False

    def list_tables(self) -> list[str]:
        """Với Mongo, "bảng" tương ứng với "collection"."""
        return self.db.list_collection_names()

    def crawl_metadata(self, table_name: str) -> TableSchema:
        """
        Sample SAMPLE_SIZE document từ collection, suy luận kiểu dữ liệu
        + nullable cho từng field, cộng thêm cột _id làm primary key.
        """
        docs = list(self.db[table_name].aggregate([{"$sample": {"size": SAMPLE_SIZE}}]))

        field_types: dict[str, set] = {}
        field_seen_count: dict[str, int] = {}
        field_has_null: dict[str, bool] = {}
        total_docs = len(docs)

        for doc in docs: 
            for field_name, value in doc.items(): 
                if field_name == "_id": 
                    continue
                field_seen_count[field_name] = field_seen_count.get(field_name, 0) + 1
                if value is None: 
                    field_has_null[field_name] = True
                    continue
                field_types.setdefault(field_name, set()).add(self._infer_type(value))

        columns = [ColumnSchema(name="_id", data_type="text", nullable=False)]
        for field_name, types_seen in field_types.items():
            data_type = types_seen.pop() if len(types_seen) == 1 else "json"

            nullable = (
                field_has_null.get(field_name, False) 
                or field_seen_count.get(field_name, 0) < total_docs
            )
            columns.append(ColumnSchema(name=field_name, data_type=data_type, nullable=nullable))

        return TableSchema(
            table_name=table_name, 
            columns=columns, 
            primary_key=["_id"], 
            foreign_keys=[],
        )

    def _infer_type(self, value) -> str: 
        if isinstance(value, bool): 
            return "boolean"
        if isinstance(value, Int64):
            return "bigint"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "double"
        if isinstance(value, str):
            return "text"
        if isinstance(value, datetime): 
            return "timestamp"
        if isinstance(value, ObjectId):
            return "text"
        if isinstance(value, (dict, list)): 
            return "json"
        return "json"

    def generate_ddl(self, changes: list[SchemaChange]) -> list[str]:
        """
        Mongo không cần DDL thật — thêm field mới không cần lệnh gì, document
        cũ đơn giản là không có field đó. Trả về placeholder no-op, giữ
        đúng số lượng phần tử để khớp 1-1 với changes (apply_non_breaking_changes
        cần zip(changes, ddls) đúng cặp).
        """
        return [f"NO-OP (Mongo schema-less): {change.change_type.value}" for change in changes]
 
    def execute_ddl(self, ddl_statement: str) -> None:
        pass

    def test_ddl(self, changes: list[SchemaChange]) -> tuple[bool, str]:
        if not changes:
            return True, "No changes to test."
        return True, "Sandbox test passed (MongoDB is schema-less, no DDL to dry-run)."