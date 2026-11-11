import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'
import { ToastProvider } from './components/NotificationToast.jsx'
import { LanguageProvider } from './context/LanguageContext.jsx'

// Engine bật auth (main.yaml auth.users): gắn token đã lưu vào mọi request /api; 401 -> hỏi token, thử lại 1 lần.
const TOKEN_KEY = 'engine_api_token';
const rawFetch = window.fetch.bind(window);
const readToken = () => { try { return localStorage.getItem(TOKEN_KEY); } catch { return null; } };
window.fetch = async (url, opts = {}) => {
  const isApi = String(url).startsWith('/api/');
  const send = () => {
    const token = isApi && readToken();
    return rawFetch(url, token ? { ...opts, headers: { ...(opts.headers || {}), Authorization: `Bearer ${token}` } } : opts);
  };
  const res = await send();
  if (res.status !== 401 || !isApi) return res;
  const token = window.prompt('Engine API token (auth.users in config/main.yaml)');
  if (!token) return res;
  try { localStorage.setItem(TOKEN_KEY, token.trim()); } catch { return res; }
  return send();
};

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ToastProvider>
      <LanguageProvider>
        <App />
      </LanguageProvider>
    </ToastProvider>
  </React.StrictMode>,
)


