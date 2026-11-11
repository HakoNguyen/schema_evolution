from typing import Dict, Any
from src.schema_evolution.core import SchemaRegistry, compare_schemas, for_target, TableSchema, ColumnSchema, ForeignKeySchema
from src.schema_evolution.engines.base import BaseEngine

def run_sandbox_test(target_engine: BaseEngine | None, registry_key: str, registry: SchemaRegistry,
                     target_table: str | None = None) -> Dict[str, Any]:
    if target_engine is None:
        return {"status": "success", "message": "Sandbox test passed (No target engine configured, pure detection mode)."}
        
    if not registry.is_frozen(registry_key):
        return {"status": "error", "message": "Table is not frozen, no pending changes to test."}
        
    draft = registry.load_draft(registry_key)
    if draft is None:
        return {"status": "error", "message": "No draft changes found for this table."}
        
    old_schema = registry.load(registry_key)
    if old_schema is None:
        return {"status": "error", "message": "Original schema not found in registry."}
        
    s = draft["table_schema"]
    new_schema = TableSchema(
        table_name=s["table_name"],
        columns=[ColumnSchema(**c) for c in s.get("columns", [])],
        primary_key=s.get("primary_key", []),
        foreign_keys=[ForeignKeySchema(**fk) for fk in s.get("foreign_keys", [])],
    )
    
    all_changes = compare_schemas(old_schema, new_schema)
    
    if not all_changes:
        return {"status": "success", "message": "Sandbox test passed (no actual changes detected)."}
        
    # target_engine đã được caller connect sẵn (build_target_engine).
    try:
        success, message = target_engine.test_ddl(for_target(all_changes, target_table))
    except Exception as e:
        success, message = False, f"Sandbox test failed: {str(e)}"
    return {"status": "success" if success else "error", "message": message}
