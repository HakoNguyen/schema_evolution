import React from 'react';
import { Database, AlertCircle, CheckCircle2, Layers } from 'lucide-react';

export default function TablesList({ tables, onSelectTable }) {
  if (tables.length === 0) {
    return <div className="no-data">No tables monitored.</div>;
  }

  // Group tables by pipeline pair_name
  const groupedPipelines = tables.reduce((acc, table) => {
    const pName = table.pair_name || 'default';
    if (!acc[pName]) {
      acc[pName] = {
        name: pName,
        mode: table.mode,
        source_type: table.source_type,
        target_type: table.target_type,
        tables: []
      };
    }
    acc[pName].tables.push(table);
    return acc;
  }, {});

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
        <div>
          <h2 style={{ margin: '0 0 4px 0', fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-dark)' }}>
            Task / Flow Monitor
          </h2>
          <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Monitored pipeline flows & tables categorized by pipeline namespace
          </p>
        </div>
      </div>

      {Object.values(groupedPipelines).map(pipeline => (
        <div key={pipeline.name} className="table-details-card" style={{ padding: 0, overflow: 'hidden' }}>
          
          {/* Pipeline Group Header */}
          <div style={{
            padding: '16px 20px',
            background: '#f8fafc',
            borderBottom: '1px solid var(--border-color)',
            display: 'flex',
            justify: 'space-between',
            alignItems: 'center'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Layers size={18} color="var(--primary-color)" />
              <span style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--text-dark)' }}>
                Pipeline: <code style={{ color: 'var(--primary-color)', fontSize: '0.95rem' }}>{pipeline.name}</code>
              </span>
            </div>
            <span className="badge badge-outline" style={{ background: '#ffffff', color: '#0f172a', fontWeight: 600 }}>
              {pipeline.mode}
            </span>
          </div>

          {/* Tables in Pipeline */}
          <div className="schema-table-wrapper" style={{ border: 'none', borderRadius: 0, marginBottom: 0 }}>
            <table className="schema-table">
              <thead>
                <tr>
                  <th style={{ width: '40%' }}>IDENTIFIER (NAMESPACE / TABLE)</th>
                  <th>VERSION</th>
                  <th>STATUS</th>
                  <th>LAST SCAN</th>
                </tr>
              </thead>
              <tbody>
                {pipeline.tables.map(table => (
                  <tr 
                    key={table.registry_key} 
                    className="list-row-clickable"
                    onClick={() => onSelectTable(table.registry_key)}
                  >
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Database size={16} className="text-muted" />
                        <div>
                          <strong style={{ color: '#0f172a', fontSize: '0.9rem' }}>{table.table_name}</strong>
                          <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                            <code style={{ fontSize: '0.75rem' }}>{table.registry_key}</code>
                          </div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#334155', background: '#f1f5f9', padding: '2px 8px', borderRadius: '12px' }}>
                        v{table.version || 1}
                      </span>
                    </td>
                    <td>
                      {table.is_frozen ? (
                        <span className="status-frozen" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                          <AlertCircle size={14} /> Pending Approval
                        </span>
                      ) : (
                        <span className="status-normal" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
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
      ))}
    </div>
  );
}
