import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'
import { ToastProvider } from './components/NotificationToast.jsx'
import { LanguageProvider } from './context/LanguageContext.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ToastProvider>
      <LanguageProvider>
        <App />
      </LanguageProvider>
    </ToastProvider>
  </React.StrictMode>,
)


