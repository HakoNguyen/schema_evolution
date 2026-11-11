import React, { useState, useEffect } from 'react';
import { Check, X, FlaskConical } from 'lucide-react';
import { useToast } from './NotificationToast';
import { useLanguage } from '../context/LanguageContext';

const btn = { display: 'inline-flex', alignItems: 'center', gap: '6px' };

export default function PendingApproval({ registryKey, onResolved }) {
  const { t } = useLanguage();
  const [draft, setDraft] = useState(null);
  const [loading, setLoading] = useState(false);
  const [isSandboxTested, setIsSandboxTested] = useState(false);
  const { addToast } = useToast();

  useEffect(() => {
    if (!registryKey) return;
    fetch(`/api/tables/${registryKey}/draft`)
      .then(res => res.json())
      .then(data => setDraft(data.exists ? data.draft : null))
      .catch(err => {
        console.error("Error fetching draft", err);
        addToast(t('err_load_draft'), "error");
      });
    setIsSandboxTested(false);
  }, [registryKey]);

  const handleAction = async (action) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/tables/${registryKey}/${action}`, { method: 'POST' });
      const data = await res.json();
      if (data.status === 'success') {
        addToast(action === 'approve' ? t('toast_approved') : t('toast_rejected'), "success");
        onResolved();
      } else {
        addToast(`${t('toast_action_failed')}: ${data.message || ''}`, "error");
      }
    } catch (err) {
      console.error(err);
      addToast(`${t('toast_network_error')}: ${err.message}`, "error");
    } finally {
      setLoading(false);
    }
  };

  const handleTestSandbox = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/tables/${registryKey}/test_sandbox`, { method: 'POST' });
      const data = await res.json();
      if (data.status === 'success') {
        setIsSandboxTested(true);
        addToast(t('toast_sandbox_ok'), "success");
      } else {
        addToast(`${t('toast_sandbox_failed')}: ${data.message || ''}`, "error");
      }
    } catch (err) {
      console.error(err);
      addToast(`${t('toast_network_error')}: ${err.message}`, "error");
    } finally {
      setLoading(false);
    }
  };

  if (!draft) return null;

  return (
    <div style={{
      background: 'var(--card-bg)',
      border: '1px solid var(--warning-border)',
      borderRadius: 'var(--radius)',
      padding: '18px 20px',
      marginBottom: '24px',
      boxShadow: 'var(--shadow)'
    }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '12px' }}>
        <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span className="dot" style={{ color: 'var(--warning-color)' }} />
          {t('breaking_alert_title')}
        </h3>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>
          {t('detected_at')} {draft.detected_at ? new Date(draft.detected_at).toLocaleString() : 'N/A'}
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '16px' }}>
        {draft.breaking_changes && draft.breaking_changes.map((change, idx) => (
          <div key={idx} style={{ fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className="pill warning" style={{ fontFamily: 'var(--mono)', borderRadius: '4px' }}>
              {change.change_type}
            </span>
            <code>{change.column_name || change.constraint_name || '?'}</code>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
        <button
          className="btn-outline"
          onClick={handleTestSandbox}
          disabled={loading || isSandboxTested}
          style={{ ...btn, color: isSandboxTested ? 'var(--success-color)' : undefined, opacity: isSandboxTested ? 1 : undefined }}
        >
          {isSandboxTested ? <Check size={14} /> : <FlaskConical size={14} />}
          {loading && !isSandboxTested ? t('testing_sandbox') : (isSandboxTested ? t('sandbox_tested') : t('test_sandbox'))}
        </button>

        <button
          className="btn-primary"
          onClick={() => handleAction('approve')}
          disabled={loading || !isSandboxTested}
          style={btn}
        >
          <Check size={14} /> {t('approve_ddl')}
        </button>

        <button
          className="btn-outline"
          onClick={() => handleAction('reject')}
          disabled={loading}
          style={{ ...btn, color: 'var(--danger-color)' }}
        >
          <X size={14} /> {t('reject')}
        </button>

        {!isSandboxTested && (
          <span style={{ fontSize: '0.78rem', color: 'var(--text-dim)', marginLeft: '4px' }}>{t('approve_hint')}</span>
        )}
      </div>
    </div>
  );
}
