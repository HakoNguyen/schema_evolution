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
    <div style={{ color: 'var(--text-main)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
        <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600 }}>
          {t('schema_structure')}{' '}
          <span style={{ color: 'var(--text-dim)', fontWeight: 400 }}>
            {versionDetails ? `v${selectedVersion}` : `${t('current_version')} · v${details.version}`}
          </span>
        </h3>

        {versions.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <History size={14} style={{ color: 'var(--text-dim)' }} />
            <select
              value={selectedVersion || ''}
              onChange={e => setSelectedVersion(e.target.value === '' ? null : Number(e.target.value))}
              style={{
                padding: '5px 10px',
                background: 'var(--card-bg)',
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
      
      <div className="schema-table-wrapper" style={{ marginBottom: '12px' }}>
        <table className="schema-table fixed">
          <colgroup>
            <col style={{ width: '40%' }} />
            <col style={{ width: '22%' }} />
            <col style={{ width: '16%' }} />
            <col style={{ width: '22%' }} />
          </colgroup>
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
                <td>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontWeight: 500 }}>
                    {col.name}
                    {displaySchema.primary_key?.includes(col.name) && <Key size={12} style={{ color: 'var(--text-dim)' }} aria-label="primary key" />}
                  </span>
                </td>
                <td><code style={{ color: 'var(--text-muted)' }}>{col.data_type}{col.max_length ? `(${col.max_length})` : ''}</code></td>
                <td style={{ color: col.nullable ? 'var(--text-dim)' : 'var(--text-muted)', fontSize: '0.8rem' }}>{col.nullable ? 'NULL' : 'NOT NULL'}</td>
                <td style={{ color: 'var(--text-dim)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {col.default !== null ? <code>{col.default}</code> : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {displaySchema.primary_key && displaySchema.primary_key.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Key size={12} style={{ color: 'var(--text-dim)' }} />
            <span>{t('primary_key_label')}</span> <code style={{ color: 'var(--text-main)' }}>{displaySchema.primary_key.join(', ')}</code>
          </div>
        )}
        {displaySchema.foreign_keys && displaySchema.foreign_keys.length > 0 && (
          <div>
            <span>{t('foreign_keys_label')}</span>
            <ul style={{ marginTop: '6px', paddingLeft: '20px' }}>
              {displaySchema.foreign_keys.map((fk, idx) => (
                <li key={idx} style={{ marginBottom: '4px' }}>
                  <code style={{ color: 'var(--text-main)' }}>{fk.column_name}</code> → <code style={{ color: 'var(--text-main)' }}>{fk.ref_table}.{fk.ref_column}</code>
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
