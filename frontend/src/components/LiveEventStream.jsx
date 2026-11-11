import React, { useState, useEffect, useCallback } from 'react';
import { Zap, Activity, Clock, ChevronLeft, ChevronRight, X, Trash2 } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';
import { useToast } from './NotificationToast';

const PAGE_SIZE = 3; // sự kiện cũ hơn xem bằng nút ‹ ›

export default function LiveEventStream({ onReviewTable }) {
  const { t } = useLanguage();
  const { addToast } = useToast();
  const [events, setEvents] = useState([]);
  const [isLive, setIsLive] = useState(true);
  const [page, setPage] = useState(0);

  const load = useCallback(() => {
    fetch('/api/events')
      .then(res => res.json())
      .then(data => setEvents(data))
      .catch(err => console.error("Error fetching live events", err));
  }, []);

  useEffect(() => {
    if (!isLive) return undefined;
    load();
    const interval = setInterval(load, 2000);
    return () => clearInterval(interval);
  }, [isLive, load]);

  // Lịch sử chỉ là nhật ký: xoá không đổi freeze, baseline hay bảng chờ duyệt.
  const failed = async (res) => {
    const d = await res.json().catch(() => ({}));
    addToast(`${t('toast_action_failed')}: ${typeof d.detail === 'string' ? d.detail : res.status}`, "error");
  };

  const removeEvent = async (id) => {
    const res = await fetch(`/api/events/${id}`, { method: 'DELETE' });
    if (!res.ok) return failed(res);
    setEvents(evts => evts.filter(e => e.id !== id));
  };

  const clearAll = async () => {
    if (!window.confirm(t('confirm_clear_events'))) return;
    const res = await fetch('/api/events', { method: 'DELETE' });
    if (!res.ok) return failed(res);
    setEvents([]);
    setPage(0);
  };

  const pages = Math.max(1, Math.ceil(events.length / PAGE_SIZE));
  const current = Math.min(page, pages - 1); // xoá bớt làm số trang giảm: không đứng ở trang trống
  const start = current * PAGE_SIZE;

  return (
    <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '10px', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', flexWrap: 'wrap', background: 'var(--card-bg)' }}>
        <div>
          <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Zap style={{ color: 'var(--text-dim)' }} size={16} /> {t('live_stream_title')}
          </h3>
          <p style={{ margin: '4px 0 0 0', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            {t('live_stream_sub')}
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: isLive ? 'var(--success-color)' : 'var(--text-dim)' }}></span>
            {isLive ? t('streaming_active') : t('paused')}
          </span>
          <button
            className="btn-outline"
            style={{ padding: '6px 14px', fontSize: '0.8rem' }}
            onClick={() => setIsLive(!isLive)}
          >
            {isLive ? t('pause_stream') : t('resume_stream')}
          </button>
          <button
            className="btn-outline"
            style={{ padding: '6px 14px', fontSize: '0.8rem', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
            onClick={clearAll}
            disabled={events.length === 0}
          >
            <Trash2 size={13} /> {t('clear_all_events')}
          </button>
        </div>
      </div>

      {/* Events Stream List */}
      <div style={{ padding: '20px' }}>
        {events.length === 0 ? (
          <div className="no-data" style={{ padding: '28px', minHeight: '180px' }}>
            <Activity size={22} style={{ marginBottom: '10px', color: 'var(--text-dim)' }} />
            <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-main)', marginBottom: '4px' }}>
              {t('listening_events')}
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', maxWidth: '420px' }}>
              {t('listening_desc')}
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {events.slice(start, start + PAGE_SIZE).map((evt, i) => {
              const idx = start + i; // vị trí trong toàn bộ lịch sử (mới nhất = 0)
              const isBreaking = evt.status === 'breaking_detected';
              // Nhãn theo trạng thái thật của sự kiện, không chỉ breaking / non-breaking.
              const badge = {
                breaking_detected: ['requires_approval', 'warning'],
                approved: ['evt_approved', 'success'],
                rejected: ['evt_rejected', 'muted'],
                resolved_at_source: ['evt_resolved', 'success'],
                sink_paused: ['evt_sink_paused', 'warning'],
                sink_resumed: ['evt_sink_resumed', 'success'],
                sink_restarted: ['evt_sink_resumed', 'success'],
                sink_control_failed: ['evt_sink_failed', 'danger'],
              }[evt.status] || ['auto_synced_badge', 'success'];
              const tone = { warning: 'var(--warning-color)', success: 'var(--success-color)', muted: 'var(--text-dim)', danger: 'var(--danger-color)' }[badge[1]];
              const toneBg = { warning: 'var(--warning-bg)', success: 'var(--success-bg)', muted: 'var(--card-hover)', danger: 'var(--danger-bg)' }[badge[1]];

              return (
                <div key={evt.id ?? idx} style={{
                  background: 'var(--body-bg)',
                  border: '1px solid var(--border-color)',
                  borderLeft: `3px solid ${tone}`,
                  borderRadius: '8px',
                  padding: '14px 18px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: '12px'
                }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
                      <span style={{
                        fontSize: '0.7rem',
                        fontWeight: 700,
                        padding: '2px 8px',
                        borderRadius: '4px',
                        textTransform: 'none',
                        background: toneBg,
                        color: tone
                      }}>
                        {t(badge[0])}
                      </span>
                      <strong style={{ color: 'var(--text-main)', fontSize: '0.9rem' }}>{evt.table || evt.table_name || 'CDC Event'}</strong>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}><code style={{ color: 'var(--text-dim)' }}>{evt.pipeline || 'default'}</code></span>
                    </div>

                    <div style={{ fontSize: '0.85rem', color: 'var(--text-main)' }}>
                      {evt.detail || evt.message || JSON.stringify(evt.changes || {})}
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                    {isBreaking && onReviewTable && !events.slice(0, idx).some(e =>
                      // Sự kiện mới hơn (đứng trước trong danh sách) đã kết thúc yêu cầu duyệt này.
                      e.pipeline === evt.pipeline && e.table === evt.table &&
                      ['approved', 'rejected', 'resolved_at_source'].includes(e.status)) && (
                      <button
                        className="btn-outline"
                        style={{ padding: '5px 12px', fontSize: '0.78rem', fontWeight: 500 }}
                        onClick={() => onReviewTable(`${evt.pipeline}/${evt.table || evt.table_name}`)}
                      >
                        {t('review_approve')}
                      </button>
                    )}
                    <div style={{ textAlign: 'right', fontSize: '0.75rem', color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Clock size={12} /> {evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : 'Just now'}
                    </div>
                    {evt.id != null && (
                      <button
                        className="icon-btn"
                        onClick={() => removeEvent(evt.id)}
                        aria-label={t('delete_event')}
                        title={t('delete_event')}
                      >
                        <X size={14} />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}

            {pages > 1 && (
              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '10px', marginTop: '4px' }}>
                <button className="icon-btn" onClick={() => setPage(current - 1)} disabled={current === 0}
                        aria-label={t('newer_events')} title={t('newer_events')}>
                  <ChevronLeft size={14} />
                </button>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', minWidth: '48px', textAlign: 'center' }}>
                  {current + 1} / {pages}
                </span>
                <button className="icon-btn" onClick={() => setPage(current + 1)} disabled={current === pages - 1}
                        aria-label={t('older_events')} title={t('older_events')}>
                  <ChevronRight size={14} />
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
