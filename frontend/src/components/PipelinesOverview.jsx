import React, { useEffect, useRef, useState } from 'react';
import { ArrowRight, ChevronLeft, ChevronRight } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';
import LiveEventStream from './LiveEventStream';

// Trang tổng quan dùng chung cho MỌI pipeline: engine không biết gì về bên trong data plane,
// chỉ hiển thị cái các thành phần tự báo cáo qua POST /api/pipelines/{p}/components/{name}.
const POLL_MS = 2000;
const HISTORY = 60; // ~2 phút ở POLL_MS

const STATE_TONE = {
  running: 'success', ok: 'success',
  hold: 'warning', paused: 'warning', warn: 'warning', starting: 'warning',
  failed: 'danger', error: 'danger', missing: 'danger',
  stopped: 'muted', stale: 'muted',
};
const toneColor = (tone) => ({ success: 'var(--success-color)', warning: 'var(--warning-color)', danger: 'var(--danger-color)' }[tone] || 'var(--text-dim)');
const prettyKey = (k) => k.replace(/_/g, ' ').replace(/^./, (ch) => ch.toUpperCase());
const fmt = (v) => (typeof v === 'number' ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : v === null || v === undefined ? '—' : String(v));

function StatePill({ state }) {
  return (
    <span className="pill" style={{ color: toneColor(STATE_TONE[state]), borderColor: 'currentColor' }}>
      <span className="dot" />{state}
    </span>
  );
}

function Sparkline({ values }) {
  const W = 120, H = 28, PAD = 3;
  if (values.length < 2) return null;
  const max = Math.max(...values, 1);
  const x = (i) => PAD + (i / (values.length - 1)) * (W - PAD * 2);
  const y = (v) => H - PAD - (v / max) * (H - PAD * 2);
  const d = values.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('');
  const last = values.length - 1;
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`rows per second, last ${values.length} samples`}>
      <title>{`${values[last].toFixed(1)} rows/s now · max ${max.toFixed(1)}`}</title>
      <path d={`${d}L${x(last)},${H - PAD}L${x(0)},${H - PAD}Z`} fill="var(--text-dim)" opacity="0.12" />
      <path d={d} fill="none" stroke="var(--text-dim)" strokeWidth="2" strokeLinejoin="round" />
      <circle cx={x(last)} cy={y(values[last])} r="2.5" fill="var(--text-main)" />
    </svg>
  );
}

function ComponentTile({ comp, history }) {
  const { t } = useLanguage();
  const metrics = Object.entries(comp.metrics || {});
  return (
    <div style={{ border: '1px solid var(--border-color)', borderRadius: 'var(--radius)', padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8, background: 'var(--card-bg)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 600 }}>{comp.name}</div>
          {comp.role && <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>{comp.role}</div>}
        </div>
        <StatePill state={comp.state} />
      </div>
      {metrics.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(110px, 1fr))', gap: '6px 12px' }}>
          {metrics.map(([k, v]) => (
            <div key={k}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>{prettyKey(k)}</div>
              <div style={{ fontWeight: 600, fontVariantNumeric: 'tabular-nums', overflowWrap: 'anywhere' }}>{fmt(v)}</div>
            </div>
          ))}
        </div>
      )}
      {history?.length > 1 && <Sparkline values={history} />}
      {comp.message && <div style={{ fontSize: '0.78rem', color: toneColor(STATE_TONE[comp.state]) === 'var(--text-dim)' ? 'var(--text-muted)' : toneColor(STATE_TONE[comp.state]) }}>{comp.message}</div>}
      {comp.age_seconds != null && <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>{t('ov_reported_ago').replace('{s}', Math.round(comp.age_seconds))}</div>}
    </div>
  );
}

function pipelineHealth(p) {
  const tr = p.transport || {};
  if ([tr.status, tr.fallback?.status].some(s => s === 'disconnected' || s === 'error')) return ['danger', 'degraded'];
  if (p.tables.some(tb => tb.is_frozen)) return ['warning', 'pending_approval'];
  return ['success', 'healthy'];
}

// Mới nhất trước (theo lúc engine bắt đầu theo dõi). Chưa có baseline (vừa khai báo, lỗi kết nối, lỗi cấu hình) coi là mới nhất.
const newestFirst = (a, b) => (b.created_at || '9999').localeCompare(a.created_at || '9999');

function PipelineCard({ p, onReview, history }) {
  const { t } = useLanguage();
  const [tone, label] = pipelineHealth(p);
  const cdc = p.transport?.kind === 'broker';
  return (
    <section style={{ background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius)', padding: '16px 18px', boxShadow: 'var(--shadow)', display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span style={{ fontWeight: 600, fontSize: '1rem' }}>{p.name}</span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.78rem', color: 'var(--text-dim)', fontFamily: 'var(--mono)' }}>
            {p.source?.type?.toUpperCase()} <ArrowRight size={11} /> {p.target?.configured ? p.target.type.toUpperCase() : t('source_only')} · {cdc ? 'Kafka CDC' : 'Polling'}
          </span>
        </div>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          <span className="dot" style={{ color: toneColor(tone) }} />{t(label)}
        </span>
      </div>

      <div>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginBottom: 6 }}>{t('ov_tables')}</div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {p.tables.map(tb => (
            <span key={tb.name} className={`pill${tb.is_frozen ? ' warning' : ''}`} style={{ borderRadius: 6, padding: '4px 10px' }}>
              <span className="dot" style={{ color: tb.is_frozen ? undefined : 'var(--success-color)' }} />
              <span style={{ fontFamily: 'var(--mono)' }}>{tb.name}</span>
              <span style={{ color: 'var(--text-dim)' }}>v{tb.version}</span>
              {tb.is_frozen ? t('ov_gate_frozen') : t('ov_gate_open')}
              {tb.is_frozen && onReview && (
                <button className="btn-primary" style={{ padding: '2px 10px', fontSize: '0.75rem', marginLeft: 4 }} onClick={() => onReview(tb.registry_key)}>
                  {t('review_approve')}
                </button>
              )}
            </span>
          ))}
        </div>
      </div>

      <div>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginBottom: 6 }}>{t('ov_components')}</div>
        {(p.components || []).length === 0 ? (
          <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>
            {t('ov_no_components')} <code>POST /api/pipelines/{p.name}/components/&lt;name&gt;</code>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 10 }}>
            {p.components.map(comp => (
              <ComponentTile key={comp.name} comp={comp} history={history[`${p.name}/${comp.name}`]} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function BrokenCard({ p }) {
  const { t } = useLanguage();
  return (
    <section style={{ border: '1px solid var(--danger-border)', borderRadius: 'var(--radius)', padding: '14px 18px', background: 'var(--card-bg)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
        <span style={{ fontWeight: 600 }}>{p.name}</span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          <span className="dot" style={{ color: 'var(--danger-color)' }} />{t('config_error')}
        </span>
      </div>
      <code style={{ display: 'block', fontSize: '0.75rem', color: 'var(--danger-color)', marginTop: 6, whiteSpace: 'pre-wrap' }}>{p.config_error}</code>
    </section>
  );
}

export default function PipelinesOverview({ onReview }) {
  const { t } = useLanguage();
  const [pipelines, setPipelines] = useState(null);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null); // tên pipeline đang xem; null = luôn bám pipeline mới nhất
  const history = useRef({}); // "pipeline/component" -> rows_per_sec gần nhất

  useEffect(() => {
    let alive = true;
    const tick = () => fetch('/api/topology')
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(data => {
        if (!alive) return;
        for (const p of data) {
          for (const comp of p.components || []) {
            const v = comp.metrics?.rows_per_sec;
            if (typeof v !== 'number') continue;
            const key = `${p.name}/${comp.name}`;
            history.current[key] = [...(history.current[key] || []).slice(-(HISTORY - 1)), comp.state === 'stale' ? 0 : v];
          }
        }
        setPipelines(data);
        setError(null);
      })
      .catch(e => alive && setError(e.message));
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => { alive = false; clearInterval(id); };
  }, []);

  if (!pipelines) return <div className="no-data">{error ? `${t('toast_network_error')}: ${error}` : t('loading')}</div>;

  const monitored = pipelines.filter(p => !p.config_error);
  const broken = pipelines.filter(p => p.config_error);
  const pending = monitored.reduce((n, p) => n + p.tables.filter(tb => tb.is_frozen).length, 0);

  // Mỗi màn 1 pipeline. Pipeline đang xem bị xoá -> quay về mới nhất.
  const all = [...pipelines].sort(newestFirst);
  const idx = Math.max(0, all.findIndex(p => p.name === selected));
  const current = all[idx];
  const go = (i) => setSelected(i === 0 ? null : all[i].name); // về đầu danh sách = lại bám pipeline mới nhất

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: '1.3rem', letterSpacing: '-0.02em' }}>{t('overview')}</h1>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-dim)', marginTop: 4 }}>
            {t('ov_summary').replace('{n}', monitored.length).replace('{p}', pending).replace('{e}', broken.length)}
          </div>
        </div>
        {all.length > 1 && (
          <nav aria-label={t('ov_pager')} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button className="icon-btn" onClick={() => go(idx - 1)} disabled={idx === 0} aria-label={t('ov_newer')} title={t('ov_newer')}>
              <ChevronLeft size={14} />
            </button>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>{idx + 1} / {all.length}</span>
            <button className="icon-btn" onClick={() => go(idx + 1)} disabled={idx === all.length - 1} aria-label={t('ov_older')} title={t('ov_older')}>
              <ChevronRight size={14} />
            </button>
          </nav>
        )}
      </div>

      {all.length === 0 && <div className="no-data">{t('ov_empty')}</div>}

      {current && (current.config_error
        ? <BrokenCard p={current} />
        : <PipelineCard p={current} onReview={onReview} history={history.current} />)}

      <LiveEventStream onReviewTable={onReview} />
    </div>
  );
}
