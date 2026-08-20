import React, { useState, useEffect } from 'react';
import { Database, Cpu, ShieldCheck, HardDrive, ArrowRight, RefreshCw, AlertTriangle, CheckCircle2 } from 'lucide-react';

export default function PipelineTopology() {
  const [pipelines, setPipelines] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchTopology = () => {
    setLoading(true);
    fetch('/api/topology')
      .then(res => res.json())
      .then(data => setPipelines(data))
      .catch(err => console.error("Error fetching topology", err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchTopology();
    const interval = setInterval(fetchTopology, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="table-details-card" style={{ padding: 0 }}>
      <div className="card-header" style={{ padding: '24px 24px 16px 24px', marginBottom: 0, borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={{ marginBottom: '4px' }}>Pipeline Topology Visualizer</h3>
          <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Real-time architecture mapping: Source DB ➔ Redpanda (Kafka CDC) ➔ Schema Evolution Engine ➔ Target Warehouse
          </p>
        </div>
        <button className="btn-outline" style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px' }} onClick={fetchTopology}>
          <RefreshCw size={14} className={loading ? "spin" : ""} /> Refresh
        </button>
      </div>

      <div style={{ padding: '24px' }}>
        {loading && pipelines.length === 0 ? (
          <div className="no-data">Loading pipeline topologies...</div>
        ) : pipelines.length === 0 ? (
          <div className="no-data">No active pipelines configured.</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            {pipelines.map(pipeline => (
              <div key={pipeline.name} className="topology-card" style={{ background: '#ffffff', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.03)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', paddingBottom: '12px', borderBottom: '1px solid #f1f5f9' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-dark)' }}>
                      Pipeline: <code style={{ color: 'var(--primary-color)', fontSize: '1rem' }}>{pipeline.name}</code>
                    </span>
                  </div>
                  <span className="badge badge-outline" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span className="live-dot"></span> Real-Time Event-Driven
                  </span>
                </div>

                {/* Node Flow Diagram */}
                <div className="topology-flow-grid" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', overflowX: 'auto', padding: '10px 0' }}>
                  
                  {/* Node 1: Source DB */}
                  <div className="topology-node" style={{ flex: '1', minWidth: '180px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '16px', textAlign: 'center' }}>
                    <div style={{ color: '#0284c7', marginBottom: '8px', display: 'flex', justifyContent: 'center' }}>
                      <Database size={28} />
                    </div>
                    <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>SOURCE DB</div>
                    <div style={{ fontSize: '1rem', fontWeight: 700, color: '#0f172a', margin: '4px 0', textTransform: 'uppercase' }}>{pipeline.source.type}</div>
                    <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>{pipeline.source.host}</div>
                  </div>

                  <ArrowRight size={20} color="#94a3b8" />

                  {/* Node 2: Redpanda Kafka CDC */}
                  <div className="topology-node" style={{ flex: '1', minWidth: '180px', background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: '8px', padding: '16px', textAlign: 'center' }}>
                    <div style={{ color: '#16a34a', marginBottom: '8px', display: 'flex', justifyContent: 'center' }}>
                      <Cpu size={28} />
                    </div>
                    <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#15803d', textTransform: 'uppercase' }}>CDC BROKER</div>
                    <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#14532d', margin: '4px 0' }}>Redpanda / Debezium</div>
                    <div style={{ fontSize: '0.75rem', color: '#16a34a', fontWeight: 600 }}>Topic: {pipeline.broker.topic}</div>
                  </div>

                  <ArrowRight size={20} color="#94a3b8" />

                  {/* Node 3: Schema Evolution Core */}
                  <div className="topology-node" style={{ flex: '1', minWidth: '200px', background: pipeline.gatekeeper.status === 'healthy' ? '#f0f9ff' : '#fef2f2', border: pipeline.gatekeeper.status === 'healthy' ? '1px solid #bae6fd' : '1px solid #fecaca', borderRadius: '8px', padding: '16px', textAlign: 'center' }}>
                    <div style={{ color: pipeline.gatekeeper.status === 'healthy' ? '#0284c7' : '#dc2626', marginBottom: '8px', display: 'flex', justifyContent: 'center' }}>
                      <ShieldCheck size={28} />
                    </div>
                    <div style={{ fontSize: '0.75rem', fontWeight: 700, color: pipeline.gatekeeper.status === 'healthy' ? '#0369a1' : '#991b1b', textTransform: 'uppercase' }}>SCHEMA ENGINE</div>
                    <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0f172a', margin: '4px 0' }}>Gatekeeper & Registry</div>
                    <div style={{ fontSize: '0.75rem', fontWeight: 600, color: pipeline.gatekeeper.status === 'healthy' ? '#0284c7' : '#dc2626' }}>
                      {pipeline.gatekeeper.status === 'healthy' ? '🟢 Gatekeeper Normal' : '🔴 Action Required'}
                    </div>
                  </div>

                  <ArrowRight size={20} color="#94a3b8" />

                  {/* Node 4: Target Warehouse */}
                  <div className="topology-node" style={{ flex: '1', minWidth: '180px', background: '#faf5ff', border: '1px solid #e9d5ff', borderRadius: '8px', padding: '16px', textAlign: 'center' }}>
                    <div style={{ color: '#9333ea', marginBottom: '8px', display: 'flex', justifyContent: 'center' }}>
                      <HardDrive size={28} />
                    </div>
                    <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#7e22ce', textTransform: 'uppercase' }}>TARGET WAREHOUSE</div>
                    <div style={{ fontSize: '1rem', fontWeight: 700, color: '#3b0764', margin: '4px 0', textTransform: 'uppercase' }}>
                      {pipeline.target.configured ? pipeline.target.type : 'None (Self-Monitor)'}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#a855f7' }}>
                      {pipeline.target.configured ? 'Auto-Sync Target' : 'Detection Only'}
                    </div>
                  </div>

                </div>

                {/* Monitored Tables Chips */}
                <div style={{ marginTop: '16px', paddingTop: '12px', borderTop: '1px dashed #e2e8f0', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#64748b' }}>Monitored Tables:</span>
                  {pipeline.tables.map(t => (
                    <div key={t.name} style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', background: '#f1f5f9', border: '1px solid #cbd5e1', borderRadius: '20px', padding: '4px 10px', fontSize: '0.8rem' }}>
                      {t.is_frozen ? <AlertTriangle size={12} color="#ef4444" /> : <CheckCircle2 size={12} color="#22c55e" />}
                      <span>{t.name}</span>
                      <span style={{ fontSize: '0.7rem', color: '#64748b', background: '#e2e8f0', borderRadius: '10px', padding: '1px 6px' }}>v{t.version}</span>
                    </div>
                  ))}
                </div>

              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
