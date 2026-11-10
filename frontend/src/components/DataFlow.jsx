import React, { useEffect, useRef, useState } from 'react';
import { ArrowRight, CheckCircle2, AlertTriangle, XCircle, PauseCircle, Loader2, ShieldCheck, Unplug } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';
import LiveEventStream from './LiveEventStream';

const POLL_MS = 1500;
const HISTORY = 80; // ~2 phút ở POLL_MS

const fmtInt = (n) => (n ?? 0).toLocaleString();
const fmtLag = (s) => (s == null ? '—' : s < 60 ? `${s.toFixed(1)}s` : `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`);

// Trạng thái loader -> màu + icon + nhãn (status luôn đi kèm icon và chữ, không chỉ màu).
const LOADER_STATE = {
  running: { color: 'var(--success-color)', Icon: CheckCircle2, key: 'flow_state_running' },
  hold: { color: 'var(--warning-color)', Icon: Loader2, key: 'flow_state_hold' },
  paused: { color: 'var(--warning-color)', Icon: PauseCircle, key: 'flow_state_paused' },
  failed: { color: 'var(--danger-color)', Icon: XCircle, key: 'flow_state_failed' },
  stopped: { color: 'var(--text-dim)', Icon: Unplug, key: 'flow_state_stopped' },
  starting: { color: 'var(--text-dim)', Icon: Loader2, key: 'flow_state_stopped' },
};

function StatePill({ state }) {
  const { t } = useLanguage();
  const s = LOADER_STATE[state] || LOADER_STATE.stopped;
  return (
    <span className="pill" style={{ color: s.color, borderColor: 'currentColor' }}>
      <s.Icon size={12} className={state === 'hold' ? 'spin' : undefined} /> {t(s.key)}
    </span>
  );
}

function Sparkline({ values, label }) {
  const [hover, setHover] = useState(null);
  const W = 160, H = 36, PAD = 3;
  if (values.length < 2) return <div style={{ height: H }} />;
  const max = Math.max(...values, 1);
  const x = (i) => PAD + (i / (values.length - 1)) * (W - PAD * 2);
  const y = (v) => H - PAD - (v / max) * (H - PAD * 2);
  const d = values.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('');
  const last = values.length - 1;
  const hi = hover ?? last;
  return (
    <div style={{ position: 'relative' }}>
      <svg
        width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={label}
        onMouseMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          setHover(Math.round(((e.clientX - r.left) / r.width) * last));
        }}
        onMouseLeave={() => setHover(null)}
        style={{ display: 'block', overflow: 'visible' }}
      >
        <path d={`${d}L${x(last)},${H - PAD}L${x(0)},${H - PAD}Z`} fill="var(--text-dim)" opacity="0.12" />
        <path d={d} fill="none" stroke="var(--text-dim)" strokeWidth="2" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
        {hover != null && <line x1={x(hi)} x2={x(hi)} y1={PAD} y2={H - PAD} stroke="var(--border-subtle)" vectorEffect="non-scaling-stroke" />}
        <circle cx={x(hi)} cy={y(values[hi])} r="3" fill="var(--text-main)" stroke="var(--card-bg)" strokeWidth="2" vectorEffect="non-scaling-stroke" />
      </svg>
      {hover != null && (
        <div style={{
          position: 'absolute', top: -26, left: `${(x(hi) / W) * 100}%`, transform: 'translateX(-50%)',
          background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: 4,
          padding: '1px 6px', fontSize: '0.72rem', whiteSpace: 'nowrap', boxShadow: 'var(--shadow)', pointerEvents: 'none',
        }}>
          {values[hi].toFixed(1)} rows/s · {Math.round((last - hi) * POLL_MS / 1000)}s ago
        </div>
      )}
    </div>
  );
}

function Tile({ label, value, sub, children, valueColor }) {
  return (
    <div className="metric-card" style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <div className="metric-label">{label}</div>
      <div className="metric-value" style={{ color: valueColor }}>{value}</div>
      {sub && <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>{sub}</div>}
      {children}
    </div>
  );
}

function Lane({ title, subtitle, icon, loader, rows, extra, note }) {
  return (
    <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius)', padding: '16px 18px', boxShadow: 'var(--shadow)', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div>
          <div style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>{icon}{title}</div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)', marginTop: 2 }}>{subtitle}</div>
        </div>
        <StatePill state={loader?.state || 'stopped'} />
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
        {rows.map(([k, v, color]) => (
          <div key={k}>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>{k}</div>
            <div style={{ fontSize: '1.05rem', fontWeight: 600, fontVariantNumeric: 'tabular-nums', color }}>{v}</div>
          </div>
        ))}
      </div>
      {extra}
      {note && <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', borderTop: '1px solid var(--border-color)', paddingTop: 10 }}>{note}</div>}
    </div>
  );
}

export default function DataFlow({ onReview }) {
  const { t } = useLanguage();
  const [flow, setFlow] = useState(null);
  const [history, setHistory] = useState([]);
  const prevPrices = useRef({});
  const [priceDir, setPriceDir] = useState({});

  useEffect(() => {
    let alive = true;
    const tick = () => fetch('/api/flow')
      .then(r => r.json())
      .then(data => {
        if (!alive) return;
        setFlow(data);
        const rate = data?.loaders?.loader?.rows_per_sec;
        if (rate != null) setHistory(h => [...h.slice(-(HISTORY - 1)), rate]);
        const dir = {};
        for (const p of data?.prices || []) {
          const before = prevPrices.current[p.symbol];
          dir[p.symbol] = before == null || Number(p.price) === before ? 0 : Number(p.price) > before ? 1 : -1;
          prevPrices.current[p.symbol] = Number(p.price);
        }
        setPriceDir(dir);
      })
      .catch(() => alive && setFlow({ available: false, error: 'API unreachable' }));
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => { alive = false; clearInterval(id); };
  }, []);

  if (!flow) return <div className="no-data">{t('loading')}</div>;
  if (!flow.available || !flow.reconcile) {
    return (
      <div className="no-data">
        <div style={{ fontWeight: 600, color: 'var(--text-main)', marginBottom: 6 }}>{t('flow_unavailable')}</div>
        <code style={{ fontSize: '0.8rem' }}>python -m demo.setup · python -m demo.ingestor · python -m demo.loader</code>
        {flow.error && <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: 8 }}>{flow.error}</div>}
      </div>
    );
  }

  const r = flow.reconcile;
  const loader = flow.loaders?.loader;
  const naiveLoader = flow.loaders?.['naive-loader'];
  const lost = r.lost_rows;
  const loaderNote = {
    hold: <>{t('flow_note_hold')} <code>{(loader?.held_columns || []).join(', ')}</code></>,
    paused: (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <span>{t('flow_note_paused')}</span>
        {onReview && (
          <button className="btn-primary" style={{ whiteSpace: 'nowrap' }} onClick={() => onReview(`${flow.pipeline}/trades`)}>
            {t('review_approve')}
          </button>
        )}
      </div>
    ),
  }[loader?.state];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: '1.3rem', letterSpacing: '-0.02em' }}>{t('flow_title')}</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', fontSize: '0.8rem', color: 'var(--text-dim)', marginTop: 4, fontFamily: 'var(--mono)' }}>
            {['Binance', 'Postgres', 'Debezium', 'Redpanda', 'ClickHouse'].map((n, i) => (
              <React.Fragment key={n}>{i > 0 && <ArrowRight size={11} />}{n}</React.Fragment>
            ))}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {flow.prices.map(p => (
            <span key={p.symbol} className="pill" style={{ fontFamily: 'var(--mono)', borderRadius: 4 }}>
              <span style={{ color: 'var(--text-dim)' }}>{p.symbol.replace('USDT', '')}</span>
              <span style={{ color: priceDir[p.symbol] > 0 ? 'var(--success-color)' : priceDir[p.symbol] < 0 ? 'var(--danger-color)' : 'var(--text-main)', transition: 'color .3s' }}>
                {Number(p.price).toLocaleString(undefined, { maximumFractionDigits: 5 })}
              </span>
            </span>
          ))}
        </div>
      </div>

      <div className="metrics-row" style={{ marginBottom: 0 }}>
        <Tile label={t('flow_source_rows')} value={fmtInt(r.source_total)} sub="Postgres · exchange.trades" />
        <Tile label={t('flow_warehouse_rows')} value={fmtInt(r.warehouse_total)} sub="ClickHouse · analytics.trades" />
        <Tile
          label={t('flow_lost_rows')}
          value={<span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            {lost === 0 ? <CheckCircle2 size={20} /> : <AlertTriangle size={20} />}{fmtInt(lost)}
          </span>}
          valueColor={lost === 0 ? 'var(--success-color)' : 'var(--danger-color)'}
          sub={`${t('flow_verified_upto')} ${new Date(r.mark).toLocaleTimeString()} · ${fmtInt(r.source_upto_mark)} = ${fmtInt(r.warehouse_upto_mark)}`}
        />
        <Tile label={t('flow_lag')} value={fmtLag(r.lag_seconds)} sub={t('flow_lag_sub')} />
        <Tile label={t('flow_throughput')} value={`${(loader?.rows_per_sec ?? 0).toFixed(1)}`} sub={t('flow_throughput_sub')}>
          <Sparkline values={history} label={t('flow_throughput')} />
        </Tile>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 12 }}>
        <Lane
          title={t('flow_lane_engine')}
          subtitle="analytics.trades · HOLD / PAUSE"
          icon={<ShieldCheck size={16} style={{ color: 'var(--text-dim)' }} />}
          loader={loader}
          rows={[
            [t('flow_warehouse_rows'), fmtInt(r.warehouse_total)],
            [t('flow_lost_rows'), fmtInt(lost), lost === 0 ? 'var(--success-color)' : 'var(--danger-color)'],
            [t('flow_lag'), fmtLag(r.lag_seconds)],
          ]}
          note={loaderNote}
        />
        <Lane
          title={t('flow_lane_naive')}
          subtitle="analytics_naive.trades · plain sink"
          icon={<Unplug size={16} style={{ color: 'var(--text-dim)' }} />}
          loader={naiveLoader}
          rows={[
            [t('flow_warehouse_rows'), fmtInt(r.naive?.warehouse_total)],
            [t('flow_missing_rows'), fmtInt(r.naive?.missing_rows), r.naive?.missing_rows > 1000 ? 'var(--danger-color)' : undefined],
            [t('flow_lag'), fmtLag(r.naive?.lag_seconds)],
          ]}
          note={naiveLoader?.state === 'failed'
            ? <><div style={{ color: 'var(--danger-color)', marginBottom: 4 }}>{t('flow_note_failed')}</div><code style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>{naiveLoader.error}</code></>
            : null}
        />
      </div>

      <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>{t('flow_footnote')}</div>

      <LiveEventStream onReviewTable={onReview} />
    </div>
  );
}
