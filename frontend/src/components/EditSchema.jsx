import React, { useState, useEffect } from 'react';
import { Plus, Trash2, Save, Type, GripVertical, Database } from 'lucide-react';

export default function EditSchema({ tables, onDeploySuccess }) {
  const [selectedKey, setSelectedKey] = useState('');
  const [columns, setColumns] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!selectedKey) {
      setColumns([]);
      return;
    }
    setLoading(true);
    fetch(`/api/tables/${selectedKey}`)
      .then(res => res.json())
      .then(data => {
        if (data.exists && data.schema) {
          const cols = data.schema.columns.map((c, idx) => ({
            id: Date.now() + idx,
            name: c.name,
            type: c.data_type + (c.max_length ? `(${c.max_length})` : ''),
            nullable: c.nullable,
            isPrimary: data.schema.primary_key?.includes(c.name) || false
          }));
          setColumns(cols);
        }
      })
      .catch(err => console.error("Error fetching schema for edit", err))
      .finally(() => setLoading(false));
  }, [selectedKey]);

  const addColumn = () => {
    setColumns([...columns, { 
      id: Date.now(), 
      name: 'new_column', 
      type: 'varchar(50)', 
      nullable: true, 
      isPrimary: false 
    }]);
  };

  const removeColumn = (id) => {
    setColumns(columns.filter(c => c.id !== id));
  };

  const updateColumn = (id, field, value) => {
    setColumns(columns.map(c => c.id === id ? { ...c, [field]: value } : c));
  };

  const handleDeploy = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/tables/${selectedKey}/edit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ columns: columns })
      });
      const data = await res.json();
      if (data.status === 'success') {
        alert("Schema updated and saved as a frozen draft. Please review and deploy in Monitored Tables.");
        if (onDeploySuccess) onDeploySuccess();
      } else {
        alert("Error: " + data.message);
      }
    } catch (e) {
      alert("Error: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="table-details-card" style={{ padding: 0 }}>
      <div className="card-header" style={{ padding: '24px 24px 16px 24px', marginBottom: 0, borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={{ marginBottom: '8px' }}>Schema Editor (Low-Code)</h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)' }}>SELECT TABLE:</span>
            <select 
              value={selectedKey} 
              onChange={e => setSelectedKey(e.target.value)}
              style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border-color)', minWidth: '300px', outline: 'none' }}
            >
              <option value="">-- Choose a table to edit --</option>
              {tables?.map(t => (
                <option key={t.registry_key} value={t.registry_key}>
                  {t.pair_name} / {t.table_name}
                </option>
              ))}
            </select>
          </div>
        </div>
        <button className="btn-primary" style={{ display: 'flex', alignItems: 'center', gap: '8px' }} disabled={!selectedKey || columns.length === 0} onClick={handleDeploy}>
          <Save size={16} /> Deploy Schema
        </button>
      </div>

      <div style={{ padding: '24px' }}>
        {!selectedKey ? (
          <div className="no-data" style={{ padding: '40px' }}>
            <Database size={32} style={{ opacity: 0.3, marginBottom: '12px' }} />
            <p>Please select a table from the dropdown above to start editing its schema.</p>
          </div>
        ) : loading ? (
          <div className="no-data">Loading schema...</div>
        ) : (
          <>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {columns.map((col, idx) => (
            <div key={col.id} className="edit-column-row">
              <div className="drag-handle"><GripVertical size={16} color="#94a3b8" /></div>
              
              <div className="edit-field">
                <label>Column Name</label>
                <div className="input-group">
                  <Type size={14} className="input-icon" />
                  <input 
                    type="text" 
                    value={col.name} 
                    onChange={e => updateColumn(col.id, 'name', e.target.value)}
                    disabled={col.isPrimary}
                    title={col.isPrimary ? "Cannot rename Primary Key" : ""}
                    style={{ backgroundColor: col.isPrimary ? '#f1f5f9' : 'white', cursor: col.isPrimary ? 'not-allowed' : 'text' }}
                  />
                </div>
              </div>

              <div className="edit-field">
                <label>Data Type</label>
                <select 
                  value={col.type} 
                  onChange={e => updateColumn(col.id, 'type', e.target.value)}
                  disabled={col.isPrimary}
                  title={col.isPrimary ? "Cannot change Primary Key type" : ""}
                  style={{ backgroundColor: col.isPrimary ? '#f1f5f9' : 'white', cursor: col.isPrimary ? 'not-allowed' : 'pointer', textTransform: 'uppercase' }}
                >
                  <option value="int">INT</option>
                  <option value="bigint">BIGINT</option>
                  <option value="varchar(50)">VARCHAR(50)</option>
                  <option value="varchar(100)">VARCHAR(100)</option>
                  <option value="varchar(150)">VARCHAR(150)</option>
                  <option value="varchar(255)">VARCHAR(255)</option>
                  <option value="text">TEXT</option>
                  <option value="timestamp">TIMESTAMP</option>
                  <option value="boolean">BOOLEAN</option>
                  {/* Ensure current type is always in the list if it's not one of the above */}
                  {![
                    'int', 'bigint', 'varchar(50)', 'varchar(100)', 'varchar(150)', 
                    'varchar(255)', 'text', 'timestamp', 'boolean'
                  ].includes(col.type) && (
                    <option value={col.type}>{col.type.toUpperCase()}</option>
                  )}
                </select>
              </div>

              <div className="edit-field-checkbox">
                <label style={{ cursor: col.isPrimary ? 'not-allowed' : 'pointer', opacity: col.isPrimary ? 0.5 : 1 }}>
                  <input 
                    type="checkbox" 
                    checked={col.isPrimary} 
                    onChange={e => updateColumn(col.id, 'isPrimary', e.target.checked)}
                    disabled={true} 
                  />
                  Primary Key
                </label>
              </div>

              <div className="edit-field-checkbox">
                <label style={{ cursor: col.isPrimary ? 'not-allowed' : 'pointer', opacity: col.isPrimary ? 0.5 : 1 }}>
                  <input 
                    type="checkbox" 
                    checked={col.nullable} 
                    onChange={e => updateColumn(col.id, 'nullable', e.target.checked)}
                    disabled={col.isPrimary} 
                  />
                  Nullable
                </label>
              </div>

              <button 
                className="btn-icon-danger" 
                onClick={() => removeColumn(col.id)}
                title={col.isPrimary ? "Cannot remove Primary Key" : "Remove column"}
                disabled={col.isPrimary}
                style={{ opacity: col.isPrimary ? 0.3 : 1, cursor: col.isPrimary ? 'not-allowed' : 'pointer' }}
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
            </div>

            <button 
              className="btn-outline" 
              style={{ marginTop: '20px', display: 'flex', alignItems: 'center', gap: '6px', borderStyle: 'dashed' }}
              onClick={addColumn}
            >
              <Plus size={16} /> Add Column
            </button>
          </>
        )}
      </div>
    </div>
  );
}
