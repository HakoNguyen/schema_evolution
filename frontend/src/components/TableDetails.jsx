import React, { useState, useEffect } from 'react';
import { Key, History } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';

const typeStr = c => c.precision != null
  ? `${c.data_type}(${c.precision}${c.scale != null ? `,${c.scale}` : ''})`
  : c.max_length ? `${c.data_type}(${c.max_length})` : c.data_type;
const nullStr = c => (c.nullable ? 'NULL' : 'NOT NULL');
const fkKey = fk => `${fk.column_name} → ${fk.ref_table}.${fk.ref_column}`;
const TONE = { added: 'success', changed: 'warning', renamed: 'warning', dropped: 'danger' };

// So một phiên bản với phiên bản liền trước. renames = ánh xạ cũ -> mới đã duyệt (Gate API): không có nó,
// đổi tên chỉ hiện như "xoá 1 cột + thêm 1 cột".
function diffSchemas(prev, cur, renames) {
  const prevCols = Object.fromEntries(prev.columns.map(c => [c.name, c]));
  const curNames = new Set(cur.columns.map(c => c.name));
  const renamedFrom = Object.fromEntries(Object.entries(renames)
    .filter(([o, n]) => prevCols[o] && !curNames.has(o) && curNames.has(n) && !prevCols[n])
    .map(([o, n]) => [n, o]));
  const rows = cur.columns.map(col => {
    const from = renamedFrom[col.name];
    const old = prevCols[col.name] || prevCols[from];
    if (!old) return { col, status: 'added' };
    if (from) return { col, old, from, status: 'renamed' };
    const changed = typeStr(old) !== typeStr(col) || old.nullable !== col.nullable;
    return { col, old, status: changed ? 'changed' : null };
  });
  const renamedAway = new Set(Object.values(renamedFrom));
  const prevFks = new Set((prev.foreign_keys || []).map(fkKey));
  const curFks = new Set((cur.foreign_keys || []).map(fkKey));
  return {
    rows,
    dropped: prev.columns.filter(c => !curNames.has(c.name) && !renamedAway.has(c.name)),
    pkChanged: (prev.primary_key || []).join() !== (cur.primary_key || []).join(),
    fkAdded: [...curFks].filter(k => !prevFks.has(k)),
    fkRemoved: [...prevFks].filter(k => !curFks.has(k)),
  };
}

const Was = ({ children }) => (
  <><s style={{ color: 'var(--text-dim)' }}>{children}</s>{' → '}</>
);

export default function TableDetails({ registryKey, details }) {
  const { t } = useLanguage();
  const [versions, setVersions] = useState([]);
  const [selectedVersion, setSelectedVersion] = useState(null);
  const [versionDetails, setVersionDetails] = useState(null);
  const [prevSchema, setPrevSchema] = useState(null);
  const [renames, setRenames] = useState({});

  useEffect(() => {
    if (!registryKey) return;
    fetch(`/api/tables/${registryKey}/versions`)
      .then(res => res.json())
      .then(data => {
        setVersions(data);
        setSelectedVersion(null);
      })
      .catch(err => console.error("Error fetching versions", err));
    fetch(`/api/gate/${registryKey}`)
      .then(res => (res.ok ? res.json() : {}))
      .then(data => setRenames(data.column_renames || {}))
      .catch(() => setRenames({}));
    // Theo số version, không theo object details: details được tải lại mỗi 2 giây, nếu theo object thì
    // lựa chọn version cũ bị xoá liên tục.
  }, [registryKey, details?.version]);

  useEffect(() => {
    setVersionDetails(null);  // quay về "hiện tại" phải bỏ schema cũ đang hiển thị
    if (!registryKey || !selectedVersion) return;
    let live = true;
    fetch(`/api/tables/${registryKey}/versions/${selectedVersion}`)
      .then(res => res.json())
      .then(data => { if (live && data.exists) setVersionDetails(data); });
    return () => { live = false; };
  }, [registryKey, selectedVersion]);

  const shown = selectedVersion ?? details?.version;

  useEffect(() => {
    setPrevSchema(null);
    if (!registryKey || !shown || shown <= 1) return;
    let live = true;  // bấm nhanh qua nhiều phiên bản: bỏ kết quả về muộn của lần bấm trước
    fetch(`/api/tables/${registryKey}/versions/${shown - 1}`)
      .then(res => res.json())
      .then(data => { if (live) setPrevSchema(data.exists ? data.schema : null); })
      .catch(() => {});
    return () => { live = false; };
  }, [registryKey, shown]);

  if (!details || !details.exists) {
    return <div className="no-data">{t('no_schema_data')}</div>;
  }

  const displaySchema = selectedVersion && versionDetails ? versionDetails.schema : details.schema;
  const diff = shown > 1 && prevSchema ? diffSchemas(prevSchema, displaySchema, renames) : null;
  const rows = diff ? diff.rows : displaySchema.columns.map(col => ({ col, status: null }));
  const count = s => (diff ? diff.rows.filter(r => r.status === s).length : 0);
  const shownTs = versions.find(v => v.version === shown)?.timestamp;

  const summary = diff && [
    count('added') > 0 && ['success', `+${count('added')} ${t('sum_added')}`],
    count('changed') > 0 && ['warning', `${count('changed')} ${t('sum_changed')}`],
    count('renamed') > 0 && ['warning', `${count('renamed')} ${t('sum_renamed')}`],
    diff.dropped.length > 0 && ['danger', `−${diff.dropped.length} ${t('sum_dropped')}`],
    diff.pkChanged && ['warning', t('sum_pk')],
    diff.fkAdded.length > 0 && ['warning', `+${diff.fkAdded.length} ${t('sum_fk_added')}`],
    diff.fkRemoved.length > 0 && ['warning', `−${diff.fkRemoved.length} ${t('sum_fk_removed')}`],
  ].filter(Boolean);

  const rowStyle = status => status
    ? { background: `var(--${TONE[status]}-bg)`, boxShadow: `inset 3px 0 0 var(--${TONE[status]}-color)` }
    : undefined;
  const badge = status => status && (
    <span className={`pill ${TONE[status]}`} style={{ fontSize: '0.68rem', padding: '1px 6px' }}>{t(`badge_${status}`)}</span>
  );

  return (
    <div style={{ color: 'var(--text-main)' }}>
      <h3 style={{ margin: '0 0 12px 0', fontSize: '0.95rem', fontWeight: 600 }}>
        {t('schema_structure')}{' '}
        <span style={{ color: 'var(--text-dim)', fontWeight: 400 }}>
          {selectedVersion ? `v${selectedVersion}` : `${t('current_version')} · v${details.version}`}
        </span>
      </h3>

      {versions.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap', marginBottom: '10px' }}>
          <History size={14} style={{ color: 'var(--text-dim)' }} />
          <span style={{ fontSize: '0.78rem', color: 'var(--text-dim)', marginRight: '4px' }}>{t('version_history')}</span>
          {[...versions].reverse().map((v, i) => {
            const active = v.version === shown;
            return (
              <React.Fragment key={v.version}>
                {i > 0 && <span aria-hidden="true" style={{ width: '10px', height: '1px', background: 'var(--border-color)' }} />}
                <button
                  type="button"
                  className="btn-outline"
                  aria-pressed={active}
                  title={v.timestamp ? new Date(v.timestamp).toLocaleString() : ''}
                  onClick={() => setSelectedVersion(v.version === details.version ? null : v.version)}
                  style={{
                    padding: '3px 10px', fontSize: '0.78rem', fontFamily: 'var(--mono)',
                    fontWeight: active ? 700 : 400,
                    borderColor: active ? 'var(--text-main)' : undefined,
                    color: active ? 'var(--text-main)' : 'var(--text-muted)',
                  }}
                >
                  v{v.version}
                </button>
              </React.Fragment>
            );
          })}
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap', marginBottom: '12px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
        {shown === 1 && <span>{t('diff_baseline')}</span>}
        {summary && (
          <>
            <span>{t('diff_vs')} v{shown - 1}:</span>
            {summary.length === 0 && <span style={{ color: 'var(--text-dim)' }}>{t('diff_none')}</span>}
            {summary.map(([tone, text]) => <span key={text} className={`pill ${tone}`} style={{ fontSize: '0.72rem' }}>{text}</span>)}
          </>
        )}
        {shownTs && <span style={{ color: 'var(--text-dim)', marginLeft: 'auto' }}>{new Date(shownTs).toLocaleString()}</span>}
      </div>

      <div className="schema-table-wrapper" style={{ marginBottom: '12px' }}>
        <table className="schema-table fixed">
          <colgroup>
            <col style={{ width: '38%' }} />
            <col style={{ width: '26%' }} />
            <col style={{ width: '16%' }} />
            <col style={{ width: '20%' }} />
          </colgroup>
          <thead>
            <tr>
              <th>{t('col_column_name')}</th>
              <th>{t('col_data_type')}</th>
              <th>{t('col_nullable')}</th>
              <th>{t('col_default_val')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ col, old, from, status }) => (
              <tr key={col.name} style={rowStyle(status)}>
                <td>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontWeight: 500, flexWrap: 'wrap' }}>
                    {from && <Was>{from}</Was>}
                    {col.name}
                    {displaySchema.primary_key?.includes(col.name) && <Key size={12} style={{ color: 'var(--text-dim)' }} aria-label="primary key" />}
                    {badge(status)}
                  </span>
                </td>
                <td>
                  <code style={{ color: 'var(--text-muted)' }}>
                    {old && typeStr(old) !== typeStr(col) && <Was>{typeStr(old)}</Was>}
                    {typeStr(col)}
                  </code>
                </td>
                <td style={{ color: col.nullable ? 'var(--text-dim)' : 'var(--text-muted)', fontSize: '0.8rem' }}>
                  {old && old.nullable !== col.nullable && <Was>{nullStr(old)}</Was>}
                  {nullStr(col)}
                </td>
                <td style={{ color: 'var(--text-dim)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {col.default !== null ? <code>{col.default}</code> : '—'}
                </td>
              </tr>
            ))}
            {diff?.dropped.map(col => (
              <tr key={`dropped-${col.name}`} style={rowStyle('dropped')}>
                <td>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontWeight: 500 }}>
                    <s style={{ color: 'var(--text-dim)' }}>{col.name}</s>
                    {badge('dropped')}
                  </span>
                </td>
                <td><s style={{ color: 'var(--text-dim)' }}><code>{typeStr(col)}</code></s></td>
                <td style={{ color: 'var(--text-dim)', fontSize: '0.8rem' }}><s>{nullStr(col)}</s></td>
                <td style={{ color: 'var(--text-dim)' }}>—</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {displaySchema.primary_key && displaySchema.primary_key.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Key size={12} style={{ color: 'var(--text-dim)' }} />
            <span>{t('primary_key_label')}</span>
            {diff?.pkChanged && <Was>{(prevSchema.primary_key || []).join(', ') || '—'}</Was>}
            <code style={{ color: 'var(--text-main)' }}>{displaySchema.primary_key.join(', ')}</code>
            {diff?.pkChanged && badge('changed')}
          </div>
        )}
        {((displaySchema.foreign_keys || []).length > 0 || diff?.fkRemoved.length > 0) && (
          <div>
            <span>{t('foreign_keys_label')}</span>
            <ul style={{ marginTop: '6px', paddingLeft: '20px' }}>
              {(displaySchema.foreign_keys || []).map(fk => (
                <li key={fkKey(fk)} style={{ marginBottom: '4px' }}>
                  <code style={{ color: 'var(--text-main)' }}>{fk.column_name}</code> → <code style={{ color: 'var(--text-main)' }}>{fk.ref_table}.{fk.ref_column}</code>
                  {fk.on_delete && ` (ON DELETE ${fk.on_delete})`}{' '}
                  {diff?.fkAdded.includes(fkKey(fk)) && badge('added')}
                </li>
              ))}
              {diff?.fkRemoved.map(k => (
                <li key={`removed-${k}`} style={{ marginBottom: '4px' }}>
                  <s style={{ color: 'var(--text-dim)' }}><code>{k}</code></s> {badge('dropped')}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
