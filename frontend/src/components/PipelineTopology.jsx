import React, { useState, useEffect } from 'react';
import { Database, Cpu, ShieldCheck, HardDrive, ArrowRight, RefreshCw, AlertTriangle, CheckCircle2, ShieldAlert, ChevronDown, ChevronRight, Layers, Filter, Clock } from 'lucide-react';
import { useToast } from './NotificationToast';
import { useLanguage } from '../context/LanguageContext';

const STATUS_STYLE = {
  active: { color: 'var(--success-color)', label: { en: 'Running', vi: 'Đang chạy' } },
  connecting: { color: 'var(--text-muted)', label: { en: 'Connecting…', vi: 'Đang kết nối…' } },
  pending: { color: 'var(--text-muted)', label: { en: 'Not scanned yet', vi: 'Chưa quét' } },
  disconnected: { color: 'var(--danger-color)', label: { en: 'Disconnected', vi: 'Mất kết nối' } },
  error: { color: 'var(--danger-color)', label: { en: 'Last scan failed', vi: 'Lần quét gần nhất lỗi' } },
};

// Trạng thái chạy thật lấy từ /api/topology (scheduler / Kafka consumer).
function RuntimeStatus({ status, error, lastScanAt }) {
  const { lang } = useLanguage();
  const s = STATUS_STYLE[status] || STATUS_STYLE.pending;
  return (
    <div title={error || ''} style={{ fontSize: '0.7rem', color: s.color, marginTop: '4px', fontWeight: 600 }}>
      ● {s.label[lang] || s.label.en}
      {lastScanAt && (
        <span style={{ color: 'var(--text-dim)', fontWeight: 400 }}> · {new Date(lastScanAt).toLocaleTimeString()}</span>
      )}
    </div>
  );
}

export default function PipelineTopology() {
  const [pipelines, setPipelines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(null);
  const [selectedPipeline, setSelectedPipeline] = useState('all');
  const [expandedPipelines, setExpandedPipelines] = useState({});
  const { addToast } = useToast();
  const { t } = useLanguage();

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
    <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '10px', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--card-bg)' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Layers size={18} color="var(--primary-color)" /> {t('topology_title')}
          </h3>
          <p style={{ margin: '2px 0 0 0', fontSize: '0.8rem', color: 'var(--text-dim)' }}>
            {t('topology_sub')}
          </p>
        </div>
        <button 
          className="btn-outline" 
          style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', fontSize: '0.8rem' }} 
          onClick={fetchTopology}
        >
          <RefreshCw size={13} className={loading ? "spin" : ""} /> {t('refresh')}
        </button>
      </div>

      {/* Pipeline Selector / Filter Bar */}
      <div style={{ padding: '12px 20px', background: 'var(--body-bg)', borderBottom: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Filter size={14} color="var(--text-dim)" />
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>{t('select_pipeline')}</span>
          <select 
            value={selectedPipeline} 
            onChange={(e) => setSelectedPipeline(e.target.value)}
            style={{
              padding: '6px 12px',
              borderRadius: '6px',
              background: 'var(--card-bg)',
              border: '1px solid var(--border-color)',
              color: 'var(--primary-color)',
              fontSize: '0.85rem',
              fontWeight: 600,
              outline: 'none',
              cursor: 'pointer'
            }}
          >
            <option value="all">{t('all_pipelines')} ({pipelines.length})</option>
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
              background: selectedPipeline === 'all' ? 'var(--primary-color)' : 'var(--card-bg)',
              color: selectedPipeline === 'all' ? '#0b0f17' : 'var(--text-muted)'
            }}
          >
            All
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
                background: selectedPipeline === p.name ? 'var(--primary-color)' : 'var(--card-bg)',
                color: selectedPipeline === p.name ? '#0b0f17' : 'var(--text-muted)',
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
            background: 'var(--danger-bg)',
            border: '1px solid var(--danger-border)',
            borderRadius: '8px',
            padding: '12px 16px',
            color: 'var(--danger-color)',
            fontSize: '0.875rem',
            marginBottom: '16px'
          }}>
            <ShieldAlert size={18} />
            <span><strong>Connection error:</strong> {fetchError}</span>
          </div>
        )}

        {loading && pipelines.length === 0 ? (
          <div className="no-data">Loading topology...</div>
        ) : filteredPipelines.length === 0 && !fetchError ? (
          <div className="no-data">No matching pipeline found.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {filteredPipelines.map(pipeline => {
              const isSingleView = selectedPipeline !== 'all';
              const isExpanded = isSingleView || !!expandedPipelines[pipeline.name];

              return (
                <div 
                  key={pipeline.name} 
                  style={{ 
                    background: 'var(--body-bg)', 
                    border: '1px solid var(--border-color)', 
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
                      justifyContent: 'space-between', 
                      alignItems: 'center',
                      cursor: isSingleView ? 'default' : 'pointer',
                      background: isExpanded ? 'var(--card-hover)' : 'var(--body-bg)',
                      userSelect: 'none'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      {!isSingleView && (
                        <div style={{ color: 'var(--text-dim)', display: 'flex', alignItems: 'center' }}>
                          {isExpanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                        </div>
                      )}
                      <span style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-main)' }}>
                        Pipeline: <code style={{ color: 'var(--primary-color)' }}>{pipeline.name}</code>
                      </span>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginLeft: '6px' }}>
                        ({(pipeline.transport?.kind === 'broker' || pipeline.broker?.kind === 'broker')
                          ? `${pipeline.source?.type?.toUpperCase()} ➔ ${pipeline.target?.configured ? pipeline.target.type.toUpperCase() : 'SELF-MONITOR'} [CDC]` 
                          : `${pipeline.source?.type?.toUpperCase()} ➔ ${pipeline.target?.configured ? pipeline.target.type.toUpperCase() : 'SELF-MONITOR'} [Polling]`
                        })
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        {pipeline.tables?.length || 0} {t('monitored_tables_count')}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: pipeline.gatekeeper?.status === 'healthy' ? 'var(--success-color)' : 'var(--danger-color)', fontWeight: 600 }}>
                        {pipeline.gatekeeper?.status === 'healthy' ? `● ${t('healthy')}` : `● ${t('paused')}`}
                      </div>
                    </div>
                  </div>

                  {/* Expanded Content View */}
                  {isExpanded && (
                    <div style={{ padding: '16px 18px', borderTop: '1px solid var(--border-color)', background: 'var(--body-bg)' }}>
                      {/* 4-Node Diagram Flow */}
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', overflowX: 'auto', padding: '8px 0 16px 0' }}>
                        
                        {/* Node 1: Source */}
                        <div style={{ flex: 1, minWidth: '140px', background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '16px 12px', textAlign: 'center' }}>
                          <Database size={22} color="var(--primary-color)" style={{ marginBottom: '6px' }} />
                          <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px' }}>{t('node_source')}</div>
                          <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-main)', textTransform: 'uppercase', marginTop: '2px' }}>{pipeline.source?.type}</div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '2px' }}>{pipeline.source?.host}</div>
                        </div>

                        <ArrowRight size={18} color="var(--text-dim)" style={{ flexShrink: 0 }} />

                        {/* Node 2: Transport (Kafka Broker vs Polling Scheduler) */}
                        {(pipeline.transport?.kind === 'broker' || pipeline.broker?.kind === 'broker') ? (
                          <div style={{ flex: 1, minWidth: '140px', background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '16px 12px', textAlign: 'center' }}>
                            <Cpu size={22} color="var(--success-color)" style={{ marginBottom: '6px' }} />
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px' }}>{t('node_broker')}</div>
                            <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-main)', marginTop: '2px' }}>Redpanda Kafka</div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--success-color)', marginTop: '2px' }}>{pipeline.transport?.topic || pipeline.broker?.topic || pipeline.name}</div>
                            <RuntimeStatus status={pipeline.transport?.status} error={pipeline.transport?.error} />
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                              ({t('polling_fallback')} {pipeline.transport?.fallback?.interval}s)
                            </div>
                            <RuntimeStatus
                              status={pipeline.transport?.fallback?.status}
                              error={pipeline.transport?.fallback?.last_error}
                              lastScanAt={pipeline.transport?.fallback?.last_scan_at}
                            />
                          </div>
                        ) : (
                          <div style={{ flex: 1, minWidth: '140px', background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '16px 12px', textAlign: 'center' }}>
                            <Clock size={22} color="var(--primary-color)" style={{ marginBottom: '6px' }} />
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px' }}>{t('node_scheduler')}</div>
                            <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-main)', marginTop: '2px' }}>Polling Scanner</div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--primary-color)', marginTop: '2px' }}>Interval: {pipeline.transport?.interval}s</div>
                            <RuntimeStatus
                              status={pipeline.transport?.status}
                              error={pipeline.transport?.last_error}
                              lastScanAt={pipeline.transport?.last_scan_at}
                            />
                          </div>
                        )}

                        <ArrowRight size={18} color="var(--text-dim)" style={{ flexShrink: 0 }} />

                        {/* Node 3: Engine */}
                        <div style={{ 
                          flex: 1, 
                          minWidth: '140px', 
                          background: 'var(--card-bg)', 
                          border: pipeline.gatekeeper?.status === 'healthy' ? '1px solid var(--primary-border)' : '1px solid var(--danger-border)', 
                          borderRadius: '8px', 
                          padding: '16px 12px', 
                          textAlign: 'center' 
                        }}>
                          <ShieldCheck size={22} color={pipeline.gatekeeper?.status === 'healthy' ? 'var(--primary-color)' : 'var(--danger-color)'} style={{ marginBottom: '6px' }} />
                          <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px' }}>{t('node_engine')}</div>
                          <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-main)', marginTop: '2px' }}>Gatekeeper</div>
                          <div style={{ fontSize: '0.75rem', color: pipeline.gatekeeper?.status === 'healthy' ? 'var(--primary-color)' : 'var(--danger-color)', fontWeight: 600, marginTop: '2px' }}>
                            {pipeline.gatekeeper?.status === 'healthy' ? t('healthy') : t('paused')}
                          </div>
                        </div>

                        <ArrowRight size={18} color="var(--text-dim)" style={{ flexShrink: 0 }} />

                        {/* Node 4: Target */}
                        <div style={{ flex: 1, minWidth: '140px', background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '16px 12px', textAlign: 'center' }}>
                          <HardDrive size={22} color="var(--warning-color)" style={{ marginBottom: '6px' }} />
                          <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                            {pipeline.target?.configured ? t('node_target') : 'Target (Self-monitor)'}
                          </div>
                          <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-main)', textTransform: 'uppercase', marginTop: '2px' }}>
                            {pipeline.target?.configured ? pipeline.target.type : pipeline.source?.type}
                          </div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '2px' }}>
                            {pipeline.target?.configured ? 'Auto Sync Target' : 'Self Monitor'}
                          </div>
                        </div>

                      </div>

                      {/* Monitored Tables List */}
                      <div style={{ marginTop: '4px', paddingTop: '12px', borderTop: '1px dashed var(--border-color)', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                        <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-dim)' }}>{t('monitored_tables_count')}:</span>
                        {pipeline.tables?.map(tItem => (
                          <span 
                            key={tItem.name} 
                            style={{ 
                              display: 'inline-flex', 
                              alignItems: 'center', 
                              gap: '6px', 
                              background: 'var(--card-bg)', 
                              border: '1px solid var(--border-color)', 
                              borderRadius: '4px', 
                              padding: '4px 10px', 
                              fontSize: '0.75rem', 
                              color: 'var(--text-main)' 
                            }}
                          >
                            {tItem.is_frozen ? <AlertTriangle size={12} color="var(--danger-color)" /> : <CheckCircle2 size={12} color="var(--success-color)" />}
                            <span>{tItem.name}</span>
                            <span style={{ fontSize: '0.7rem', color: 'var(--primary-color)', fontWeight: 600 }}>v{tItem.version}</span>
                          </span>
                        ))}
                      </div>                    </div>
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

