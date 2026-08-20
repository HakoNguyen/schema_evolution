from typing import Dict, Any, List
from src.schema_evolution.core import SchemaRegistry, compare_schemas, TableSchema, ColumnSchema

def parse_max_length(type_str: str) -> tuple[str, int | None]:
    type_str = type_str.lower().strip()
    if "(" in type_str and ")" in type_str:
        base = type_str[:type_str.find("(")]
        length_str = type_str[type_str.find("(")+1:type_str.find(")")]
        try:
            return base, int(length_str)
        except ValueError:
            return base, None
    return type_str, None

def apply_web_edit(registry_key: str, columns_data: List[Dict[str, Any]], registry: SchemaRegistry) -> Dict[str, Any]:
    old_schema = registry.load(registry_key)
    if old_schema is None:
        return {"status": "error", "message": "Original schema not found."}
        
    # Reconstruct columns
    new_columns = []
    for c in columns_data:
        base_type, max_length = parse_max_length(c["type"])
        new_columns.append(ColumnSchema(
            name=c["name"],
            data_type=base_type,
            nullable=c["nullable"],
            max_length=max_length
        ))
        
    new_schema = TableSchema(
        table_name=old_schema.table_name,
        columns=new_columns,
        primary_key=old_schema.primary_key,
        foreign_keys=old_schema.foreign_keys
    )
    
    all_changes = compare_schemas(old_schema, new_schema)
    if not all_changes:
        return {"status": "error", "message": "No changes detected."}
        
    registry.save_draft(registry_key, new_schema, all_changes)
    registry.set_frozen(registry_key, True)
    
    return {"status": "success"}
