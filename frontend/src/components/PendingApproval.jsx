import React, { useState, useEffect } from 'react';
import { AlertTriangle, Check, X, ShieldAlert, TestTube } from 'lucide-react';
import { useToast } from './NotificationToast';

export default function PendingApproval({ registryKey, onResolved }) {
  const [draft, setDraft] = useState(null);
  const [loading, setLoading] = useState(false);
  const [isSandboxTested, setIsSandboxTested] = useState(false);
  const { addToast } = useToast();

  useEffect(() => {
    if (!registryKey) return;
    fetch(`/api/tables/${registryKey}/draft`)
      .then(res => res.json())
      .then(data => {
        if (data.exists) {
          setDraft(data.draft);
        } else {
          setDraft(null);
        }
      })
      .catch(err => {
        console.error("Error fetching draft", err);
        addToast("Không thể tải bản nháp schema bị tạm dừng", "error");
      });
    setIsSandboxTested(false);
  }, [registryKey]);

  const handleAction = async (action) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/tables/${registryKey}/${action}`, {
        method: 'POST'
      });
      const data = await res.json();
      if (data.status === 'success') {
        addToast(action === 'approve' ? "Đã phê duyệt và thực thi DDL thành công!" : "Đã từ chối thay đổi DDL", "success");
        onResolved();
      } else {
        addToast("Thao tác thất bại: " + (data.message || 'Không thể thực thi'), "error");
      }
    } catch (err) {
      console.error(err);
      addToast("Lỗi kết nối: " + err.message, "error");
    } finally {
      setLoading(false);
    }
  };

  const handleTestSandbox = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/tables/${registryKey}/test_sandbox`, {
        method: 'POST'
      });
      const data = await res.json();
      if (data.status === 'success') {
        setIsSandboxTested(true);
        addToast("Kiểm thử Sandbox cách ly thành công! Cấu trúc an toàn.", "success");
      } else {
        addToast("Kiểm thử Sandbox thất bại: " + (data.message || 'Phát hiện xung đột'), "error");
      }
    } catch (err) {
      console.error(err);
      addToast("Lỗi khi kiểm thử sandbox: " + err.message, "error");
    } finally {
      setLoading(false);
    }
  };


  if (!draft) return null;

  return (
    <div style={{
      background: 'var(--card-bg)',
      border: '1px solid var(--danger-border)',
      borderLeft: '4px solid var(--danger-color)',
      borderRadius: '10px',
      padding: '24px',
      marginBottom: '24px',
      color: 'var(--text-main)'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
        <ShieldAlert color="var(--danger-color)" size={24} />
        <div>
          <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: 'var(--danger-color)' }}>
            Phát Hiện Thay Đổi Có Rủi Ro Gãy Cấu Trúc (Breaking Changes Pending Approval)
          </h3>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Thời gian phát hiện: {draft.detected_at ? new Date(draft.detected_at).toLocaleString() : 'N/A'}
          </div>
        </div>
      </div>
      
      <div style={{ background: 'var(--body-bg)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '16px', marginBottom: '20px' }}>
        {draft.breaking_changes && draft.breaking_changes.map((change, idx) => (
          <div key={idx} style={{ fontSize: '0.9rem', color: 'var(--text-main)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 700, padding: '2px 8px', borderRadius: '4px', background: 'var(--danger-bg)', color: 'var(--danger-color)', textTransform: 'uppercase' }}>
              {change.change_type}
            </span>
            <span>
              tại cột/ràng buộc <code style={{ color: 'var(--primary-color)' }}>{change.column_name || change.constraint_name || '?'}</code>
            </span>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: '12px' }}>
        <button 
          onClick={handleTestSandbox}
          disabled={loading || isSandboxTested}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 20px',
            background: isSandboxTested ? 'var(--success-bg)' : 'var(--card-bg)',
            color: isSandboxTested ? 'var(--success-color)' : 'var(--text-main)',
            border: isSandboxTested ? '1px solid var(--success-border)' : '1px solid var(--border-color)',
            borderRadius: '6px',
            fontWeight: 600,
            cursor: (loading || isSandboxTested) ? 'default' : 'pointer',
            fontSize: '0.85rem'
          }}
        >
          {isSandboxTested ? <Check size={16} /> : <TestTube size={16} />} 
          {loading ? 'Đang Kiểm Thử Sandbox...' : (isSandboxTested ? 'Đã Kiểm Thử Sandbox An Toàn' : 'Chạy Thử Trên Sandbox cách ly')}
        </button>

        <button 
          onClick={() => handleAction('approve')}
          disabled={loading || !isSandboxTested}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 24px',
            background: 'var(--success-color)',
            color: '#fff',
            border: 'none',
            borderRadius: '6px',
            fontWeight: 700,
            cursor: (!isSandboxTested || loading) ? 'not-allowed' : 'pointer',
            opacity: (!isSandboxTested) ? 0.5 : 1,
            fontSize: '0.85rem'
          }}
        >
          <Check size={16} /> {loading ? 'Đang Xử Lý...' : 'Phê Duyệt & Thực Thi DDL'}
        </button>

        <button 
          onClick={() => handleAction('reject')}
          disabled={loading}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 20px',
            background: 'transparent',
            color: 'var(--danger-color)',
            border: '1px solid var(--danger-border)',
            borderRadius: '6px',
            fontWeight: 600,
            cursor: loading ? 'not-allowed' : 'pointer',
            fontSize: '0.85rem'
          }}
        >
          <X size={16} /> {loading ? 'Đang Xử Lý...' : 'Từ Chối'}
        </button>
      </div>
    </div>
  );
}
