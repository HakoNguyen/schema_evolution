import React, { useState } from 'react';
import { Database, AlertCircle, CheckCircle2, Layers, Search, Filter, ChevronDown, ChevronRight, Activity, ShieldAlert, Server } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';

export default function TablesList({ tables, onSelectTable }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all'); // 'all' | 'frozen' | 'healthy'
  const [collapsedPipelines, setCollapsedPipelines] = useState({});
  const { t } = useLanguage();

  if (!tables || tables.length === 0) {
    return <div className="no-data">No monitored tables found.</div>;
  }

  // Calculate Metrics
  const totalTables = tables.length;
  const frozenCount = tables.filter(t => t.is_frozen).length;
  const healthyCount = totalTables - frozenCount;
  const healthRate = totalTables > 0 ? Math.round((healthyCount / totalTables) * 100) : 100;

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

  const totalPipelines = Object.keys(groupedPipelines).length;

  const togglePipelineCollapse = (pName) => {
    setCollapsedPipelines(prev => ({ ...prev, [pName]: !prev[pName] }));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* 1. KPI METRICS SUMMARY BAR */}
      <div className="metrics-row">
        <div className="metric-card">
          <div className="metric-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Layers size={14} style={{ color: 'var(--primary-color)' }} /> {t('active_pipelines')}
          </div>
          <div className="metric-value" style={{ color: 'var(--primary-color)' }}>{totalPipelines}</div>
        </div>

        <div className="metric-card">
          <div className="metric-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Database size={14} style={{ color: 'var(--text-main)' }} /> {t('total_tables')}
          </div>
          <div className="metric-value" style={{ color: 'var(--text-main)' }}>{totalTables}</div>
        </div>

        <div className="metric-card">
          <div className="metric-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <ShieldAlert size={14} style={{ color: frozenCount > 0 ? 'var(--danger-color)' : 'var(--text-dim)' }} /> {t('pending_tables')}
          </div>
          <div className="metric-value" style={{ color: frozenCount > 0 ? 'var(--danger-color)' : 'var(--text-muted)' }}>{frozenCount}</div>
        </div>

        <div className="metric-card">
          <div className="metric-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Activity size={14} style={{ color: 'var(--success-color)' }} /> {t('sync_rate')}
          </div>
          <div className="metric-value" style={{ color: 'var(--success-color)' }}>{healthRate}%</div>
        </div>
      </div>

      {/* 2. SEARCH & STATUS FILTER TOOLBAR */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        background: 'var(--card-bg)',
        border: '1px solid var(--border-color)',
        borderRadius: '10px',
        padding: '12px 16px',
        gap: '16px'
      }}>
        {/* Search Input */}
        <div style={{ position: 'relative', flex: 1, maxWidth: '380px' }}>
          <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dim)' }} />
          <input
            type="text"
            placeholder={t('search_tables_ph')}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              width: '100%',
              padding: '8px 12px 8px 36px',
              background: 'var(--body-bg)',
              border: '1px solid var(--border-color)',
              borderRadius: '6px',
              color: 'var(--text-main)',
              fontSize: '0.875rem',
              outline: 'none'
            }}
          />
        </div>

        {/* Status Filter Tabs */}
        <div style={{ display: 'flex', gap: '6px', background: 'var(--body-bg)', padding: '4px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
          <button
            onClick={() => setStatusFilter('all')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: 'none',
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor: 'pointer',
              background: statusFilter === 'all' ? 'var(--primary-color)' : 'transparent',
              color: statusFilter === 'all' ? '#0b0f17' : 'var(--text-muted)'
            }}
          >
            {t('all_tables')} ({totalTables})
          </button>
          <button
            onClick={() => setStatusFilter('frozen')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: 'none',
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor: 'pointer',
              background: statusFilter === 'frozen' ? 'var(--danger-bg)' : 'transparent',
              color: statusFilter === 'frozen' ? 'var(--danger-color)' : 'var(--text-muted)'
            }}
          >
            {t('pending_approval')} ({frozenCount})
          </button>
          <button
            onClick={() => setStatusFilter('healthy')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: 'none',
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor: 'pointer',
              background: statusFilter === 'healthy' ? 'var(--success-bg)' : 'transparent',
              color: statusFilter === 'healthy' ? 'var(--success-color)' : 'var(--text-muted)'
            }}
          >
            {t('healthy')} ({healthyCount})
          </button>
        </div>
      </div>

      {/* 3. COLLAPSIBLE PIPELINE ACCORDIONS */}
      {Object.values(groupedPipelines).map((pipeline, index) => {
        // Filter tables inside pipeline
        const filteredTables = pipeline.tables.filter(t => {
          const matchesSearch = t.table_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                                pipeline.name.toLowerCase().includes(searchTerm.toLowerCase());
          const matchesStatus = statusFilter === 'all' ||
                                (statusFilter === 'frozen' && t.is_frozen) ||
                                (statusFilter === 'healthy' && !t.is_frozen);
          return matchesSearch && matchesStatus;
        });

        if (filteredTables.length === 0) return null;

        const isCollapsed = collapsedPipelines[pipeline.name];
        const pipelineFrozenCount = filteredTables.filter(t => t.is_frozen).length;

        return (
          <div 
            key={pipeline.name} 
            style={{
              background: 'var(--card-bg)',
              border: '1px solid var(--border-color)',
              borderRadius: '10px',
              overflow: 'hidden'
            }}
          >
            {/* Pipeline Header */}
            <div 
              onClick={() => togglePipelineCollapse(pipeline.name)}
              style={{
                padding: '14px 20px',
                background: 'var(--card-bg)',
                borderBottom: isCollapsed ? 'none' : '1px solid var(--border-color)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                cursor: 'pointer',
                userSelect: 'none'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                {isCollapsed ? <ChevronRight size={18} color="var(--text-muted)" /> : <ChevronDown size={18} color="var(--text-muted)" />}
                <Layers size={18} style={{ color: 'var(--primary-color)' }} />
                <span style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--text-main)' }}>
                  Pipeline: <code style={{ color: 'var(--primary-color)', fontSize: '0.95rem' }}>{pipeline.name}</code>
                </span>
                <span style={{ fontSize: '0.75rem', padding: '2px 8px', borderRadius: '4px', background: 'var(--body-bg)', color: 'var(--text-muted)', border: '1px solid var(--border-color)' }}>
                  {filteredTables.length} {t('monitored_tables_count')}
                </span>
                {pipelineFrozenCount > 0 && (
                  <span style={{ fontSize: '0.75rem', padding: '2px 8px', borderRadius: '4px', background: 'var(--danger-bg)', color: 'var(--danger-color)', border: '1px solid var(--danger-border)', fontWeight: 600 }}>
                    {pipelineFrozenCount} {t('pending_approval')}
                  </span>
                )}
              </div>

              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', background: 'var(--body-bg)', padding: '4px 10px', borderRadius: '6px', border: '1px solid var(--border-color)', fontWeight: 600 }}>
                {pipeline.mode}
              </span>
            </div>

            {/* Tables list in accordion */}
            {!isCollapsed && (
              <div className="schema-table-wrapper" style={{ border: 'none', borderRadius: 0 }}>
                <table className="schema-table">
                  {index === 0 && (
                    <thead>
                      <tr>
                        <th>{t('table_name')} / REGISTRY KEY</th>
                        <th>{t('version')}</th>
                        <th>{t('status')}</th>
                        <th>LAST SCAN</th>
                      </tr>
                    </thead>
                  )}
                  <tbody>
                    {filteredTables.map(table => (
                      <tr 
                        key={table.registry_key} 
                        className="list-row-clickable"
                        onClick={() => onSelectTable(table.registry_key)}
                      >
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <Database size={16} style={{ color: 'var(--text-muted)' }} />
                            <div>
                              <strong style={{ color: 'var(--text-main)', fontSize: '0.9rem' }}>{table.table_name}</strong>
                              <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                                <code style={{ fontSize: '0.75rem', color: 'var(--primary-color)' }}>{table.registry_key}</code>
                              </div>
                            </div>
                          </div>
                        </td>
                        <td>
                          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--primary-color)', background: 'var(--primary-bg)', padding: '2px 8px', borderRadius: '12px', border: '1px solid var(--primary-border)' }}>
                            v{table.version || 1}
                          </span>
                        </td>
                        <td>
                          {table.is_frozen ? (
                            <span className="status-frozen" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', background: 'var(--danger-bg)', padding: '3px 8px', borderRadius: '4px', border: '1px solid var(--danger-border)', fontSize: '0.75rem', fontWeight: 600 }}>
                              <AlertCircle size={13} /> {t('pending_approval')}
                            </span>
                          ) : (
                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: 'var(--success-color)', fontSize: '0.8rem', fontWeight: 600 }}>
                              ● {t('healthy')}
                            </span>
                          )}
                        </td>
                        <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                          {table.updated_at !== '—' ? new Date(table.updated_at).toLocaleString() : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

