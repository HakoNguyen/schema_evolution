import React, { useState, useEffect } from 'react';
import { Plus, Trash2, Save, Type, GripVertical, Database } from 'lucide-react';
import { useToast } from './NotificationToast';
import { useLanguage } from '../context/LanguageContext';

export default function EditSchema({ tables, onDeploySuccess }) {
  const { t } = useLanguage();
  const [selectedKey, setSelectedKey] = useState('');
  const [columns, setColumns] = useState([]);
  const [loading, setLoading] = useState(false);
  const { addToast } = useToast();

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
      .catch(err => {
        console.error("Error fetching schema for edit", err);
        addToast(t('err_load_details'), "error");
      })
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
        addToast(t('toast_schema_drafted'), "success");
        if (onDeploySuccess) onDeploySuccess();
      } else {
        addToast(`${t('toast_action_failed')}: ${data.message || (typeof data.detail === 'string' ? data.detail : '')}`, "error");
      }
    } catch (e) {
      addToast(`${t('toast_network_error')}: ${e.message}`, "error");
    } finally {
      setLoading(false);
    }
  };


  return (
    <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '10px', overflow: 'hidden' }}>
      <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--card-bg)' }}>
        <div>
          <h3 style={{ margin: '0 0 6px 0', fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-main)' }}>{t('schema_editor_title')}</h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)' }}>{t('select_table_edit')}</span>
            <select 
              value={selectedKey} 
              onChange={e => setSelectedKey(e.target.value)}
              style={{ padding: '6px 12px', borderRadius: '6px', border: '1px solid var(--border-color)', background: 'var(--body-bg)', color: 'var(--text-main)', minWidth: '260px', outline: 'none', fontSize: '0.85rem' }}
            >
              <option value="">{t('select_table_edit_ph')}</option>
              {tables?.map(tItem => (
                <option key={tItem.registry_key} value={tItem.registry_key}>
                  {tItem.pair_name} / {tItem.table_name}
                </option>
              ))}
            </select>
          </div>
        </div>
        <button 
          className="btn-primary"
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '8px', 
            background: (!selectedKey || columns.length === 0) ? 'var(--border-subtle)' : 'var(--primary-color)', 
            color: (!selectedKey || columns.length === 0) ? 'var(--text-muted)' : 'var(--primary-fg)',
            opacity: (!selectedKey || columns.length === 0) ? 0.5 : 1,
            cursor: (!selectedKey || columns.length === 0) ? 'not-allowed' : 'pointer'
          }} 
          disabled={!selectedKey || columns.length === 0} 
          onClick={handleDeploy}
        >
          <Save size={16} /> {t('deploy_new_schema')}
        </button>
      </div>

      <div style={{ padding: '20px' }}>
        {!selectedKey ? (
          <div className="no-data" style={{ padding: '28px', minHeight: '160px' }}>
            <Database size={22} style={{ marginBottom: '10px', color: 'var(--text-dim)' }} />
            <p style={{ fontSize: '0.875rem' }}>{t('no_table_selected')}</p>
          </div>
        ) : loading ? (
          <div className="no-data" style={{ minHeight: '160px' }}>{t('loading_schema')}</div>
        ) : (
          <>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {columns.map((col) => (
                <div key={col.id} style={{ display: 'flex', alignItems: 'center', gap: '16px', padding: '10px 14px', background: 'var(--body-bg)', border: '1px solid var(--border-color)', borderRadius: '8px' }}>
                  <div style={{ cursor: 'grab', display: 'flex', alignItems: 'center' }}><GripVertical size={16} color="var(--text-dim)" /></div>
                  
                  <div style={{ flex: 1 }}>
                    <label style={{ display: 'block', fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '4px' }}>{t('column_name')}</label>
                    <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                      <Type size={14} style={{ position: 'absolute', left: '10px', color: 'var(--text-dim)' }} />
                      <input 
                        type="text" 
                        value={col.name} 
                        onChange={e => updateColumn(col.id, 'name', e.target.value)}
                        disabled={col.isPrimary}
                        style={{ width: '100%', padding: '6px 12px 6px 32px', background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '4px', color: 'var(--text-main)', outline: 'none', fontSize: '0.85rem' }}
                      />
                    </div>
                  </div>

                  <div style={{ flex: 1 }}>
                    <label style={{ display: 'block', fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '4px' }}>{t('data_type')}</label>

                    <select 
                      value={col.type} 
                      onChange={e => updateColumn(col.id, 'type', e.target.value)}
                      disabled={col.isPrimary}
                      style={{ width: '100%', padding: '8px 12px', background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '4px', color: 'var(--text-main)', outline: 'none', textTransform: 'uppercase' }}
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
                      {![
                        'int', 'bigint', 'varchar(50)', 'varchar(100)', 'varchar(150)', 
                        'varchar(255)', 'text', 'timestamp', 'boolean'
                      ].includes(col.type) && (
                        <option value={col.type}>{col.type.toUpperCase()}</option>
                      )}
                    </select>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', marginTop: '18px' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                      <input 
                        type="checkbox" 
                        checked={col.isPrimary} 
                        onChange={e => updateColumn(col.id, 'isPrimary', e.target.checked)}
                        disabled={true} 
                      />
                      {t('primary_key')}
                    </label>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', marginTop: '18px' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                      <input 
                        type="checkbox" 
                        checked={col.nullable} 
                        onChange={e => updateColumn(col.id, 'nullable', e.target.checked)}
                        disabled={col.isPrimary} 
                      />
                      {t('nullable')}
                    </label>
                  </div>

                  <button 
                    onClick={() => removeColumn(col.id)}
                    disabled={col.isPrimary}
                    style={{ background: 'transparent', border: 'none', color: 'var(--danger-color)', cursor: col.isPrimary ? 'not-allowed' : 'pointer', padding: '8px', marginTop: '18px', opacity: col.isPrimary ? 0.3 : 1 }}
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
              <Plus size={16} /> {t('add_column')}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
