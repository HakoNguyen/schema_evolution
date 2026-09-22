import React, { useState, useEffect } from 'react';
import { Database, Key, History, Check, X } from 'lucide-react';

export default function TableDetails({ registryKey, details, refreshDetails }) {
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
    return <div className="no-data">Không tìm thấy dữ liệu schema. Đang chờ đồng bộ đầu tiên.</div>;
  }

  const currentSchema = details.schema;
  const displaySchema = versionDetails ? versionDetails.schema : currentSchema;
  
  return (
    <div style={{ background: '#151d2a', border: '1px solid #1e293b', borderRadius: '10px', padding: '24px', color: '#f8fafc' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: '#f8fafc' }}>
          Cấu Trúc Schema {versionDetails ? `(Phiên bản ${selectedVersion})` : `(Hiện tại v${details.version})`}
        </h3>

        {versions.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <History size={16} style={{ color: '#38bdf8' }} />
            <select 
              value={selectedVersion || ''} 
              onChange={e => setSelectedVersion(e.target.value === '' ? null : Number(e.target.value))}
              style={{
                padding: '6px 12px',
                background: '#0b0f17',
                border: '1px solid #1e293b',
                borderRadius: '6px',
                color: '#f8fafc',
                fontSize: '0.85rem',
                outline: 'none'
              }}
            >
              <option value="">-- Phiên bản hiện tại v{details.version} --</option>
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
              <th>CỘT</th>
              <th>KIỂU DỮ LIỆU</th>
              <th>NULLABLE</th>
              <th>GIÁ TRỊ MẶC ĐỊNH</th>
            </tr>
          </thead>
          <tbody>
            {displaySchema.columns.map(col => (
              <tr key={col.name}>
                <td><strong style={{ color: '#38bdf8' }}>{col.name}</strong></td>
                <td><code>{col.data_type}{col.max_length ? `(${col.max_length})` : ''}</code></td>
                <td>{col.nullable ? <span style={{ color: '#10b981' }}>✔ YES</span> : <span style={{ color: '#f43f5e', fontWeight: 600 }}>✘ NOT NULL</span>}</td>
                <td style={{ color: '#94a3b8' }}>{col.default !== null ? col.default : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ background: '#0b0f17', padding: '16px', borderRadius: '8px', border: '1px solid #1e293b' }}>
        {displaySchema.primary_key && displaySchema.primary_key.length > 0 && (
          <div style={{ fontSize: '0.85rem', marginBottom: '8px', color: '#cbd5e1', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Key size={14} style={{ color: '#f59e0b' }} />
            <strong style={{ color: '#f59e0b' }}>Khóa Chính (Primary Key):</strong> <code style={{ color: '#f8fafc' }}>{displaySchema.primary_key.join(', ')}</code>
          </div>
        )}
        {displaySchema.foreign_keys && displaySchema.foreign_keys.length > 0 && (
          <div style={{ fontSize: '0.85rem', color: '#cbd5e1' }}>
            <strong style={{ color: '#38bdf8' }}>Khóa Ngoại (Foreign Keys):</strong>
            <ul style={{ marginTop: '6px', paddingLeft: '20px' }}>
              {displaySchema.foreign_keys.map((fk, idx) => (
                <li key={idx} style={{ marginBottom: '4px' }}>
                  <code style={{ color: '#38bdf8' }}>{fk.column_name}</code> → <code style={{ color: '#38bdf8' }}>{fk.ref_table}.{fk.ref_column}</code> 
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
