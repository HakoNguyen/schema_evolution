import React, { useState } from 'react';
import { Search, ChevronDown, ChevronRight } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';

const segBtn = (active) => ({
  padding: '5px 12px',
  borderRadius: '5px',
  border: 'none',
  fontSize: '0.8rem',
  fontWeight: 500,
  cursor: 'pointer',
  whiteSpace: 'nowrap',
  background: active ? 'var(--card-bg)' : 'transparent',
  color: active ? 'var(--text-main)' : 'var(--text-muted)',
  boxShadow: active ? 'var(--shadow), 0 0 0 1px var(--border-color)' : 'none',
});

export default function TablesList({ tables, onSelectTable }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all'); // 'all' | 'frozen' | 'healthy'
  const [collapsedPipelines, setCollapsedPipelines] = useState({});
  const { t } = useLanguage();

  if (!tables || tables.length === 0) {
    return <div className="no-data">{t('no_tables')}</div>;
  }

  const totalTables = tables.length;
  const frozenCount = tables.filter(tb => tb.is_frozen).length;
  const healthyCount = totalTables - frozenCount;

  const groupedPipelines = tables.reduce((acc, table) => {
    const pName = table.pair_name || 'default';
    if (!acc[pName]) {
      acc[pName] = { name: pName, source_type: table.source_type, target_type: table.target_type, tables: [] };
    }
    acc[pName].tables.push(table);
    return acc;
  }, {});

  const totalPipelines = Object.keys(groupedPipelines).length;

  const modeLabel = (p) => {
    const src = (p.source_type || '').toUpperCase();
    return p.target_type && p.target_type !== 'none'
      ? `${src} → ${p.target_type.toUpperCase()}`
      : `${src} · ${t('source_only')}`;
  };

  const togglePipelineCollapse = (pName) => {
    setCollapsedPipelines(prev => ({ ...prev, [pName]: !prev[pName] }));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div className="metrics-row" style={{ marginBottom: 0 }}>
        <div className="metric-card">
          <div className="metric-label">{t('active_pipelines')}</div>
          <div className="metric-value">{totalPipelines}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">{t('total_tables')}</div>
          <div className="metric-value">{totalTables}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">{t('pending_tables')}</div>
          <div className="metric-value" style={{ color: frozenCount > 0 ? 'var(--warning-color)' : undefined }}>{frozenCount}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">{t('sync_rate')}</div>
          <div className="metric-value">
            {healthyCount}<span style={{ color: 'var(--text-dim)', fontWeight: 400 }}> / {totalTables}</span>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: 1, minWidth: '200px', maxWidth: '340px' }}>
          <Search size={15} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dim)' }} />
          <input
            type="text"
            placeholder={t('search_tables_ph')}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              width: '100%',
              padding: '7px 12px 7px 32px',
              background: 'var(--card-bg)',
              border: '1px solid var(--border-color)',
              borderRadius: '6px',
              color: 'var(--text-main)',
              fontSize: '0.85rem',
              outline: 'none'
            }}
          />
        </div>

        <div style={{ display: 'flex', gap: '2px', background: 'var(--card-hover)', padding: '3px', borderRadius: '7px' }}>
          <button onClick={() => setStatusFilter('all')} style={segBtn(statusFilter === 'all')}>
            {t('all_tables')} <span style={{ color: 'var(--text-dim)' }}>{totalTables}</span>
          </button>
          <button onClick={() => setStatusFilter('frozen')} style={segBtn(statusFilter === 'frozen')}>
            {t('pending_approval')} <span style={{ color: 'var(--text-dim)' }}>{frozenCount}</span>
          </button>
          <button onClick={() => setStatusFilter('healthy')} style={segBtn(statusFilter === 'healthy')}>
            {t('healthy')} <span style={{ color: 'var(--text-dim)' }}>{healthyCount}</span>
          </button>
        </div>
      </div>

      {Object.values(groupedPipelines).map((pipeline) => {
        const filteredTables = pipeline.tables.filter(tb => {
          const q = searchTerm.toLowerCase();
          const matchesSearch = tb.table_name.toLowerCase().includes(q) || pipeline.name.toLowerCase().includes(q);
          const matchesStatus = statusFilter === 'all' ||
                                (statusFilter === 'frozen' && tb.is_frozen) ||
                                (statusFilter === 'healthy' && !tb.is_frozen);
          return matchesSearch && matchesStatus;
        });

        if (filteredTables.length === 0) return null;

        const isCollapsed = collapsedPipelines[pipeline.name];
        const pipelineFrozenCount = filteredTables.filter(tb => tb.is_frozen).length;

        return (
          <div
            key={pipeline.name}
            style={{ background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius)', overflow: 'hidden', boxShadow: 'var(--shadow)' }}
          >
            <div
              role="button"
              tabIndex={0}
              onClick={() => togglePipelineCollapse(pipeline.name)}
              onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), togglePipelineCollapse(pipeline.name))}
              style={{
                padding: '12px 16px',
                borderBottom: isCollapsed ? 'none' : '1px solid var(--border-color)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: '12px',
                cursor: 'pointer',
                userSelect: 'none'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0 }}>
                {isCollapsed ? <ChevronRight size={16} color="var(--text-dim)" /> : <ChevronDown size={16} color="var(--text-dim)" />}
                <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{pipeline.name}</span>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>
                  {filteredTables.length} {t('monitored_tables_count').toLowerCase()}
                </span>
                {pipelineFrozenCount > 0 && (
                  <span className="pill warning"><span className="dot" />{pipelineFrozenCount} {t('pending_approval').toLowerCase()}</span>
                )}
              </div>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', whiteSpace: 'nowrap', fontFamily: 'var(--mono)' }}>
                {modeLabel(pipeline)}
              </span>
            </div>

            {!isCollapsed && (
              <table className="schema-table fixed">
                <colgroup>
                  <col style={{ width: '46%' }} />
                  <col style={{ width: '12%' }} />
                  <col style={{ width: '20%' }} />
                  <col style={{ width: '22%' }} />
                </colgroup>
                <thead>
                  <tr>
                    <th>{t('table_name')}</th>
                    <th>{t('version')}</th>
                    <th>{t('status')}</th>
                    <th>{t('last_scan')}</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTables.map(table => (
                    <tr
                      key={table.registry_key}
                      className="list-row-clickable"
                      tabIndex={0}
                      onClick={() => onSelectTable(table.registry_key)}
                      onKeyDown={(e) => e.key === 'Enter' && onSelectTable(table.registry_key)}
                    >
                      <td>
                        <div style={{ fontWeight: 500 }}>{table.table_name}</div>
                        <code style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>{table.registry_key}</code>
                      </td>
                      <td>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: '0.8rem', color: 'var(--text-muted)' }}>v{table.version || 1}</span>
                      </td>
                      <td>
                        {table.is_frozen ? (
                          <span className="pill warning"><span className="dot" />{t('pending_approval')}</span>
                        ) : (
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                            <span className="dot" style={{ color: 'var(--success-color)' }} />{t('healthy')}
                          </span>
                        )}
                      </td>
                      <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>
                        {table.updated_at !== '—' ? new Date(table.updated_at).toLocaleString() : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        );
      })}
    </div>
  );
}
