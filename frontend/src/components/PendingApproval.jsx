import React, { useState, useEffect } from 'react';
import { AlertTriangle, Check, X } from 'lucide-react';

export default function PendingApproval({ registryKey, onResolved }) {
  const [draft, setDraft] = useState(null);
  const [loading, setLoading] = useState(false);
  const [isSandboxTested, setIsSandboxTested] = useState(false);

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
      .catch(err => console.error("Error fetching draft", err));
    setIsSandboxTested(false); // Reset test status when registryKey changes
  }, [registryKey]);

  const handleAction = async (action) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/tables/${registryKey}/${action}`, {
        method: 'POST'
      });
      const data = await res.json();
      if (data.status === 'success') {
        onResolved(); // Trigger refresh
      } else {
        alert("Action failed. See console.");
      }
    } catch (err) {
      console.error(err);
      alert("Error: " + err.message);
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
      } else {
        alert("Sandbox test failed.");
      }
    } catch (err) {
      console.error(err);
      alert("Error testing sandbox: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  if (!draft) return null;

  return (
    <div className="pending-approval-card">
      <div className="pending-header">
        <AlertTriangle color="#ef4444" size={24} />
        <div>
          <h3 className="pending-title">Breaking Changes Pending Approval</h3>
          <div className="pending-subtitle">
            Detected at: {draft.detected_at || 'Unknown'}
          </div>
        </div>
      </div>
      
      <div className="pending-changes-list">
        {draft.breaking_changes && draft.breaking_changes.map((change, idx) => (
          <div key={idx} className="change-item">
            <span className="change-type">{change.change_type}</span>
            <span className="change-target">
              at <code>{change.column_name || change.constraint_name || '?'}</code>
            </span>
          </div>
        ))}
      </div>

      <div className="pending-actions">
        <button 
          className="btn-outline" 
          style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 24px', borderColor: isSandboxTested ? '#22c55e' : 'var(--border-color)', color: isSandboxTested ? '#22c55e' : 'inherit' }}
          onClick={handleTestSandbox}
          disabled={loading || isSandboxTested}
        >
          {isSandboxTested ? <Check size={18} /> : <AlertTriangle size={18} />} 
          {loading ? 'Testing...' : (isSandboxTested ? 'Sandbox Test Passed' : 'Test in Sandbox')}
        </button>

        <button 
          className="btn-primary btn-approve" 
          onClick={() => handleAction('approve')}
          disabled={loading || !isSandboxTested}
          style={{ opacity: (!isSandboxTested) ? 0.5 : 1, cursor: (!isSandboxTested) ? 'not-allowed' : 'pointer' }}
        >
          <Check size={18} /> {loading ? 'Processing...' : 'Approve & Sync'}
        </button>
        <button 
          className="btn-outline btn-reject" 
          onClick={() => handleAction('reject')}
          disabled={loading}
        >
          <X size={18} /> {loading ? 'Processing...' : 'Reject'}
        </button>
      </div>
    </div>
  );
}
