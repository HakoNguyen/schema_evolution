import React, { useState } from 'react';
import { Database, AlertCircle, CheckCircle2, Layers, Search, Filter, ChevronDown, ChevronRight, Activity, ShieldAlert, Server } from 'lucide-react';

export default function TablesList({ tables, onSelectTable }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all'); // 'all' | 'frozen' | 'healthy'
  const [collapsedPipelines, setCollapsedPipelines] = useState({});

  if (!tables || tables.length === 0) {
    return <div className="no-data">Không có bảng dữ liệu nào đang được theo dõi.</div>;
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
        <div className="metric-card" style={{ background: '#151d2a', border: '1px solid #1e293b' }}>
          <div className="metric-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Layers size={14} style={{ color: '#38bdf8' }} /> TỔNG PIPELINES
          </div>
          <div className="metric-value" style={{ color: '#38bdf8' }}>{totalPipelines}</div>
        </div>

        <div className="metric-card" style={{ background: '#151d2a', border: '1px solid #1e293b' }}>
          <div className="metric-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Database size={14} style={{ color: '#f8fafc' }} /> BẢNG THEO DÕI
          </div>
          <div className="metric-value" style={{ color: '#f8fafc' }}>{totalTables}</div>
        </div>

        <div className="metric-card" style={{ background: '#151d2a', border: '1px solid #1e293b' }}>
          <div className="metric-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <ShieldAlert size={14} style={{ color: frozenCount > 0 ? '#f43f5e' : '#64748b' }} /> CẦN PHÊ DUYỆT (FROZEN)
          </div>
          <div className="metric-value" style={{ color: frozenCount > 0 ? '#f43f5e' : '#94a3b8' }}>{frozenCount}</div>
        </div>

        <div className="metric-card" style={{ background: '#151d2a', border: '1px solid #1e293b' }}>
          <div className="metric-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Activity size={14} style={{ color: '#10b981' }} /> ĐỘ TÔN TẠI AN TOÀN
          </div>
          <div className="metric-value" style={{ color: '#10b981' }}>{healthRate}%</div>
        </div>
      </div>

      {/* 2. SEARCH & STATUS FILTER TOOLBAR */}
      <div style={{
        display: 'flex',
        justify: 'space-between',
        alignItems: 'center',
        background: '#151d2a',
        border: '1px solid #1e293b',
        borderRadius: '10px',
        padding: '12px 16px',
        gap: '16px'
      }}>
        {/* Search Input */}
        <div style={{ position: 'relative', flex: 1, maxWidth: '380px' }}>
          <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#64748b' }} />
          <input
            type="text"
            placeholder="Tìm kiếm bảng hoặc luồng pipeline..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{
              width: '100%',
              padding: '8px 12px 8px 36px',
              background: '#0b0f17',
              border: '1px solid #1e293b',
              borderRadius: '6px',
              color: '#f8fafc',
              fontSize: '0.875rem',
              outline: 'none'
            }}
          />
        </div>

        {/* Status Filter Tabs */}
        <div style={{ display: 'flex', gap: '6px', background: '#0b0f17', padding: '4px', borderRadius: '8px', border: '1px solid #1e293b' }}>
          <button
            onClick={() => setStatusFilter('all')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: 'none',
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor: 'pointer',
              background: statusFilter === 'all' ? '#1e293b' : 'transparent',
              color: statusFilter === 'all' ? '#f8fafc' : '#94a3b8'
            }}
          >
            Tất Cả ({totalTables})
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
              background: statusFilter === 'frozen' ? 'rgba(244, 63, 94, 0.2)' : 'transparent',
              color: statusFilter === 'frozen' ? '#f43f5e' : '#94a3b8'
            }}
          >
            Cần Phê Duyệt ({frozenCount})
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
              background: statusFilter === 'healthy' ? 'rgba(16, 185, 129, 0.2)' : 'transparent',
              color: statusFilter === 'healthy' ? '#10b981' : '#94a3b8'
            }}
          >
            An Toàn ({healthyCount})
          </button>
        </div>
      </div>

      {/* 3. COLLAPSIBLE PIPELINE ACCORDIONS */}
      {Object.values(groupedPipelines).map(pipeline => {
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
              background: '#151d2a',
              border: '1px solid #1e293b',
              borderRadius: '10px',
              overflow: 'hidden'
            }}
          >
            {/* Pipeline Header */}
            <div 
              onClick={() => togglePipelineCollapse(pipeline.name)}
              style={{
                padding: '14px 20px',
                background: '#0d131f',
                borderBottom: isCollapsed ? 'none' : '1px solid #1e293b',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                cursor: 'pointer',
                userSelect: 'none'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                {isCollapsed ? <ChevronRight size={18} color="#94a3b8" /> : <ChevronDown size={18} color="#94a3b8" />}
                <Layers size={18} style={{ color: '#38bdf8' }} />
                <span style={{ fontWeight: 700, fontSize: '0.95rem', color: '#f8fafc' }}>
                  Pipeline: <code style={{ color: '#38bdf8', fontSize: '0.95rem' }}>{pipeline.name}</code>
                </span>
                <span style={{ fontSize: '0.75rem', padding: '2px 8px', borderRadius: '4px', background: '#1e293b', color: '#94a3b8', border: '1px solid #334155' }}>
                  {filteredTables.length} bảng
                </span>
                {pipelineFrozenCount > 0 && (
                  <span style={{ fontSize: '0.75rem', padding: '2px 8px', borderRadius: '4px', background: 'rgba(244, 63, 94, 0.2)', color: '#f43f5e', border: '1px solid rgba(244, 63, 94, 0.3)', fontWeight: 600 }}>
                    {pipelineFrozenCount} cần phê duyệt
                  </span>
                )}
              </div>

              <span style={{ fontSize: '0.75rem', color: '#94a3b8', background: '#0b0f17', padding: '4px 10px', borderRadius: '6px', border: '1px solid #1e293b', fontWeight: 600 }}>
                {pipeline.mode}
              </span>
            </div>

            {/* Tables list in accordion */}
            {!isCollapsed && (
              <div className="schema-table-wrapper" style={{ border: 'none', borderRadius: 0 }}>
                <table className="schema-table">
                  <thead>
                    <tr>
                      <th style={{ width: '40%' }}>TÊN BẢNG / NAMESPACE KEY</th>
                      <th>PHIÊN BẢN</th>
                      <th>TRẠNG THÁI</th>
                      <th>THỜI GIAN QUÉT GẦN NHẤT</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredTables.map(table => (
                      <tr 
                        key={table.registry_key} 
                        className="list-row-clickable"
                        onClick={() => onSelectTable(table.registry_key)}
                      >
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <Database size={16} style={{ color: '#94a3b8' }} />
                            <div>
                              <strong style={{ color: '#f8fafc', fontSize: '0.9rem' }}>{table.table_name}</strong>
                              <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                                <code style={{ fontSize: '0.75rem', color: '#38bdf8' }}>{table.registry_key}</code>
                              </div>
                            </div>
                          </div>
                        </td>
                        <td>
                          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#38bdf8', background: 'rgba(56, 189, 248, 0.1)', padding: '2px 8px', borderRadius: '12px', border: '1px solid rgba(56, 189, 248, 0.2)' }}>
                            v{table.version || 1}
                          </span>
                        </td>
                        <td>
                          {table.is_frozen ? (
                            <span className="status-frozen" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', background: 'rgba(244, 63, 94, 0.15)', padding: '4px 10px', borderRadius: '6px', border: '1px solid rgba(244, 63, 94, 0.3)', fontSize: '0.8rem', fontWeight: 600 }}>
                              <AlertCircle size={14} /> Cần Phê Duyệt
                            </span>
                          ) : (
                            <span className="status-normal" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', background: 'rgba(16, 185, 129, 0.15)', padding: '4px 10px', borderRadius: '6px', border: '1px solid rgba(16, 185, 129, 0.3)', fontSize: '0.8rem', fontWeight: 600 }}>
                              <CheckCircle2 size={14} /> Hoạt Động An Toàn
                            </span>
                          )}
                        </td>
                        <td style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
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
