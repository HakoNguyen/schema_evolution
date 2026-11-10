import re
from datetime import datetime
from typing import Any, Dict, List
from src.schema_evolution.engines.base import TableSchema, ColumnSchema

ISO_DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")

def infer_datatype(val: Any) -> str:
    """Infer engine-agnostic normalized datatype from Python value."""
    if val is None:
        return "text"
    if isinstance(val, bool):
        return "boolean"
    if isinstance(val, int):
        if abs(val) > 2147483647:
            return "bigint"
        return "int"
    if isinstance(val, float):
        return "double"
    if isinstance(val, datetime):
        return "timestamp"
    if isinstance(val, str):
        if ISO_DATE_REGEX.match(val):
            return "timestamp"
        if len(val) <= 255:
            return "varchar"
        return "text"
    if isinstance(val, (dict, list)):
        return "text"
    return "text"

def extract_schema_from_data_dict(table_name: str, data_dict: Dict[str, Any], primary_key: str = "_id") -> TableSchema:
    """Extract a TableSchema from a CDC message data dictionary."""
    columns: List[ColumnSchema] = []
    
    pk_cols = [primary_key] if primary_key in data_dict else []
    
    for key, val in data_dict.items():
        data_type = infer_datatype(val)
        is_nullable = (key not in pk_cols)
        columns.append(
            ColumnSchema(
                name=key,
                data_type=data_type,
                nullable=is_nullable,
                default=None,
                max_length=255 if data_type == "varchar" else None
            )
        )
        
    return TableSchema(
        table_name=table_name,
        columns=columns,
        primary_key=pk_cols,
        foreign_keys=[]
    )
