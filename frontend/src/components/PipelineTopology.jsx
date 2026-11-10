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

// Trạng thái tổng của pipeline: lỗi kết nối > chờ duyệt > bình thường.
function pipelineHealth(p) {
  const tr = p.transport || p.broker || {};
  if ([tr.status, tr.fallback?.status].some(s => s === 'disconnected' || s === 'error')) {
    return { color: 'var(--danger-color)', key: 'degraded' };
  }
  if (p.gatekeeper?.status !== 'healthy') return { color: 'var(--warning-color)', key: 'pending_approval' };
  return { color: 'var(--success-color)', key: 'healthy' };
}

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
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
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
        setFetchError(err.message || t('toast_network_error'));
        addToast(t('err_load_topology'), "error");
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
            <Layers size={16} color="var(--text-dim)" /> {t('topology_title')}
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
              background: selectedPipeline === 'all' ? 'var(--card-hover)' : 'var(--card-bg)',
              color: selectedPipeline === 'all' ? 'var(--text-main)' : 'var(--text-muted)'
            }}
          >
            {t('all')}
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
                background: selectedPipeline === p.name ? 'var(--card-hover)' : 'var(--card-bg)',
                color: selectedPipeline === p.name ? 'var(--text-main)' : 'var(--text-muted)',
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
            <span><strong>{t('toast_network_error')}:</strong> {fetchError}</span>
          </div>
        )}

        {loading && pipelines.length === 0 ? (
          <div className="no-data">{t('loading')}</div>
        ) : filteredPipelines.length === 0 && !fetchError ? (
          <div className="no-data">{t('no_match')}</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {filteredPipelines.map(pipeline => {
              if (pipeline.config_error) {
                // File cấu hình lỗi: engine không giám sát pipeline này, các pipeline khác không bị ảnh hưởng.
                return (
                  <div key={pipeline.file} style={{ background: 'var(--body-bg)', border: '1px solid var(--danger-border)', borderRadius: '8px', padding: '14px 18px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px' }}>
                      <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>{pipeline.name}</span>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                        <span className="dot" style={{ color: 'var(--danger-color)' }} />{t('config_error')}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '6px' }}>
                      <code>config/pipelines/{pipeline.file}</code> · {t('config_error_hint')}
                    </div>
                    <code style={{ display: 'block', fontSize: '0.75rem', color: 'var(--danger-color)', marginTop: '6px', whiteSpace: 'pre-wrap' }}>{pipeline.config_error}</code>
                  </div>
                );
              }
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
                      <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>{pipeline.name}</span>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontFamily: 'var(--mono)' }}>
                        {pipeline.source?.type?.toUpperCase()} → {pipeline.target?.configured ? pipeline.target.type.toUpperCase() : t('source_only')}
                        {' · '}{(pipeline.transport?.kind === 'broker' || pipeline.broker?.kind === 'broker') ? 'CDC' : 'Polling'}
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                        {pipeline.tables?.length || 0} {t('monitored_tables_count').toLowerCase()}
                      </div>
                      {(() => {
                        const h = pipelineHealth(pipeline);
                        return (
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                            <span className="dot" style={{ color: h.color }} />{t(h.key)}
                          </span>
                        );
                      })()}
                    </div>
                  </div>

                  {/* Expanded Content View */}
                  {isExpanded && (
                    <div style={{ padding: '16px 18px', borderTop: '1px solid var(--border-color)', background: 'var(--body-bg)' }}>
                      {/* 4-Node Diagram Flow */}
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', overflowX: 'auto', padding: '8px 0 16px 0' }}>
                        
                        {/* Node 1: Source */}
                        <div style={{ flex: 1, minWidth: '140px', background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '16px 12px', textAlign: 'center' }}>
                          <Database size={18} color="var(--text-dim)" style={{ marginBottom: '6px' }} />
                          <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px' }}>{t('node_source')}</div>
                          <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-main)', textTransform: 'uppercase', marginTop: '2px' }}>{pipeline.source?.type}</div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '2px' }}>{pipeline.source?.host}</div>
                        </div>

                        <ArrowRight size={18} color="var(--text-dim)" style={{ flexShrink: 0 }} />

                        {/* Node 2: Transport (Kafka Broker vs Polling Scheduler) */}
                        {(pipeline.transport?.kind === 'broker' || pipeline.broker?.kind === 'broker') ? (
                          <div style={{ flex: 1, minWidth: '140px', background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '16px 12px', textAlign: 'center' }}>
                            <Cpu size={18} color="var(--text-dim)" style={{ marginBottom: '6px' }} />
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px' }}>{t('node_broker')}</div>
                            <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-main)', marginTop: '2px' }}>Redpanda Kafka</div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--mono)', marginTop: '2px' }}>{pipeline.transport?.topic || pipeline.broker?.topic || pipeline.name}</div>
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
                            <Clock size={18} color="var(--text-dim)" style={{ marginBottom: '6px' }} />
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px' }}>{t('node_scheduler')}</div>
                            <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-main)', marginTop: '2px' }}>Polling Scanner</div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>Interval: {pipeline.transport?.interval}s</div>
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
                          border: pipeline.gatekeeper?.status === 'healthy' ? '1px solid var(--border-color)' : '1px solid var(--warning-border)',
                          borderRadius: '8px',
                          padding: '16px 12px',
                          textAlign: 'center'
                        }}>
                          <ShieldCheck size={18} color={pipeline.gatekeeper?.status === 'healthy' ? 'var(--text-dim)' : 'var(--warning-color)'} style={{ marginBottom: '6px' }} />
                          <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.5px' }}>{t('node_engine')}</div>
                          <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-main)', marginTop: '2px' }}>Gatekeeper</div>
                          <div style={{ fontSize: '0.75rem', color: pipeline.gatekeeper?.status === 'healthy' ? 'var(--success-color)' : 'var(--warning-color)', fontWeight: 500, marginTop: '2px' }}>
                            {pipeline.gatekeeper?.status === 'healthy' ? t('healthy') : t('pending_approval')}
                          </div>
                        </div>

                        <ArrowRight size={18} color="var(--text-dim)" style={{ flexShrink: 0 }} />

                        {/* Node 4: Target */}
                        <div style={{ flex: 1, minWidth: '140px', background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '16px 12px', textAlign: 'center' }}>
                          <HardDrive size={18} color="var(--text-dim)" style={{ marginBottom: '6px' }} />
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
                            {tItem.is_frozen ? <AlertTriangle size={12} color="var(--warning-color)" /> : <CheckCircle2 size={12} color="var(--success-color)" />}
                            <span>{tItem.name}</span>
                            <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)', fontFamily: 'var(--mono)' }}>v{tItem.version}</span>
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

