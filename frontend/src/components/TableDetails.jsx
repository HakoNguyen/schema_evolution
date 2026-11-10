import React, { useState, useEffect } from 'react';
import { Database, Key, History, Check, X } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';

export default function TableDetails({ registryKey, details, refreshDetails }) {
  const { t } = useLanguage();
  const [versions, setVersions] = useState([]);
  const [selectedVersion, setSelectedVersion] = useState(null);
  const [versionDetails, setVersionDetails] = useState(null);

  useEffect(() => {
    if (!registryKey) return;
    fetch(`/api/tables/${registryKey}/versions`)
      .then(res => res.json())
      .then(data => {
        setVersions(data);
        setSelectedVersion(null);
        setVersionDetails(null);
      })
      .catch(err => console.error("Error fetching versions", err));
  }, [registryKey, details]);

  useEffect(() => {
    if (!registryKey || !selectedVersion) return;
    fetch(`/api/tables/${registryKey}/versions/${selectedVersion}`)
      .then(res => res.json())
      .then(data => {
        if (data.exists) {
          setVersionDetails(data);
        }
      });
  }, [registryKey, selectedVersion]);

  if (!details || !details.exists) {
    return <div className="no-data">{t('no_schema_data')}</div>;
  }

  const currentSchema = details.schema;
  const displaySchema = versionDetails ? versionDetails.schema : currentSchema;
  
  return (
    <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '10px', padding: '24px', color: 'var(--text-main)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-main)' }}>
          {t('schema_structure')} {versionDetails ? `(v${selectedVersion})` : `(${t('current_version')} v${details.version})`}
        </h3>

        {versions.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <History size={16} style={{ color: 'var(--primary-color)' }} />
            <select 
              value={selectedVersion || ''} 
              onChange={e => setSelectedVersion(e.target.value === '' ? null : Number(e.target.value))}
              style={{
                padding: '6px 12px',
                background: 'var(--body-bg)',
                border: '1px solid var(--border-color)',
                borderRadius: '6px',
                color: 'var(--text-main)',
                fontSize: '0.85rem',
                outline: 'none'
              }}
            >
              <option value="">-- {t('current_version')} v{details.version} --</option>
              {versions.map(v => (
                <option key={v.version} value={v.version}>
                  v{v.version} — {v.timestamp ? new Date(v.timestamp).toLocaleString() : '—'}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
      
      <div className="schema-table-wrapper" style={{ marginBottom: '20px' }}>
        <table className="schema-table">
          <thead>
            <tr>
              <th>{t('col_column_name')}</th>
              <th>{t('col_data_type')}</th>
              <th>{t('col_nullable')}</th>
              <th>{t('col_default_val')}</th>
            </tr>
          </thead>
          <tbody>
            {displaySchema.columns.map(col => (
              <tr key={col.name}>
                <td><strong style={{ color: 'var(--primary-color)' }}>{col.name}</strong></td>
                <td><code>{col.data_type}{col.max_length ? `(${col.max_length})` : ''}</code></td>
                <td>{col.nullable ? <span style={{ color: 'var(--success-color)' }}>✔ YES</span> : <span style={{ color: 'var(--danger-color)', fontWeight: 600 }}>✘ NOT NULL</span>}</td>
                <td style={{ color: 'var(--text-muted)' }}>{col.default !== null ? col.default : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ background: 'var(--body-bg)', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
        {displaySchema.primary_key && displaySchema.primary_key.length > 0 && (
          <div style={{ fontSize: '0.85rem', marginBottom: '8px', color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Key size={14} style={{ color: 'var(--warning-color)' }} />
            <strong style={{ color: 'var(--warning-color)' }}>{t('primary_key_label')}</strong> <code style={{ color: 'var(--text-main)' }}>{displaySchema.primary_key.join(', ')}</code>
          </div>
        )}
        {displaySchema.foreign_keys && displaySchema.foreign_keys.length > 0 && (
          <div style={{ fontSize: '0.85rem', color: 'var(--text-main)' }}>
            <strong style={{ color: 'var(--primary-color)' }}>{t('foreign_keys_label')}</strong>
            <ul style={{ marginTop: '6px', paddingLeft: '20px' }}>
              {displaySchema.foreign_keys.map((fk, idx) => (
                <li key={idx} style={{ marginBottom: '4px' }}>
                  <code style={{ color: 'var(--primary-color)' }}>{fk.column_name}</code> → <code style={{ color: 'var(--primary-color)' }}>{fk.ref_table}.{fk.ref_column}</code> 
                  {fk.on_delete && ` (ON DELETE ${fk.on_delete})`}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
