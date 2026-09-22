import React, { createContext, useContext, useState, useCallback } from 'react';
import { CheckCircle2, AlertTriangle, Info, X, ShieldAlert } from 'lucide-react';

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((message, type = 'info', duration = 4000) => {
    const id = Date.now() + Math.random();
    setToasts(prev => [...prev, { id, message, type }]);

    if (duration > 0) {
      setTimeout(() => {
        removeToast(id);
      }, duration);
    }
  }, []);

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ addToast, removeToast }}>
      {children}
      <div style={{
        position: 'fixed',
        bottom: '24px',
        right: '24px',
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
        maxWidth: '420px',
        width: '100%',
        pointerEvents: 'none'
      }}>
        {toasts.map(toast => {
          const isSuccess = toast.type === 'success';
          const isError = toast.type === 'error';
          const isWarning = toast.type === 'warning';

          const bgColor = isSuccess 
            ? '#064e3b' 
            : isError 
            ? '#7f1d1d' 
            : isWarning 
            ? '#78350f' 
            : '#1e293b';

          const borderColor = isSuccess 
            ? '#10b981' 
            : isError 
            ? '#f43f5e' 
            : isWarning 
            ? '#f59e0b' 
            : '#38bdf8';

          const textColor = '#f8fafc';

          return (
            <div
              key={toast.id}
              style={{
                pointerEvents: 'auto',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '12px',
                padding: '14px 16px',
                borderRadius: '8px',
                background: bgColor,
                borderLeft: `4px solid ${borderColor}`,
                boxShadow: '0 10px 25px rgba(0,0,0,0.5)',
                color: textColor,
                fontSize: '0.875rem',
                fontWeight: 500,
                lineHeight: 1.4,
                animation: 'fadeIn 0.2s ease-in-out'
              }}
            >
              <div style={{ marginTop: '2px', flexShrink: 0, color: borderColor }}>
                {isSuccess && <CheckCircle2 size={18} />}
                {isError && <ShieldAlert size={18} />}
                {isWarning && <AlertTriangle size={18} />}
                {!isSuccess && !isError && !isWarning && <Info size={18} />}
              </div>
              <div style={{ flex: 1, wordBreak: 'break-word' }}>{toast.message}</div>
              <button
                onClick={() => removeToast(toast.id)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#94a3b8',
                  cursor: 'pointer',
                  padding: '2px',
                  display: 'flex',
                  alignItems: 'center',
                  marginTop: '1px'
                }}
              >
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}
