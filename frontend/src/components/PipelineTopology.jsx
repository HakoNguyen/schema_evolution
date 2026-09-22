import React, { useState, useEffect } from 'react';
import { Database, Cpu, ShieldCheck, HardDrive, ArrowRight, RefreshCw, AlertTriangle, CheckCircle2, ShieldAlert, ChevronDown, ChevronRight, Layers, Filter } from 'lucide-react';
import { useToast } from './NotificationToast';

export default function PipelineTopology() {
  const [pipelines, setPipelines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(null);
  const [selectedPipeline, setSelectedPipeline] = useState('all');
  const [expandedPipelines, setExpandedPipelines] = useState({});
  const { addToast } = useToast();

  const fetchTopology = () => {
    setLoading(true);
    setFetchError(null);
    fetch('/api/topology')
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: không thể lấy thông tin sơ đồ`);
        return res.json();
      })
      .then(data => {
        setPipelines(data);
        // Default expand the first pipeline if expandedPipelines is empty
        if (data.length > 0 && Object.keys(expandedPipelines).length === 0) {
          setExpandedPipelines({ [data[0].name]: true });
        }
        setFetchError(null);
      })
      .catch(err => {
        console.error("Error fetching topology:", err);
        setFetchError(err.message || "Lỗi kết nối tới hệ thống");
        addToast("Không thể tải sơ đồ luồng dữ liệu. Vui lòng kiểm tra API backend.", "error");
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchTopology();
    const interval = setInterval(fetchTopology, 8000);
    return () => clearInterval(interval);
  }, []);

  const toggleExpand = (name) => {
    setExpandedPipelines(prev => ({
      ...prev,
      [name]: !prev[name]
    }));
  };

  const filteredPipelines = selectedPipeline === 'all' 
    ? pipelines 
    : pipelines.filter(p => p.name === selectedPipeline);

  return (
    <div style={{ background: '#151d2a', border: '1px solid #1e293b', borderRadius: '10px', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '16px 20px', borderBottom: '1px solid #1e293b', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#0d131f' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Layers size={18} color="#38bdf8" /> Pipeline Topology Visualizer
          </h3>
          <p style={{ margin: '2px 0 0 0', fontSize: '0.8rem', color: '#64748b' }}>
            Sơ đồ luồng dữ liệu thời gian thực giữa các Database và Data Warehouse
          </p>
        </div>
        <button 
          className="btn-outline" 
          style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', fontSize: '0.8rem' }} 
          onClick={fetchTopology}
        >
          <RefreshCw size={13} className={loading ? "spin" : ""} /> Làm mới
        </button>
      </div>

      {/* Pipeline Selector / Filter Bar */}
      <div style={{ padding: '12px 20px', background: '#0b0f17', borderBottom: '1px solid #1e293b', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Filter size={14} color="#64748b" />
          <span style={{ fontSize: '0.8rem', color: '#94a3b8', fontWeight: 600 }}>CHỌN PIPELINE:</span>
          <select 
            value={selectedPipeline} 
            onChange={(e) => setSelectedPipeline(e.target.value)}
            style={{
              padding: '6px 12px',
              borderRadius: '6px',
              background: '#151d2a',
              border: '1px solid #1e293b',
              color: '#38bdf8',
              fontSize: '0.85rem',
              fontWeight: 600,
              outline: 'none',
              cursor: 'pointer'
            }}
          >
            <option value="all">Tất cả Pipelines ({pipelines.length})</option>
            {pipelines.map(p => (
              <option key={p.name} value={p.name}>
                {p.name} ({p.target?.configured ? `${p.source?.type} ➔ ${p.target?.type}` : `${p.source?.type} (Self-Monitor)`})
              </option>
            ))}

          </select>
        </div>

        {/* Quick Tabs Pill */}
        <div style={{ display: 'flex', gap: '6px', overflowX: 'auto', maxWidth: '100%', paddingBottom: '2px' }}>
          <button
            onClick={() => setSelectedPipeline('all')}
            style={{
              padding: '4px 10px',
              borderRadius: '6px',
              fontSize: '0.75rem',
              fontWeight: 600,
              border: 'none',
              cursor: 'pointer',
              background: selectedPipeline === 'all' ? '#38bdf8' : '#151d2a',
              color: selectedPipeline === 'all' ? '#0b0f17' : '#94a3b8'
            }}
          >
            Tất cả
          </button>
          {pipelines.map(p => (
            <button
              key={p.name}
              onClick={() => setSelectedPipeline(p.name)}
              style={{
                padding: '4px 10px',
                borderRadius: '6px',
                fontSize: '0.75rem',
                fontWeight: 600,
                border: 'none',
                cursor: 'pointer',
                background: selectedPipeline === p.name ? '#38bdf8' : '#151d2a',
                color: selectedPipeline === p.name ? '#0b0f17' : '#94a3b8',
                whiteSpace: 'nowrap'
              }}
            >
              {p.name}
            </button>
          ))}
        </div>
      </div>

      <div style={{ padding: '20px' }}>
        {fetchError && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            background: 'rgba(244, 63, 94, 0.1)',
            border: '1px solid rgba(244, 63, 94, 0.3)',
            borderRadius: '8px',
            padding: '12px 16px',
            color: '#f43f5e',
            fontSize: '0.875rem',
            marginBottom: '16px'
          }}>
            <ShieldAlert size={18} />
            <span><strong>Lỗi kết nối topology:</strong> {fetchError}</span>
          </div>
        )}

        {loading && pipelines.length === 0 ? (
          <div className="no-data">Đang tải sơ đồ...</div>
        ) : filteredPipelines.length === 0 && !fetchError ? (
          <div className="no-data">Không tìm thấy pipeline phù hợp.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {filteredPipelines.map(pipeline => {
              const isSingleView = selectedPipeline !== 'all';
              const isExpanded = isSingleView || !!expandedPipelines[pipeline.name];

              return (
                <div 
                  key={pipeline.name} 
                  style={{ 
                    background: '#0b0f17', 
                    border: '1px solid #1e293b', 
                    borderRadius: '8px', 
                    overflow: 'hidden',
                    transition: 'all 0.2s ease-in-out'
                  }}
                >
                  {/* Accordion Bar Header */}
                  <div 
                    onClick={() => !isSingleView && toggleExpand(pipeline.name)}
                    style={{ 
                      padding: '14px 18px', 
                      display: 'flex', 
                      justify: 'space-between', 
                      alignItems: 'center',
                      cursor: isSingleView ? 'default' : 'pointer',
                      background: isExpanded ? '#111827' : '#0b0f17',
                      userSelect: 'none'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      {!isSingleView && (
                        <div style={{ color: '#64748b', display: 'flex', alignItems: 'center' }}>
                          {isExpanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                        </div>
                      )}
                      <span style={{ fontSize: '0.9rem', fontWeight: 700, color: '#f8fafc' }}>
                        Pipeline: <code style={{ color: '#38bdf8' }}>{pipeline.name}</code>
                      </span>
                      <span style={{ fontSize: '0.75rem', color: '#64748b', marginLeft: '6px' }}>
                        ({pipeline.target.configured 
                          ? `${pipeline.source.type.toUpperCase()} ➔ ${pipeline.target.type.toUpperCase()}` 
                          : `${pipeline.source.type.toUpperCase()} (Self-Monitor)`
                        })
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                      <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                        {pipeline.tables?.length || 0} bảng theo dõi
                      </div>
                      <div style={{ fontSize: '0.75rem', color: pipeline.gatekeeper.status === 'healthy' ? '#10b981' : '#f43f5e', fontWeight: 600 }}>
                        {pipeline.gatekeeper.status === 'healthy' ? '● Hoạt động' : '● Chờ duyệt'}
                      </div>
                    </div>
                  </div>

                  {/* Expanded Content View */}
                  {isExpanded && (
                    <div style={{ padding: '16px 18px', borderTop: '1px solid #1e293b', background: '#0b0f17' }}>
                      {/* 4-Node Diagram Flow */}
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', overflowX: 'auto', paddingBottom: '8px' }}>
                        
                        {/* Node 1: Source */}
                        <div style={{ flex: 1, minWidth: '130px', background: '#151d2a', border: '1px solid #1e293b', borderRadius: '6px', padding: '12px', textAlign: 'center' }}>
                          <Database size={20} color="#38bdf8" style={{ marginBottom: '4px' }} />
                          <div style={{ fontSize: '0.65rem', color: '#64748b', fontWeight: 700 }}>NGUỒN</div>
                          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc', textTransform: 'uppercase' }}>{pipeline.source.type}</div>
                          <div style={{ fontSize: '0.7rem', color: '#64748b' }}>{pipeline.source.host}</div>
                        </div>

                        <ArrowRight size={16} color="#475569" />

                        {/* Node 2: CDC Broker */}
                        <div style={{ flex: 1, minWidth: '130px', background: '#151d2a', border: '1px solid #1e293b', borderRadius: '6px', padding: '12px', textAlign: 'center' }}>
                          <Cpu size={20} color="#10b981" style={{ marginBottom: '4px' }} />
                          <div style={{ fontSize: '0.65rem', color: '#64748b', fontWeight: 700 }}>CDC BROKER</div>
                          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc' }}>Redpanda</div>
                          <div style={{ fontSize: '0.7rem', color: '#10b981' }}>{pipeline.broker.topic}</div>
                        </div>

                        <ArrowRight size={16} color="#475569" />

                        {/* Node 3: Engine */}
                        <div style={{ 
                          flex: 1, 
                          minWidth: '140px', 
                          background: '#151d2a', 
                          border: pipeline.gatekeeper.status === 'healthy' ? '1px solid rgba(56, 189, 248, 0.3)' : '1px solid rgba(244, 63, 94, 0.3)', 
                          borderRadius: '6px', 
                          padding: '12px', 
                          textAlign: 'center' 
                        }}>
                          <ShieldCheck size={20} color={pipeline.gatekeeper.status === 'healthy' ? '#38bdf8' : '#f43f5e'} style={{ marginBottom: '4px' }} />
                          <div style={{ fontSize: '0.65rem', color: '#64748b', fontWeight: 700 }}>ENGINE</div>
                          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc' }}>Gatekeeper</div>
                          <div style={{ fontSize: '0.7rem', color: pipeline.gatekeeper.status === 'healthy' ? '#38bdf8' : '#f43f5e', fontWeight: 600 }}>
                            {pipeline.gatekeeper.status === 'healthy' ? 'Normal' : 'Frozen'}
                          </div>
                        </div>

                        <ArrowRight size={16} color="#475569" />

                        {/* Node 4: Target */}
                        <div style={{ flex: 1, minWidth: '130px', background: '#151d2a', border: '1px solid #1e293b', borderRadius: '6px', padding: '12px', textAlign: 'center' }}>
                          <HardDrive size={20} color="#f59e0b" style={{ marginBottom: '4px' }} />
                          <div style={{ fontSize: '0.65rem', color: '#64748b', fontWeight: 700 }}>
                            {pipeline.target.configured ? 'ĐÍCH WAREHOUSE' : 'ĐÍCH (SELF-MONITOR)'}
                          </div>
                          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc', textTransform: 'uppercase' }}>
                            {pipeline.target.configured ? pipeline.target.type : pipeline.source.type}
                          </div>
                          <div style={{ fontSize: '0.7rem', color: '#64748b' }}>
                            {pipeline.target.configured ? 'Auto Sync Target' : 'Theo dõi Nguồn (No Sync)'}
                          </div>
                        </div>


                      </div>

                      {/* Monitored Tables List */}
                      <div style={{ marginTop: '12px', paddingTop: '10px', borderTop: '1px dashed #1e293b', display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                        <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#64748b' }}>BẢNG THEO DÕI:</span>
                        {pipeline.tables.map(t => (
                          <span 
                            key={t.name} 
                            style={{ 
                              display: 'inline-flex', 
                              alignItems: 'center', 
                              gap: '4px', 
                              background: '#151d2a', 
                              border: '1px solid #1e293b', 
                              borderRadius: '4px', 
                              padding: '3px 8px', 
                              fontSize: '0.75rem', 
                              color: '#f8fafc' 
                            }}
                          >
                            {t.is_frozen ? <AlertTriangle size={11} color="#f43f5e" /> : <CheckCircle2 size={11} color="#10b981" />}
                            <span>{t.name}</span>
                            <span style={{ fontSize: '0.65rem', color: '#38bdf8' }}>v{t.version}</span>
                          </span>
                        ))}
                      </div>

                    </div>
                  )}

                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
