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
    <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '10px', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--card-bg)' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Zap style={{ color: 'var(--primary-color)' }} size={20} /> Live CDC Event Stream
          </h3>
          <p style={{ margin: '4px 0 0 0', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Luồng audit log trực tiếp bắt các sự kiện DDL / Payload CDC từ Redpanda Kafka Broker
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: isLive ? 'var(--success-color)' : 'var(--text-dim)' }}></span>
            {isLive ? 'Real-Time Streaming Active' : 'Paused'}
          </span>
          <button 
            className="btn-outline"
            style={{ padding: '6px 14px', fontSize: '0.8rem' }}
            onClick={() => setIsLive(!isLive)}
          >
            {isLive ? 'Tạm dừng' : 'Tiếp tục stream'}
          </button>
        </div>
      </div>

      {/* Events Stream List */}
      <div style={{ padding: '20px' }}>
        {events.length === 0 ? (
          <div className="no-data" style={{ padding: '28px', minHeight: '180px' }}>
            <Activity size={28} style={{ opacity: 0.3, marginBottom: '10px', color: 'var(--primary-color)' }} className="spin" />
            <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-main)', marginBottom: '4px' }}>
              Đang lắng nghe sự kiện CDC thời gian thực
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', maxWidth: '420px' }}>
              Hệ thống đang kết nối tới Redpanda Broker topic. Sự kiện thay đổi DDL/Schema từ Database Nguồn sẽ tự động xuất hiện tại đây.
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {events.map((evt, idx) => {
              const isBreaking = evt.type === 'breaking' || evt.status === 'breaking_detected';
              const isNonBreaking = evt.type === 'non_breaking' || evt.status === 'auto_applied';

              return (
                <div key={idx} style={{
                  background: 'var(--body-bg)',
                  border: isBreaking ? '1px solid var(--danger-border)' : isNonBreaking ? '1px solid var(--success-border)' : '1px solid var(--border-color)',
                  borderLeft: isBreaking ? '4px solid var(--danger-color)' : isNonBreaking ? '4px solid var(--success-color)' : '4px solid var(--primary-color)',
                  borderRadius: '8px',
                  padding: '14px 18px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
                      <span style={{
                        fontSize: '0.7rem',
                        fontWeight: 700,
                        padding: '2px 8px',
                        borderRadius: '4px',
                        textTransform: 'uppercase',
                        background: isBreaking ? 'var(--danger-bg)' : 'var(--success-bg)',
                        color: isBreaking ? 'var(--danger-color)' : 'var(--success-color)'
                      }}>
                        {isBreaking ? 'Cần phê duyệt' : 'Tự động đồng bộ'}
                      </span>
                      <strong style={{ color: 'var(--text-main)', fontSize: '0.9rem' }}>{evt.table || evt.table_name || 'CDC Event'}</strong>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Pipeline: <code style={{ color: 'var(--primary-color)' }}>{evt.pipeline || 'default'}</code></span>
                    </div>

                    <div style={{ fontSize: '0.85rem', color: 'var(--text-main)' }}>
                      {evt.detail || evt.message || JSON.stringify(evt.changes || {})}
                    </div>
                  </div>

                  <div style={{ textAlign: 'right', fontSize: '0.75rem', color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: '4px' }}>
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

