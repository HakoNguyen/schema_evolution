import React, { useState, useEffect } from 'react';
import { Zap, Activity, Clock, Layers, Filter } from 'lucide-react';

export default function LiveEventStream() {
  const [events, setEvents] = useState([]);
  const [isLive, setIsLive] = useState(true);

  useEffect(() => {
    let interval = null;
    if (isLive) {
      const fetchEvents = () => {
        fetch('/api/events')
          .then(res => res.json())
          .then(data => setEvents(data))
          .catch(err => console.error("Error fetching live events", err));
      };

      fetchEvents();
      interval = setInterval(fetchEvents, 2000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isLive]);

  return (
    <div style={{ background: '#151d2a', border: '1px solid #1e293b', borderRadius: '10px', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '20px 24px', borderBottom: '1px solid #1e293b', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#0d131f' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Zap style={{ color: '#38bdf8' }} size={20} /> Live CDC Event Stream
          </h3>
          <p style={{ margin: '4px 0 0 0', fontSize: '0.85rem', color: '#94a3b8' }}>
            Luồng audit log trực tiếp bắt các sự kiện DDL / Payload CDC từ Redpanda Kafka Broker
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '0.8rem', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: isLive ? '#10b981' : '#64748b' }}></span>
            {isLive ? 'Real-Time Streaming Active' : 'Paused'}
          </span>
          <button 
            className="btn-outline"
            style={{ padding: '6px 14px', fontSize: '0.8rem' }}
            onClick={() => setIsLive(!isLive)}
          >
            {isLive ? 'Tạm Dừng' : 'Tiếp Tục Stream'}
          </button>
        </div>
      </div>

      {/* Events Stream List */}
      <div style={{ padding: '24px' }}>
        {events.length === 0 ? (
          <div className="no-data">Đang lắng nghe sự kiện CDC thời gian thực...</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {events.map((evt, idx) => {
              const isBreaking = evt.type === 'breaking' || evt.status === 'breaking_detected';
              const isNonBreaking = evt.type === 'non_breaking' || evt.status === 'auto_applied';

              return (
                <div key={idx} style={{
                  background: '#0b0f17',
                  border: isBreaking ? '1px solid rgba(244, 63, 94, 0.3)' : isNonBreaking ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid #1e293b',
                  borderLeft: isBreaking ? '4px solid #f43f5e' : isNonBreaking ? '4px solid #10b981' : '4px solid #38bdf8',
                  borderRadius: '8px',
                  padding: '16px 20px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
                      <span style={{
                        fontSize: '0.7rem',
                        fontWeight: 700,
                        padding: '2px 8px',
                        borderRadius: '4px',
                        textTransform: 'uppercase',
                        background: isBreaking ? 'rgba(244, 63, 94, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                        color: isBreaking ? '#f43f5e' : '#10b981'
                      }}>
                        {isBreaking ? 'BREAKING CHANGE' : 'AUTO SYNCED'}
                      </span>
                      <strong style={{ color: '#f8fafc', fontSize: '0.9rem' }}>{evt.table || evt.table_name || 'CDC Event'}</strong>
                      <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Pipeline: <code style={{ color: '#38bdf8' }}>{evt.pipeline || 'default'}</code></span>
                    </div>

                    <div style={{ fontSize: '0.85rem', color: '#cbd5e1' }}>
                      {evt.detail || evt.message || JSON.stringify(evt.changes || {})}
                    </div>
                  </div>

                  <div style={{ textAlign: 'right', fontSize: '0.75rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Clock size={12} /> {evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : 'Vừa xong'}
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
