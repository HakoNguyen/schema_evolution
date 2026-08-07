import React from 'react';
import { Database, AlertCircle, CheckCircle2 } from 'lucide-react';

export default function TablesList({ tables, onSelectTable }) {
  if (tables.length === 0) {
    return <div className="no-data">No tables monitored.</div>;
  }

  return (
    <div className="table-details-card" style={{ padding: 0 }}>
      <div className="card-header" style={{ padding: '24px 24px 12px 24px', marginBottom: 0 }}>
        <h3>Task/Flow Monitor</h3>
      </div>
      
      <div className="schema-table-wrapper" style={{ border: 'none', borderRadius: 0, marginBottom: 0 }}>
        <table className="schema-table">
          <thead>
            <tr>
              <th style={{ width: '35%' }}>NAME</th>
              <th>PAIR (CLUSTER)</th>
              <th>MODE</th>
              <th>STATUS</th>
              <th>LAST SCAN</th>
            </tr>
          </thead>
          <tbody>
            {tables.map(table => (
              <tr 
                key={table.registry_key} 
                className="list-row-clickable"
                onClick={() => onSelectTable(table.registry_key)}
              >
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Database size={16} className="text-muted" />
                    <strong>{table.table_name}</strong>
                  </div>
                </td>
                <td>{table.pair_name}</td>
                <td><span className="badge badge-outline">{table.mode}</span></td>
                <td>
                  {table.is_frozen ? (
                    <span className="status-frozen" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <AlertCircle size={14} /> Pending
                    </span>
                  ) : (
                    <span className="status-normal" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <CheckCircle2 size={14} /> Healthy
                    </span>
                  )}
                </td>
                <td className="text-muted" style={{ fontSize: '0.8rem' }}>
                  {table.updated_at !== '—' ? new Date(table.updated_at).toLocaleString() : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
