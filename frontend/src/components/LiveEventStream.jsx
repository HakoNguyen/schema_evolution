import React, { useState, useEffect } from 'react';
import { Zap, Clock, ShieldCheck, AlertOctagon, CheckCircle, RefreshCw, Radio } from 'lucide-react';

export default function LiveEventStream() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchEvents = () => {
    fetch('/api/events')
      .then(res => res.json())
      .then(data => setEvents(data))
      .catch(err => console.error("Error fetching events", err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchEvents();
    if (!autoRefresh) return;
    const interval = setInterval(fetchEvents, 2000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  return (
    <div className="table-details-card" style={{ padding: 0 }}>
      <div className="card-header" style={{ padding: '24px 24px 16px 24px', marginBottom: 0, borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <h3 style={{ margin: 0 }}>Live CDC Event Stream</h3>
            <span className="badge badge-outline" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', background: '#f0fdf4', color: '#16a34a', borderColor: '#bbf7d0' }}>
              <Radio size={12} className="spin" /> Real-time Audit Feed
            </span>
          </div>
          <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Intercepted DDL events streamed via Debezium CDC and evaluated instantaneously by Schema Evolution Core
          </p>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', cursor: 'pointer' }}>
            <input 
              type="checkbox" 
              checked={autoRefresh} 
              onChange={e => setAutoRefresh(e.target.checked)} 
            />
            Auto-refresh (2s)
          </label>
          <button className="btn-outline" style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px' }} onClick={fetchEvents}>
            <RefreshCw size={14} className={loading ? "spin" : ""} /> Refresh
          </button>
        </div>
      </div>

      <div style={{ padding: '24px' }}>
        {events.length === 0 ? (
          <div className="no-data" style={{ padding: '40px' }}>
            <Zap size={32} style={{ opacity: 0.3, marginBottom: '12px' }} />
            <p>No CDC events captured yet.</p>
            <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
              Execute a DDL query (e.g., <code>ALTER TABLE customers ADD COLUMN...</code>) on the source database to view live events!
            </span>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {events.map((event) => {
              const isBreaking = event.severity === 'breaking' || event.status === 'frozen';
              return (
                <div 
                  key={event.id} 
                  style={{
                    background: '#ffffff',
                    border: '1px solid #e2e8f0',
                    borderLeft: isBreaking ? '4px solid #ef4444' : '4px solid #0ea5e9',
                    borderRadius: '8px',
                    padding: '16px 20px',
                    boxShadow: '0 1px 2px rgba(0,0,0,0.02)',
                    transition: 'all 0.2s ease'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontWeight: 700, fontSize: '0.95rem', color: '#0f172a' }}>
                        {event.pipeline_name} / <code>{event.table_name}</code>
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <span style={{ fontSize: '0.8rem', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Clock size={12} /> {new Date(event.timestamp).toLocaleTimeString()}
                      </span>

                      {isBreaking ? (
                        <span className="status-frozen" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '3px 10px', fontSize: '0.75rem' }}>
                          <AlertOctagon size={12} /> Frozen (Breaking Change)
                        </span>
                      ) : (
                        <span className="status-normal" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '3px 10px', fontSize: '0.75rem' }}>
                          <CheckCircle size={12} /> Auto-Synced to Warehouse
                        </span>
                      )}
                    </div>
                  </div>

                  <div style={{ background: '#f8fafc', border: '1px solid #f1f5f9', borderRadius: '6px', padding: '10px 14px', fontFamily: 'monospace', fontSize: '0.85rem', color: '#1e293b', overflowX: 'auto' }}>
                    {event.ddl}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
