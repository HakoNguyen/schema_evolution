from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ChangeSeverity(Enum):
    # Phan loai muc do be cau truc
    NON_BREAKING = "non_breaking"
    BREAKING = "breaking"


class ChangeType(Enum):
    # Cac thay doi cau truc he thong nhan dien duoc
    # non-breaking
    ADD_COLUMN = "add_column"
    NOT_NULL_TO_NULLABLE = "not_null_to_nullable"
    WIDEN_TYPE = "widen_type"
    # breaking
    DROP_COLUMN = "drop_column"
    RENAME_COLUMN = "rename_column"
    NARROW_TYPE = "narrow_type"
    CHANGE_TYPE_INCOMPATIBLE = "change_type_incompatible"
    NULLABLE_TO_NOT_NULL = "nullable_to_not_null"
    # primary key
    ADD_PRIMARY_KEY = "add_primary_key"
    DROP_PRIMARY_KEY = "drop_primary_key"
    CHANGE_PRIMARY_KEY = "change_primary_key"
    # foreign key
    ADD_FOREIGN_KEY = "add_foreign_key"
    DROP_FOREIGN_KEY = "drop_foreign_key"
    CHANGE_FOREIGN_KEY_TARGET = "change_fk_target"
    CHANGE_FOREIGN_KEY_ACTION = "change_fk_action"


@dataclass
class ColumnSchema:
    """Chuan hoa cho 1 cot, ca SQL va NoSQL"""
    name: str
    data_type: str
    nullable: bool
    default: Optional[Any] = None
    max_length: Optional[int] = None


@dataclass
class ForeignKeySchema:
    """Chuan hoa cho 1 Khoa ngoai"""
    constraint_name: str
    column_name: str
    ref_table: str
    ref_column: str
    on_delete: Optional[str] = None
    on_update: Optional[str] = None


@dataclass
class TableSchema:
    """Chuan hoa cho cau truc 1 bang hoac collection tai 1 thoi diem"""
    table_name: str
    columns: list[ColumnSchema] = field(default_factory=list)
    primary_key: list[str] = field(default_factory=list)
    foreign_keys: list[ForeignKeySchema] = field(default_factory=list)


@dataclass
class SchemaChange:
    """Mo ta thay doi cu the khi phat hien giua Source va Registry"""
    table_name: str
    change_type: ChangeType
    severity: ChangeSeverity
    column_name: Optional[str] = None
    constraint_name: Optional[str] = None
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None


class BaseEngine(ABC):
    """
    Interface trừu tượng cho mọi database engine.
    Mỗi driver cụ thể (PostgresEngine, MySQLEngine, MongoEngine,
    ClickHouseEngine) phải kế thừa và implement đầy đủ class này.
    """

    def __init__(self, connection_config: dict):
        """
        connection_config: dict chứa host, port, user, password, database....
        """
        self.connection_config = connection_config
        self.connection = None

    @property
    @abstractmethod
    def engine_type(self) -> str:
        """Trả về tên engine, ví dụ: 'postgres', 'mysql', 'mongodb', 'clickhouse'"""
        raise NotImplementedError("Subclasses must implement this method.")

    @abstractmethod
    def connect(self) -> None:
        """Kết nối tới database"""
        raise NotImplementedError("Subclasses must implement this method.")

    @abstractmethod
    def disconnect(self) -> None:
        """Ngắt kết nối tới database"""
        raise NotImplementedError("Subclasses must implement this method.")

    @abstractmethod
    def health_check(self) -> bool:
        """Kiểm tra kết nối tới database"""
        raise NotImplementedError("Subclasses must implement this method.")

    @abstractmethod
    def list_tables(self) -> list[str]:
        """Liệt kê tất cả các bảng/collections trong database"""
        raise NotImplementedError("Subclasses must implement this method.")

    @abstractmethod
    def crawl_metadata(self, table_name: str) -> TableSchema:
        """Crawl metadata của 1 bảng/collection
        SQL engine doc tu INFORMATION_SCHEMA,
        NoSQL engine sample N documents, infer type tung file
        """
        raise NotImplementedError("Subclasses must implement this method.")

    @abstractmethod
    def generate_ddl(self, changes: list[SchemaChange]) -> list[str]:
        """Sinh ra DDL tuong ung voi 1 thay doi cau truc"""
        raise NotImplementedError("Subclasses must implement this method.")

    @abstractmethod
    def execute_ddl(self, ddl_statement: str) -> None:
        """Thuc thi DDL tuong ung voi 1 thay doi cau truc"""
        raise NotImplementedError("Subclasses must implement this method.")