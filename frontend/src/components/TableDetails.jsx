import React, { useState, useEffect } from 'react';

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
  }, [registryKey, details]); // reload when details update

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
    return <div className="no-data">No schema data found. Waiting for first sync.</div>;
  }

  const currentSchema = details.schema;
  const displaySchema = versionDetails ? versionDetails.schema : currentSchema;
  
  return (
    <div className="table-details-card">
      <div className="card-header">
        <h3>Schema Structure {versionDetails ? `(Version ${selectedVersion})` : `(Current v${details.version})`}</h3>
      </div>
      
      <div className="schema-table-wrapper">
        <table className="schema-table">
          <thead>
            <tr>
              <th>Column</th>
              <th>Data Type</th>
              <th>Nullable</th>
              <th>Default</th>
            </tr>
          </thead>
          <tbody>
            {displaySchema.columns.map(col => (
              <tr key={col.name}>
                <td><strong>{col.name}</strong></td>
                <td>{col.data_type}{col.max_length ? `(${col.max_length})` : ''}</td>
                <td>{col.nullable ? '✔' : '✘'}</td>
                <td className="text-muted">{col.default !== null ? col.default : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="schema-meta">
        {displaySchema.primary_key && displaySchema.primary_key.length > 0 && (
          <div className="meta-item">
            <strong>Primary Key:</strong> {displaySchema.primary_key.join(', ')}
          </div>
        )}
        {displaySchema.foreign_keys && displaySchema.foreign_keys.length > 0 && (
          <div className="meta-item">
            <strong>Foreign Keys:</strong>
            <ul>
              {displaySchema.foreign_keys.map((fk, idx) => (
                <li key={idx}>
                  <code>{fk.column_name}</code> → <code>{fk.ref_table}.{fk.ref_column}</code> 
                  {fk.on_delete && ` (ON DELETE ${fk.on_delete})`}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {versions.length > 0 && (
        <div className="version-history">
          <h4>Version History</h4>
          <select 
            value={selectedVersion || ''} 
            onChange={e => setSelectedVersion(e.target.value === '' ? null : Number(e.target.value))}
            className="version-select"
          >
            <option value="">-- Current Version --</option>
            {versions.map(v => (
              <option key={v.version} value={v.version}>
                v{v.version} — {v.timestamp ? new Date(v.timestamp).toLocaleString() : '—'}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}
