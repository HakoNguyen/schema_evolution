import React, { useState, useEffect } from 'react';
import { CheckCircle2, AlertTriangle } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';

const POLL_MS = 3000;

// Thứ tự và màu cố định trên mọi biểu đồ: một kết quả luôn mang cùng một màu.
const OUTCOMES = [
  { key: 'auto', color: 'var(--series-1)' },
  { key: 'blocked', color: 'var(--series-2)' },
  { key: 'reviewed', color: 'var(--series-3)' },
  { key: 'resolved', color: 'var(--series-4)' },
];

const outcomeOf = e => (
  e.status === 'changes_applied' ? 'auto'
    : e.status === 'breaking_detected' ? 'blocked'
      : e.status === 'resolved_at_source' ? 'resolved'
        : e.severity === 'review' ? 'reviewed' : null
);

// Sự kiện ghi trước khi có trường `changes`: đọc lại từ chuỗi "Auto-synced: add_column x | Pending approval: ...".
const changesOf = e => (e.changes?.length ? e.changes : [...(e.detail || '').matchAll(/(Auto-synced|Pending approval): ([^|]+)/g)]
  .flatMap(([, kind, list]) => list.split(',').map(s => ({ type: s.trim().split(' ')[0], applied: kind === 'Auto-synced' }))));

const STEPS = [10, 30, 60, 300, 900, 1800, 3600, 10800, 21600, 43200, 86400].map(s => s * 1000);
const MAX_BUCKETS = 30;

function bucketize(events, now) {
  const times = events.map(e => Date.parse(e.timestamp));
  const t0 = Math.min(...times);
  const step = STEPS.find(s => (now - t0) / s <= MAX_BUCKETS) ?? STEPS.at(-1);
  const start = Math.max(Math.floor(t0 / step) * step, now - step * (MAX_BUCKETS - 1));
  const n = Math.floor((now - start) / step) + 1;
  const buckets = Array.from({ length: n }, (_, i) => ({ t: start + i * step, auto: 0, blocked: 0, reviewed: 0, resolved: 0 }));
  events.forEach((e, i) => {
    const idx = Math.floor((times[i] - start) / step);
    if (idx >= 0 && idx < n) buckets[idx][outcomeOf(e)] += 1;
  });
  return { buckets, step };
}

const pad = v => String(v).padStart(2, '0');
const fmtTick = (t, step, multiDay) => {
  const d = new Date(t);
  const day = `${pad(d.getDate())}/${pad(d.getMonth() + 1)}`;
  if (step >= 86400000) return day;
  const clock = step < 60000 ? `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}` : `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  return multiDay ? `${day} ${clock}` : clock;  // "13:00" hai ngày khác nhau sẽ đọc nhầm nếu thiếu ngày
};

function Kpi({ label, value, sub, tone, icon }) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value" style={{ display: 'flex', alignItems: 'center', gap: '8px', color: tone ? `var(--${tone}-color)` : undefined }}>
        {icon}{value}
      </div>
      <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '4px' }}>{sub}</div>
    </div>
  );
}

function Legend({ items, t }) {
  return (
    <div className="dash-legend">
      {items.map(o => <span key={o.key}><i style={{ background: o.color }} />{t(`out_${o.key}`)}{o.total != null && ` · ${o.total}`}</span>)}
    </div>
  );
}

function TimelineChart({ events, t, now }) {
  const [hover, setHover] = useState(null);
  const { buckets, step } = bucketize(events, now);
  const W = 640, H = 220, L = 34, R = 8, T = 10, B = 26;
  const plotW = W - L - R, plotH = H - T - B;
  const peak = Math.max(1, ...buckets.map(b => b.auto + b.blocked + b.reviewed + b.resolved));
  const yStep = Math.max(1, Math.ceil(peak / 4));
  const yMax = yStep * Math.ceil(peak / yStep);
  const ticks = Array.from({ length: yMax / yStep + 1 }, (_, i) => i * yStep);
  const slot = plotW / buckets.length;
  const barW = Math.max(3, Math.min(28, slot * 0.68));
  const y = v => T + plotH - (v / yMax) * plotH;
  const multiDay = new Date(buckets[0].t).toDateString() !== new Date(now).toDateString();
  const labelEvery = Math.ceil(buckets.length / (multiDay ? 5 : 6));
  const totals = OUTCOMES.map(o => ({ ...o, total: buckets.reduce((s, b) => s + b[o.key], 0) }));

  return (
    <>
      <Legend items={totals} t={t} />
      <div style={{ position: 'relative' }} onMouseLeave={() => setHover(null)}>
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={t('chart_timeline')} style={{ display: 'block' }}>
          {ticks.map(v => (
            <g key={v}>
              <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke="var(--border-subtle)" strokeWidth="1" />
              <text x={L - 8} y={y(v) + 4} textAnchor="end" fontSize="11" fill="var(--text-dim)">{v}</text>
            </g>
          ))}
          {buckets.map((b, i) => {
            const cx = L + slot * i + slot / 2;
            let acc = 0;
            return (
              <g key={b.t}>
                {OUTCOMES.map(o => {
                  if (!b[o.key]) return null;
                  const y0 = y(acc), y1 = y(acc + b[o.key]);
                  acc += b[o.key];
                  // 2px khe màu nền giữa các đoạn chồng nhau
                  return <rect key={o.key} x={cx - barW / 2} y={y1} width={barW} height={Math.max(1, y0 - y1 - 2)} rx="2" fill={o.color} />;
                })}
                {i % labelEvery === 0 && (
                  <text x={cx} y={H - 8} textAnchor="middle" fontSize="11" fill="var(--text-dim)">{fmtTick(b.t, step, multiDay)}</text>
                )}
                <rect x={L + slot * i} y={T} width={slot} height={plotH} fill="transparent"
                  onMouseEnter={() => setHover({ i, x: cx, y: y(acc) })} />
              </g>
            );
          })}
          {hover && <line x1={hover.x} x2={hover.x} y1={T} y2={T + plotH} stroke="var(--text-dim)" strokeDasharray="3 3" pointerEvents="none" />}
        </svg>
        {hover && (
          <div className="dash-tip" style={{ left: `${(hover.x / W) * 100}%`, top: `${(Math.max(hover.y, T + 30) / H) * 100}%` }}>
            <div style={{ fontWeight: 600, marginBottom: '4px' }}>{fmtTick(buckets[hover.i].t, Math.min(step, 59000), multiDay)}</div>
            {OUTCOMES.map(o => (
              <div key={o.key}><i style={{ background: o.color }} />{t(`out_${o.key}`)}: <b>{buckets[hover.i][o.key]}</b></div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}

function ChangeTypesChart({ events, t }) {
  const [hover, setHover] = useState(null);
  const counts = {};
  events.forEach(e => changesOf(e).forEach(c => {
    counts[c.type] = counts[c.type] || { auto: 0, blocked: 0 };
    counts[c.type][c.applied ? 'auto' : 'blocked'] += 1;
  }));
  const rows = Object.entries(counts).map(([type, c]) => ({ type, ...c, total: c.auto + c.blocked }))
    .sort((a, b) => b.total - a.total).slice(0, 8);
  if (!rows.length) return <div className="no-data">{t('no_events')}</div>;
  const max = rows[0].total;

  return (
    <>
      <Legend items={OUTCOMES.slice(0, 2)} t={t} />
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }} onMouseLeave={() => setHover(null)}>
        {rows.map(r => (
          <div key={r.type} onMouseEnter={() => setHover(r.type)}
            style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 9.5em) 1fr 2em', alignItems: 'center', gap: '8px', fontSize: '0.78rem', position: 'relative' }}>
            <span style={{ color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.type}>
              {t(`ct_${r.type}`) === `ct_${r.type}` ? r.type : t(`ct_${r.type}`)}
            </span>
            <div style={{ display: 'flex', gap: '2px', height: '14px' }}>
              {r.auto > 0 && <div style={{ width: `${(r.auto / max) * 100}%`, background: 'var(--series-1)', borderRadius: '3px' }} />}
              {r.blocked > 0 && <div style={{ width: `${(r.blocked / max) * 100}%`, background: 'var(--series-2)', borderRadius: '3px' }} />}
            </div>
            <span style={{ color: 'var(--text-main)', fontWeight: 600, textAlign: 'right' }}>{r.total}</span>
            {hover === r.type && (
              <div className="dash-tip" style={{ position: 'absolute', left: '60%', top: 0, transform: 'translate(-50%, -100%)' }}>
                <div style={{ fontWeight: 600, marginBottom: '4px' }}>{r.type}</div>
                <div><i style={{ background: 'var(--series-1)' }} />{t('out_auto')}: <b>{r.auto}</b></div>
                <div><i style={{ background: 'var(--series-2)' }} />{t('out_blocked')}: <b>{r.blocked}</b></div>
              </div>
            )}
          </div>
        ))}
      </div>
    </>
  );
}

export default function Dashboard({ onOpenTable }) {
  const { t, lang } = useLanguage();
  const [tables, setTables] = useState([]);
  const [events, setEvents] = useState([]);
  const [components, setComponents] = useState({});
  const [now, setNow] = useState(Date.now());
  const [pipeline, setPipeline] = useState('');  // '' = tổng mọi pipeline

  useEffect(() => {
    let live = true;
    const load = async () => {
      try {
        const [tb, ev] = await Promise.all([
          fetch('/api/tables').then(r => r.json()),
          fetch('/api/events?limit=2000').then(r => r.json()),
        ]);
        const pipes = [...new Set(tb.map(x => x.pair_name))];
        const comps = await Promise.all(pipes.map(p => fetch(`/api/pipelines/${p}/components`)
          .then(r => (r.ok ? r.json() : [])).catch(() => [])));
        if (!live) return;
        setTables(tb);
        setEvents(Array.isArray(ev) ? ev : []);
        setComponents(Object.fromEntries(pipes.map((p, i) => [p, comps[i]])));
        setNow(Date.now());
      } catch { /* backend tạm tắt: giữ số liệu lần trước */ }
    };
    load();
    const id = setInterval(load, POLL_MS);
    return () => { live = false; clearInterval(id); };
  }, []);

  const nf = new Intl.NumberFormat(lang === 'vi' ? 'vi-VN' : 'en-US');
  const rel = new Intl.RelativeTimeFormat(lang === 'vi' ? 'vi' : 'en', { numeric: 'auto' });
  const ago = ts => {
    const s = Math.round((Date.parse(ts) - now) / 1000);
    if (Math.abs(s) < 60) return rel.format(s, 'second');
    if (Math.abs(s) < 3600) return rel.format(Math.round(s / 60), 'minute');
    if (Math.abs(s) < 86400) return rel.format(Math.round(s / 3600), 'hour');
    return rel.format(Math.round(s / 86400), 'day');
  };

  const pipelineNames = [...new Set(tables.map(x => x.pair_name))].sort();
  // Pipeline đã chọn bị xoá khỏi config -> quay về tổng thay vì hiện trang trống.
  const only = pipelineNames.includes(pipeline) ? pipeline : '';
  const vTables = only ? tables.filter(x => x.pair_name === only) : tables;
  const vEvents = only ? events.filter(e => e.pipeline === only) : events;
  const vComponents = only ? [components[only] || []] : Object.values(components);

  const scored = vEvents.filter(e => outcomeOf(e));
  const allChanges = vEvents.flatMap(changesOf);
  const frozen = vTables.filter(x => x.is_frozen);
  const pipelines = new Set(vTables.map(x => x.pair_name)).size;
  const reconcilers = vComponents.flat().filter(c => c?.metrics && 'lost_rows' in c.metrics);
  const lost = reconcilers.reduce((s, c) => s + (c.metrics.lost_rows || 0), 0);
  const checkedRows = reconcilers.reduce((s, c) => s + (c.metrics.warehouse_rows || 0), 0);
  const lastEventOf = key => vEvents.find(e => `${e.pipeline}/${e.table}` === key);
  const route = only && vTables[0]?.mode;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: '12px', flexWrap: 'wrap', marginBottom: '16px' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 600 }}>{t('dash_title')}</h2>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginTop: '4px' }}>
            {only ? `${only}${route ? ` · ${route}` : ''}` : t('dash_all')} · {t('dash_refresh')}
          </div>
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          {t('dash_filter_label')}
          <select
            value={only}
            onChange={e => setPipeline(e.target.value)}
            style={{ padding: '6px 10px', minWidth: '200px', background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--text-main)', fontSize: '0.85rem' }}
          >
            <option value="">{t('dash_all')}</option>
            {pipelineNames.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </label>
      </div>

      <div className="metrics-row">
        <Kpi label={t('kpi_tables')} value={nf.format(vTables.length)} sub={t('kpi_tables_sub').replace('{n}', pipelines)} />
        <Kpi
          label={t('kpi_frozen')}
          value={nf.format(frozen.length)}
          tone={frozen.length ? 'danger' : 'success'}
          icon={frozen.length ? <AlertTriangle size={20} /> : <CheckCircle2 size={20} />}
          sub={frozen.length ? frozen.map(x => x.registry_key).join(', ') : t('kpi_frozen_ok')}
        />
        <Kpi label={t('kpi_auto')} value={nf.format(allChanges.filter(c => c.applied).length)} sub={t('kpi_auto_sub')} />
        <Kpi label={t('kpi_blocked')} value={nf.format(allChanges.filter(c => !c.applied).length)} sub={t('kpi_blocked_sub')} />
        <Kpi
          label={t('kpi_lost')}
          value={reconcilers.length ? nf.format(lost) : '—'}
          tone={reconcilers.length ? (lost ? 'danger' : 'success') : undefined}
          sub={reconcilers.length ? t('kpi_lost_sub').replace('{n}', nf.format(checkedRows)) : t('kpi_lost_none')}
        />
      </div>

      <div className="dash-grid">
        <div className="dash-card">
          <h3>{t('chart_timeline')}</h3>
          <div className="dash-sub">{t('chart_timeline_sub')}</div>
          {scored.length ? <TimelineChart events={scored} t={t} now={now} /> : <div className="no-data">{t('no_events')}</div>}
        </div>
        <div className="dash-card">
          <h3>{t('chart_types')}</h3>
          <div className="dash-sub">{t('chart_types_sub')}</div>
          <ChangeTypesChart events={vEvents} t={t} />
        </div>
      </div>

      <div className="dash-grid">
        <div className="dash-card">
          <h3>{t('table_status')}</h3>
          <div className="dash-sub">{t('table_status_sub')}</div>
          <div className="schema-table-wrapper">
            <table className="schema-table">
              <thead>
                <tr>
                  <th>{t('col_table')}</th>
                  <th>{t('col_route')}</th>
                  <th>{t('col_version')}</th>
                  <th>{t('col_state')}</th>
                  <th>{t('col_last_change')}</th>
                </tr>
              </thead>
              <tbody>
                {vTables.map(x => {
                  const last = lastEventOf(x.registry_key);
                  return (
                    <tr key={x.registry_key} className="list-row-clickable" onClick={() => onOpenTable(x.registry_key)}>
                      <td>
                        <div style={{ fontWeight: 600 }}>{x.table_name}</div>
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>{x.pair_name}</div>
                      </td>
                      <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{x.mode}</td>
                      <td><code>v{x.version}</code></td>
                      <td>
                        {x.is_frozen
                          ? <span className="pill danger"><AlertTriangle size={12} />{t('state_frozen')}</span>
                          : <span className="pill success"><CheckCircle2 size={12} />{t('state_open')}</span>}
                      </td>
                      <td style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>{last ? ago(last.timestamp) : '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
        <div className="dash-card">
          <h3>{t('recent_activity')}</h3>
          <div className="dash-sub">{t('recent_activity_sub')}</div>
          {scored.length === 0 && <div className="no-data">{t('no_events')}</div>}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {scored.slice(0, 7).map(e => {
              const o = OUTCOMES.find(x => x.key === outcomeOf(e));
              return (
                <div key={e.id} style={{ display: 'grid', gridTemplateColumns: '10px 1fr auto', gap: '8px', alignItems: 'start', fontSize: '0.78rem' }}>
                  <i style={{ width: '10px', height: '10px', borderRadius: '3px', background: o.color, marginTop: '4px' }} />
                  <div style={{ minWidth: 0 }}>
                    <div><b>{e.table}</b> <span style={{ color: 'var(--text-dim)' }}>· {e.pipeline}</span></div>
                    <div style={{ color: 'var(--text-muted)' }}>
                      {t(`out_${o.key}`)}
                      {changesOf(e).length > 0 && `: ${changesOf(e).map(c => c.type).join(', ')}`}
                    </div>
                  </div>
                  <span style={{ color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>{ago(e.timestamp)}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
